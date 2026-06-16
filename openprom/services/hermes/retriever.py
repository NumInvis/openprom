"""Hybrid retriever for the Hermes poetry knowledge layer.

Combines dense vector search (ChromaDB) with sparse keyword search (BM25 or a
simple token-overlap fallback) via Reciprocal Rank Fusion (RRF).
"""

import logging
import os
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from openprom.services.rag.vector_store import PoetryVectorStore, get_vector_store

logger = logging.getLogger(__name__)

DEFAULT_RRF_K = 60


def _tokenize(text: str) -> List[str]:
    """Tokenize Chinese text for keyword indexing."""
    text = text.strip()
    if not text:
        return []
    try:
        import jieba
        return [t for t in jieba.lcut(text) if t.strip()]
    except Exception:
        # Fallback: character tokens, drop punctuation/whitespace
        return [c for c in text if "\u4e00" <= c <= "\u9fff"]


class _KeywordIndex:
    """In-memory keyword index over indexed poems/chunks."""

    def __init__(self, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        self.ids = ids
        self.documents = documents
        self.metadatas = metadatas
        self.tokenized_docs: List[List[str]] = [_tokenize(d) for d in documents]
        self._bm25: Optional[Any] = None
        try:
            from rank_bm25 import BM25Okapi
            self._bm25 = BM25Okapi(self.tokenized_docs)
        except Exception as e:
            logger.warning(f"BM25 not available ({e}), falling back to token overlap")

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
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
                    count * doc_counter.get(token, 0)
                    for token, count in query_counter.items()
                )
                # tf-idf-ish length normalization
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


class HermesRetriever:
    """Hybrid retriever: dense + keyword + RRF."""

    def __init__(
        self,
        store: Optional[PoetryVectorStore] = None,
        vector_weight: float = 1.0,
        keyword_weight: float = 1.0,
        rrf_k: int = DEFAULT_RRF_K,
        enable_hybrid: bool = True,
    ):
        self.store = store or get_vector_store()
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.rrf_k = rrf_k
        self.enable_hybrid = enable_hybrid
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
            data = self.store._collection.get(include=["documents", "metadatas"])  # type: ignore
            ids = data.get("ids", [])
            docs = data.get("documents", [])
            metas = data.get("metadatas", [])
            if not ids:
                self._keyword_index = _KeywordIndex([], [], [])
            else:
                self._keyword_index = _KeywordIndex(docs, metas, ids)
            self._indexed_count = count
        except Exception as e:
            logger.warning(f"Failed to build keyword index: {e}")

    def _passes_filters(self, meta: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        for key, value in filters.items():
            if meta.get(key) != value:
                return False
        return True

    def _vector_search(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        return self.store.search(query, top_k=top_k, filters=filters)

    def _keyword_search(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        self._build_keyword_index()
        if self._keyword_index is None:
            return []
        scored = self._keyword_index.search(query, top_k=top_k * 2)
        # Map id -> row
        id_to_meta_doc = {
            id_: (doc, meta)
            for id_, doc, meta in zip(
                self._keyword_index.ids,
                self._keyword_index.documents,
                self._keyword_index.metadatas,
            )
        }
        results = []
        for doc_id, score in scored:
            doc, meta = id_to_meta_doc.get(doc_id, ("", {}))
            if filters and not self._passes_filters(meta, filters):
                continue
            results.append({
                "id": doc_id,
                "text": doc,
                "metadata": meta,
                "keyword_score": score,
            })
        return results[:top_k]

    def _rank_ids(
        self,
        vector_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        scores: Dict[str, float] = {}
        details: Dict[str, Dict[str, Any]] = {}

        for rank, r in enumerate(vector_results):
            id_ = r["id"]
            scores[id_] = scores.get(id_, 0.0) + self.vector_weight / (self.rrf_k + rank + 1)
            details[id_] = r

        for rank, r in enumerate(keyword_results):
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

    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search poems by hybrid semantic + keyword ranking."""
        if filters is None:
            filters = {}
        vector_results = self._vector_search(query, top_k=top_k, filters=filters)
        if not self.enable_hybrid:
            return vector_results
        keyword_results = self._keyword_search(query, top_k=top_k, filters=filters)
        return self._rank_ids(vector_results, keyword_results, top_k=top_k)

    def refresh(self) -> None:
        """Force rebuild of the keyword index."""
        self._indexed_count = -1
        self._build_keyword_index()

    def retrieve_poems(
        self,
        query: str,
        form: Optional[str] = None,
        dynasty: Optional[str] = None,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        filters: Dict[str, Any] = {}
        if form:
            filters["form"] = form
        if dynasty:
            filters["dynasty"] = dynasty
        return self.hybrid_search(query, top_k=top_k, filters=filters if filters else None)

    def retrieve_lines(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        return self.hybrid_search(query, top_k=top_k)


_global_retriever: Optional[HermesRetriever] = None


def get_hermes_retriever() -> HermesRetriever:
    global _global_retriever
    if _global_retriever is None:
        from openprom.infrastructure.config.settings import get_settings
        settings = get_settings()
        hcfg = getattr(settings, "hermes", None)
        if hcfg is None:
            return HermesRetriever()
        _global_retriever = HermesRetriever(
            vector_weight=getattr(hcfg, "vector_weight", 1.0),
            keyword_weight=getattr(hcfg, "keyword_weight", 1.0),
            rrf_k=getattr(hcfg, "rrf_k", DEFAULT_RRF_K),
            enable_hybrid=getattr(hcfg, "enable_hybrid", True),
        )
    return _global_retriever
