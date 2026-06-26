"""Retrieval pipeline: the five-stage retrieval system.

Query → [1 Query理解] → [2 召回] → [3 Rerank] → [4 融合/去重] → [5 结构化]

This is the upgraded HermesRetriever for the knowledge layer.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from openprom.knowledge.providers import (
    EmbeddingProvider,
    NoOpReranker,
    RerankProvider,
    get_embedding_provider,
    get_rerank_provider,
)
from openprom.knowledge.providers.vector_store import ChromaVectorStore, get_vector_store
from openprom.knowledge.rule_signals import extract_rule_signals, fuse_with_rule_signals
from openprom.knowledge.schema import Provenance, RetrievalResult, RetrievalResultSet

try:
    from openprom.knowledge.metrics import (
        record_cache_hit,
        record_embedding_call,
        record_rerank,
        record_retrieval,
    )
except Exception:

    def record_retrieval(*a, **kw):
        pass

    def record_rerank(*a, **kw):
        pass

    def record_cache_hit(*a, **kw):
        pass

    def record_embedding_call(*a, **kw):
        pass


logger = logging.getLogger(__name__)

DEFAULT_RRF_K = 60


def _tokenize(text: str) -> List[str]:
    """Tokenize Chinese text for keyword search."""
    text = text.strip()
    if not text:
        return []
    try:
        import jieba

        return [t for t in jieba.lcut(text) if t.strip()]
    except Exception:
        return [c for c in text if "\u4e00" <= c <= "\u9fff"]


class _KeywordIndex:
    """In-memory BM25 index over indexed documents."""

    def __init__(self, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        self.ids = ids
        self.documents = documents
        self.metadatas = metadatas
        self.tokenized_docs = [_tokenize(d) for d in documents]
        self._bm25 = None
        try:
            from rank_bm25 import BM25Okapi

            self._bm25 = BM25Okapi(self.tokenized_docs)
        except Exception as e:
            logger.warning(f"BM25 not available ({e}), falling back to token overlap")

    def search(self, query: str, top_k: int = 10) -> List[tuple]:
        tokens = _tokenize(query)
        if not tokens:
            return []
        if self._bm25 is not None:
            scores = self._bm25.get_scores(tokens)
        else:
            query_counter = Counter(tokens)
            scores = []
            for doc_tokens in self.tokenized_docs:
                doc_counter = Counter(doc_tokens)
                score = sum(
                    count * doc_counter.get(token, 0) for token, count in query_counter.items()
                )
                if doc_tokens:
                    score /= len(doc_tokens) ** 0.5
                scores.append(score)
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in indexed[:top_k]:
            if score <= 0:
                continue
            results.append((self.ids[idx], float(score)))
        return results


_TASK_PROFILES: Dict[str, Dict[str, Any]] = {
    "generate_couplet": {
        "top_k": 5,
        "top_k_recall": 15,
        "preferred_chunk_types": ["couplet", "poem"],
        "description": "对联生成：需要对仗范例",
    },
    "generate_shi": {
        "top_k": 5,
        "top_k_recall": 20,
        "preferred_chunk_types": ["poem", "quatrain"],
        "description": "律诗生成：需要完整律诗和颔颈联范例",
    },
    "analyze_couplet": {
        "top_k": 5,
        "top_k_recall": 10,
        "preferred_chunk_types": ["poem", "couplet"],
        "description": "对联评分：需要完整诗歌语境",
    },
    "check_meter": {
        "top_k": 3,
        "top_k_recall": 10,
        "preferred_chunk_types": ["poem"],
        "description": "格律检测：需要合规范例",
    },
    "general": {
        "top_k": 5,
        "top_k_recall": 20,
        "preferred_chunk_types": [],
        "description": "通用检索",
    },
}


class QueryPlanner:
    """Selects retrieval parameters based on task type."""

    def __init__(self, profiles: Optional[Dict[str, Dict[str, Any]]] = None):
        self.profiles = profiles or _TASK_PROFILES

    def plan(self, task_type: str = "general") -> Dict[str, Any]:
        """Return retrieval params for the given task type."""
        return self.profiles.get(task_type, self.profiles["general"])

    def list_tasks(self) -> List[str]:
        return list(self.profiles.keys())


class RetrievalPipeline:
    """Five-stage retrieval pipeline for the knowledge layer.

    Stages:
    1. Query understanding (task-aware chunk strategy selection)
    2. Recall (dense + sparse parallel)
    3. Rerank (cross-encoder, optional)
    4. Fusion/Dedup (RRF + same-poem aggregation)
    5. Structured output (RetrievalResult)
    """

    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        rerank_provider: Optional[RerankProvider] = None,
        vector_store: Optional[ChromaVectorStore] = None,
        rrf_k: int = DEFAULT_RRF_K,
        vector_weight: float = 1.0,
        keyword_weight: float = 1.0,
        enable_hybrid: bool = True,
        w_semantic: float = 0.6,
        w_rule: float = 0.4,
        enable_rule_signals: bool = True,
        query_planner: Optional[QueryPlanner] = None,
    ):
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.rerank_provider = rerank_provider or get_rerank_provider()
        self.store = vector_store or get_vector_store()
        self.rrf_k = rrf_k
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.enable_hybrid = enable_hybrid
        self.w_semantic = w_semantic
        self.w_rule = w_rule
        self.enable_rule_signals = enable_rule_signals
        self.query_planner = query_planner or QueryPlanner()
        self._rerank_cache = None
        self._retrieval_cache = None
        try:
            from openprom.knowledge.memory.cache import get_rerank_cache, get_retrieval_cache

            self._rerank_cache = get_rerank_cache()
            self._retrieval_cache = get_retrieval_cache()
        except Exception:
            pass
        self._keyword_index: Optional[_KeywordIndex] = None
        self._indexed_count: int = -1

    def _build_keyword_index(self) -> None:
        try:
            count = self.store.count()
        except Exception as e:
            logger.warning(f"Cannot count vector store: {e}")
            return
        if count == self._indexed_count and self._keyword_index is not None:
            return
        try:
            data = self.store._collection.get(include=["documents", "metadatas"])
            ids = data.get("ids", [])
            docs = data.get("documents", [])
            metas = data.get("metadatas", [])
            self._keyword_index = _KeywordIndex(docs, metas, ids)
            self._indexed_count = count
        except Exception as e:
            logger.warning(f"Failed to build keyword index: {e}")

    def _dense_recall(
        self, query: str, top_k: int, filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Stage 2a: Dense vector recall."""
        query_emb = self.embedding_provider.embed_query(query)
        try:
            return self.store.query(query_emb, top_k=top_k, filters=filters)
        except Exception as e:
            logger.warning(f"Dense recall failed: {e}")
            return []

    def _sparse_recall(
        self, query: str, top_k: int, filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Stage 2b: Sparse keyword recall."""
        self._build_keyword_index()
        if self._keyword_index is None:
            return []
        scored = self._keyword_index.search(query, top_k=top_k * 2)
        id_to_data = {
            id_: (doc, meta)
            for id_, doc, meta in zip(
                self._keyword_index.ids,
                self._keyword_index.documents,
                self._keyword_index.metadatas,
            )
        }
        results = []
        for doc_id, score in scored:
            doc, meta = id_to_data.get(doc_id, ("", {}))
            if filters:
                skip = False
                for k, v in filters.items():
                    if meta.get(k) != v:
                        skip = True
                        break
                if skip:
                    continue
            results.append(
                {
                    "id": doc_id,
                    "text": doc,
                    "metadata": meta,
                    "keyword_score": score,
                }
            )
        return results[:top_k]

    def _rrf_fusion(
        self,
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Stage 4a: Reciprocal Rank Fusion."""
        scores: Dict[str, float] = {}
        details: Dict[str, Dict[str, Any]] = {}

        for rank, r in enumerate(dense_results):
            id_ = r["id"]
            scores[id_] = scores.get(id_, 0.0) + self.vector_weight / (self.rrf_k + rank + 1)
            details[id_] = r

        for rank, r in enumerate(sparse_results):
            id_ = r["id"]
            scores[id_] = scores.get(id_, 0.0) + self.keyword_weight / (self.rrf_k + rank + 1)
            if id_ not in details:
                details[id_] = r

        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        output = []
        for id_, score in sorted_ids[:top_k]:
            item = details[id_].copy()
            item["hybrid_score"] = score
            output.append(item)
        return output

    def _dedup_by_poem(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Stage 4b: Aggregate chunks from the same poem, keep best representative."""
        seen_poems: Dict[str, List[Dict[str, Any]]] = {}
        for r in results:
            # Extract base poem id (before _couplet_ or _quatrain_ suffix)
            poem_id = r["id"].split("_couplet_")[0].split("_quatrain_")[0]
            seen_poems.setdefault(poem_id, []).append(r)

        deduped = []
        for poem_id, chunks in seen_poems.items():
            # Keep the chunk with the best score
            best = max(chunks, key=lambda x: x.get("hybrid_score", x.get("distance", 0)))
            deduped.append(best)
        return deduped

    def _apply_rerank(
        self, query: str, results: List[Dict[str, Any]], top_k: int
    ) -> List[Dict[str, Any]]:
        """Stage 3: Cross-encoder rerank with enhanced doc text and caching."""
        if isinstance(self.rerank_provider, NoOpReranker):
            return results[:top_k]

        # Check rerank cache
        doc_ids = [r.get("id", "") for r in results]
        cached_scores = self._rerank_cache.get(query, doc_ids) if self._rerank_cache else None
        if cached_scores is not None:
            record_cache_hit("rerank")
            record_rerank(hit=True)
            reranked = []
            for idx, score in cached_scores:
                if idx < len(results):
                    item = results[idx].copy()
                    item["rerank_score"] = score
                    reranked.append(item)
            return reranked

        # Build enhanced doc text with metadata for better rerank quality
        docs = []
        for r in results:
            meta = r.get("metadata", {})
            text = r.get("text", "")
            parts = []
            if meta.get("title"):
                parts.append(meta["title"])
            if meta.get("author"):
                parts.append(meta["author"])
            if meta.get("form"):
                parts.append(meta["form"])
            header = " · ".join(parts)
            doc = f"{header} {text}" if header else text
            docs.append(doc)
        try:
            ranked = self.rerank_provider.rerank(query, docs, top_k=top_k)
            # Cache the rerank scores
            if self._rerank_cache:
                self._rerank_cache.put(query, doc_ids, ranked)
            record_rerank(hit=True)
            reranked = []
            for idx, score in ranked:
                if idx < len(results):
                    item = results[idx].copy()
                    item["rerank_score"] = score
                    reranked.append(item)
            return reranked
        except Exception as e:
            logger.warning(f"Rerank failed, falling back to original order: {e}")
            return results[:top_k]

    def _build_structured_results(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        target_form: Optional[str] = None,
        target_rhyme_category: Optional[str] = None,
    ) -> RetrievalResultSet:
        """Stage 5: Convert raw candidates into structured RetrievalResults."""
        results = []
        for item in candidates:
            text = item.get("text", "")
            meta = item.get("metadata", {})

            # Compute rule signals
            rule_signals = {}
            if self.enable_rule_signals:
                rule_signals = extract_rule_signals(text, meta, target_form, target_rhyme_category)

            # Compute final score
            semantic_score = item.get("hybrid_score", 1.0 - item.get("distance", 0.0))
            rerank_score = item.get("rerank_score")

            if rerank_score is not None:
                final_score = fuse_with_rule_signals(
                    rerank_score, rule_signals, self.w_semantic, self.w_rule
                )
            else:
                final_score = fuse_with_rule_signals(
                    semantic_score, rule_signals, self.w_semantic, self.w_rule
                )

            # Build annotated text
            dynasty = meta.get("dynasty", "")
            author = meta.get("author", "")
            title = meta.get("title", "")
            form = meta.get("form", "")
            header = " ".join(filter(None, [dynasty, author, title]))

            parts = [f"【{form or '诗'}·{header}】"]
            parts.append(text)
            if rule_signals:
                signals_str = " | ".join(
                    f"{k}: {v:.2f}" for k, v in rule_signals.items() if v != 0.5
                )
                if signals_str:
                    parts.append(f"  规则信号: {signals_str}")
            annotated = "\n".join(parts)

            provenance = Provenance(
                source=meta.get("source", "unknown"),
                dynasty=dynasty or None,
                form=form or None,
                confidence=float(meta.get("confidence", 0.95)),
                version=meta.get("version", ""),
            )

            results.append(
                RetrievalResult(
                    id=item.get("id", ""),
                    content=text,
                    annotated=annotated,
                    semantic_score=semantic_score,
                    rerank_score=rerank_score,
                    rule_signals=rule_signals,
                    final_score=final_score,
                    provenance=provenance,
                    chunk_type=meta.get("chunk_type", "poem"),
                    metadata=meta,
                )
            )

        # Sort by final_score descending
        results.sort(key=lambda r: r.final_score, reverse=True)

        return RetrievalResultSet(
            results=results,
            query=query,
            total_candidates=len(candidates),
            pipeline_stages=["dense", "bm25", "rrf", "dedup", "rerank", "rule_fusion"],
        )

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        top_k_recall: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        target_form: Optional[str] = None,
        target_rhyme_category: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> RetrievalResultSet:
        """Full five-stage retrieval pipeline.

        Args:
            query: Search query (theme, imagery, etc.)
            top_k: Final number of results to return.
            top_k_recall: Number of candidates to recall before reranking.
            filters: ChromaDB metadata filters.
            target_form: Target poetic form for rule signals.
            target_rhyme_category: Target rhyme category for rule signals.
            task_type: Task type for query planner (e.g. 'generate_couplet').
        """
        import time

        t0 = time.time()

        # Apply query planner if task_type specified
        if task_type:
            profile = self.query_planner.plan(task_type)
            top_k = profile.get("top_k", top_k)
            top_k_recall = profile.get("top_k_recall", top_k_recall)

        # Check retrieval cache
        if self._retrieval_cache is not None:
            cached = self._retrieval_cache.get(query, top_k, filters)
            if cached is not None:
                record_cache_hit("retrieval")
                return cached

        # Stage 2: Recall
        dense_results = self._dense_recall(query, top_k=top_k_recall, filters=filters)
        record_embedding_call()

        if self.enable_hybrid:
            sparse_results = self._sparse_recall(query, top_k=top_k_recall, filters=filters)
            # Stage 4a: RRF fusion
            fused = self._rrf_fusion(dense_results, sparse_results, top_k=top_k_recall)
        else:
            fused = dense_results[:top_k_recall]

        # Stage 4b: Dedup by poem
        deduped = self._dedup_by_poem(fused)

        # Stage 3: Rerank
        reranked = self._apply_rerank(query, deduped, top_k=top_k)

        # Stage 5: Build structured results
        result_set = self._build_structured_results(
            query, reranked[:top_k], target_form, target_rhyme_category
        )

        # Populate retrieval cache
        if self._retrieval_cache is not None:
            self._retrieval_cache.put(query, top_k, result_set, filters)

        latency = time.time() - t0
        record_retrieval(
            query_type=task_type or "general",
            latency=latency,
            result_count=len(result_set),
        )

        return result_set


_global_pipeline: Optional[RetrievalPipeline] = None


def get_retrieval_pipeline() -> RetrievalPipeline:
    """Get or create the singleton retrieval pipeline."""
    global _global_pipeline
    if _global_pipeline is not None:
        return _global_pipeline
    from openprom.infrastructure.config.settings import get_settings

    settings = get_settings()
    hcfg = getattr(settings, "hermes", None)
    _global_pipeline = RetrievalPipeline(
        vector_weight=getattr(hcfg, "vector_weight", 1.0) if hcfg else 1.0,
        keyword_weight=getattr(hcfg, "keyword_weight", 1.0) if hcfg else 1.0,
        rrf_k=getattr(hcfg, "rrf_k", DEFAULT_RRF_K) if hcfg else DEFAULT_RRF_K,
        enable_hybrid=getattr(hcfg, "enable_hybrid", True) if hcfg else True,
    )
    return _global_pipeline


def reset_pipeline() -> None:
    """Reset singleton (for testing)."""
    global _global_pipeline
    _global_pipeline = None
