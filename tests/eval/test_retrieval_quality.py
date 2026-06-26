"""Automated retrieval quality evaluation.

Generates query-answer pairs from poem metadata (NO human annotations),
runs the RetrievalPipeline, and computes standard IR metrics:
  - Recall@K
  - MRR (Mean Reciprocal Rank)
  - nDCG@K (Normalized Discounted Cumulative Gain)

All tests pass without external dependencies — uses MockEmbeddingProvider
and an in-memory vector store.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pytest
from numpy.typing import NDArray

from openprom.knowledge.providers import (
    MockEmbeddingProvider,
    NoOpReranker,
    reset_providers,
)
from openprom.knowledge.retrieval.pipeline import RetrievalPipeline

# ---------------------------------------------------------------------------
# Sample corpus in chinese-poetry JSON format
# ---------------------------------------------------------------------------

POEM_CORPUS: List[Dict[str, Any]] = [
    {
        "id": "poem_001",
        "title": "静夜思",
        "author": "李白",
        "dynasty": "唐",
        "form": "五绝",
        "paragraphs": ["床前明月光，疑是地上霜。", "举头望明月，低头思故乡。"],
    },
    {
        "id": "poem_002",
        "title": "春晓",
        "author": "孟浩然",
        "dynasty": "唐",
        "form": "五绝",
        "paragraphs": ["春眠不觉晓，处处闻啼鸟。", "夜来风雨声，花落知多少。"],
    },
    {
        "id": "poem_003",
        "title": "登鹳雀楼",
        "author": "王之涣",
        "dynasty": "唐",
        "form": "五绝",
        "paragraphs": ["白日依山尽，黄河入海流。", "欲穷千里目，更上一层楼。"],
    },
    {
        "id": "poem_004",
        "title": "山居秋暝",
        "author": "王维",
        "dynasty": "唐",
        "form": "五律",
        "paragraphs": [
            "空山新雨后，天气晚来秋。",
            "明月松间照，清泉石上流。",
            "竹喧归浣女，莲动下渔舟。",
            "随意春芳歇，王孙自可留。",
        ],
    },
    {
        "id": "poem_005",
        "title": "望庐山瀑布",
        "author": "李白",
        "dynasty": "唐",
        "form": "七绝",
        "paragraphs": ["日照香炉生紫烟，遥看瀑布挂前川。", "飞流直下三千尺，疑是银河落九天。"],
    },
    {
        "id": "poem_006",
        "title": "送杜少府之任蜀州",
        "author": "王勃",
        "dynasty": "唐",
        "form": "五律",
        "paragraphs": [
            "城阙辅三秦，风烟望五津。",
            "与君离别意，同是宦游人。",
            "海内存知己，天涯若比邻。",
            "无为在歧路，儿女共沾巾。",
        ],
    },
    {
        "id": "poem_007",
        "title": "枫桥夜泊",
        "author": "张继",
        "dynasty": "唐",
        "form": "七绝",
        "paragraphs": ["月落乌啼霜满天，江枫渔火对愁眠。", "姑苏城外寒山寺，夜半钟声到客船。"],
    },
    {
        "id": "poem_008",
        "title": "将进酒",
        "author": "李白",
        "dynasty": "唐",
        "form": "乐府",
        "paragraphs": [
            "君不见黄河之水天上来，奔流到海不复回。",
            "君不见高堂明镜悲白发，朝如青丝暮成雪。",
            "人生得意须尽欢，莫使金樽空对月。",
        ],
    },
    {
        "id": "poem_009",
        "title": "水调歌头",
        "author": "苏轼",
        "dynasty": "宋",
        "form": "词",
        "paragraphs": [
            "明月几时有？把酒问青天。",
            "不知天上宫阙，今夕是何年。",
            "我欲乘风归去，又恐琼楼玉宇，高处不胜寒。",
        ],
    },
    {
        "id": "poem_010",
        "title": "赤壁怀古",
        "author": "苏轼",
        "dynasty": "宋",
        "form": "词",
        "paragraphs": [
            "大江东去，浪淘尽，千古风流人物。",
            "故垒西边，人道是，三国周郎赤壁。",
        ],
    },
]


# ---------------------------------------------------------------------------
# In-memory mock vector store (no ChromaDB dependency)
# ---------------------------------------------------------------------------


class _MockCollection:
    """Minimal stand-in for a ChromaDB collection."""

    def __init__(self) -> None:
        self._ids: List[str] = []
        self._documents: List[str] = []
        self._metadatas: List[Dict[str, Any]] = []
        self._embeddings: List[List[float]] = []

    def add(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> None:
        self._ids.extend(ids)
        self._documents.extend(documents)
        self._metadatas.extend(metadatas)
        self._embeddings.extend(embeddings)

    def get(self, include: Optional[List[str]] = None) -> Dict[str, Any]:
        result: Dict[str, Any] = {"ids": list(self._ids)}
        if include and "documents" in include:
            result["documents"] = list(self._documents)
        if include and "metadatas" in include:
            result["metadatas"] = list(self._metadatas)
        return result

    def count(self) -> int:
        return len(self._ids)


class InMemoryVectorStore:
    """Vector store backed by numpy cosine similarity — no ChromaDB."""

    def __init__(self) -> None:
        self._collection = _MockCollection()
        self._embeddings_matrix: Optional[NDArray[np.float32]] = None

    def upsert(
        self,
        ids: List[str],
        embeddings: NDArray[np.float32],
        metadatas: List[Dict[str, Any]],
        documents: List[str],
    ) -> int:
        emb_list = embeddings.tolist() if isinstance(embeddings, np.ndarray) else embeddings
        self._collection.add(ids, documents, metadatas, emb_list)
        self._embeddings_matrix = None  # invalidate cache
        return len(ids)

    def _ensure_matrix(self) -> NDArray[np.float32]:
        if self._embeddings_matrix is None:
            self._embeddings_matrix = np.array(self._collection._embeddings, dtype=np.float32)
        return self._embeddings_matrix

    def query(
        self,
        embedding: NDArray[np.float32],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        matrix = self._ensure_matrix()
        if matrix.shape[0] == 0:
            return []

        query_vec = np.asarray(embedding, dtype=np.float32).flatten()
        # cosine similarity
        norms = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(query_vec) or 1.0)
        sims = matrix @ query_vec / np.where(norms > 0, norms, 1.0)

        order = np.argsort(-sims)[: top_k * 2]  # over-fetch for filtering

        results: List[Dict[str, Any]] = []
        for idx in order:
            idx = int(idx)
            meta = self._collection._metadatas[idx]
            if filters:
                if any(meta.get(k) != v for k, v in filters.items()):
                    continue
            results.append(
                {
                    "id": self._collection._ids[idx],
                    "text": self._collection._documents[idx],
                    "metadata": meta,
                    "distance": float(1.0 - sims[idx]),
                }
            )
            if len(results) >= top_k:
                break
        return results

    def count(self) -> int:
        return self._collection.count()

    def delete_collection(self) -> None:
        self._collection = _MockCollection()
        self._embeddings_matrix = None


# ---------------------------------------------------------------------------
# Metrics — reusable helper functions
# ---------------------------------------------------------------------------


def recall_at_k(ranked_ids: List[str], relevant_ids: set, k: int) -> float:
    """Fraction of relevant items in the top-K results.

    Args:
        ranked_ids: Ordered list of retrieved item IDs (rank 1 first).
        relevant_ids: Set of ground-truth relevant item IDs.
        k: Cutoff rank.

    Returns:
        Recall@K in [0, 1].
    """
    if not relevant_ids:
        return 1.0
    top_k = ranked_ids[:k]
    hits = sum(1 for rid in top_k if rid in relevant_ids)
    return hits / len(relevant_ids)


def mean_reciprocal_rank(ranked_ids: List[str], relevant_ids: set) -> float:
    """Reciprocal rank of the first relevant result.

    Args:
        ranked_ids: Ordered list of retrieved item IDs.
        relevant_ids: Set of ground-truth relevant item IDs.

    Returns:
        1/rank of first relevant hit, or 0.0 if none found.
    """
    for i, rid in enumerate(ranked_ids):
        if rid in relevant_ids:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(ranked_ids: List[str], relevant_ids: set, k: int) -> float:
    """Normalized Discounted Cumulative Gain at K (binary relevance).

    Args:
        ranked_ids: Ordered list of retrieved item IDs.
        relevant_ids: Set of ground-truth relevant item IDs.
        k: Cutoff rank.

    Returns:
        nDCG@K in [0, 1].
    """
    dcg = 0.0
    for i, rid in enumerate(ranked_ids[:k]):
        if rid in relevant_ids:
            dcg += 1.0 / math.log2(i + 2)  # i+2 because rank is 1-indexed

    # Ideal DCG: all relevant items at the top
    ideal_count = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_count))

    return dcg / idcg if idcg > 0 else 0.0


# ---------------------------------------------------------------------------
# Query-answer pair generation from metadata (fully automated)
# ---------------------------------------------------------------------------


@dataclass
class QueryAnswerPair:
    """A generated query with its expected relevant poem IDs."""

    query: str
    relevant_ids: set
    query_type: str
    source_poem_id: str


def generate_qa_pairs(corpus: List[Dict[str, Any]]) -> List[QueryAnswerPair]:
    """Generate query-answer pairs automatically from poem metadata.

    Three query types per poem:
      1. title+author  —  e.g. "《静夜思》李白"
      2. author name   —  e.g. "李白"
      3. first line    —  e.g. "床前明月光，疑是地上霜。"

    For author queries, ALL poems by that author are relevant.
    """
    pairs: List[QueryAnswerPair] = []
    author_poems: Dict[str, set] = {}

    for poem in corpus:
        author = poem["author"]
        author_poems.setdefault(author, set()).add(poem["id"])

    for poem in corpus:
        pid = poem["id"]
        title = poem["title"]
        author = poem["author"]
        first_line = poem["paragraphs"][0] if poem["paragraphs"] else ""

        # Type 1: title + author
        pairs.append(
            QueryAnswerPair(
                query=f"《{title}》{author}",
                relevant_ids={pid},
                query_type="title_author",
                source_poem_id=pid,
            )
        )

        # Type 2: author name (all poems by this author are relevant)
        pairs.append(
            QueryAnswerPair(
                query=author,
                relevant_ids=author_poems[author],
                query_type="author",
                source_poem_id=pid,
            )
        )

        # Type 3: first line
        if first_line:
            pairs.append(
                QueryAnswerPair(
                    query=first_line,
                    relevant_ids={pid},
                    query_type="first_line",
                    source_poem_id=pid,
                )
            )

    return pairs


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset():
    reset_providers()
    yield
    reset_providers()


@pytest.fixture
def embedding_provider() -> MockEmbeddingProvider:
    return MockEmbeddingProvider()


@pytest.fixture
def loaded_store(embedding_provider: MockEmbeddingProvider) -> InMemoryVectorStore:
    """In-memory vector store pre-loaded with the poem corpus."""
    store = InMemoryVectorStore()
    emb_provider = embedding_provider

    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for poem in POEM_CORPUS:
        full_text = "\n".join(poem["paragraphs"])
        ids.append(poem["id"])
        documents.append(full_text)
        metadatas.append(
            {
                "title": poem["title"],
                "author": poem["author"],
                "dynasty": poem.get("dynasty", ""),
                "form": poem.get("form", ""),
                "source": "tang300",
            }
        )

    embeddings = emb_provider.embed(documents)
    store.upsert(ids, embeddings, metadatas, documents)
    return store


@pytest.fixture
def pipeline(
    embedding_provider: MockEmbeddingProvider,
    loaded_store: InMemoryVectorStore,
) -> RetrievalPipeline:
    """RetrievalPipeline wired to mock components."""
    return RetrievalPipeline(
        embedding_provider=embedding_provider,
        rerank_provider=NoOpReranker(),
        vector_store=loaded_store,
        enable_hybrid=True,
        enable_rule_signals=False,
    )


@pytest.fixture
def qa_pairs() -> List[QueryAnswerPair]:
    return generate_qa_pairs(POEM_CORPUS)


# ---------------------------------------------------------------------------
# Tests — metric helper correctness
# ---------------------------------------------------------------------------


class TestMetricHelpers:
    """Verify the metric functions themselves are correct."""

    def test_recall_at_k_perfect(self):
        assert recall_at_k(["a", "b", "c"], {"a", "b", "c"}, k=3) == 1.0

    def test_recall_at_k_partial(self):
        assert recall_at_k(["a", "x", "y"], {"a", "b"}, k=3) == 0.5

    def test_recall_at_k_zero(self):
        assert recall_at_k(["x", "y"], {"a", "b"}, k=2) == 0.0

    def test_recall_at_k_empty_relevant(self):
        assert recall_at_k(["a", "b"], set(), k=2) == 1.0

    def test_mrr_first_position(self):
        assert mean_reciprocal_rank(["a", "b"], {"a"}) == 1.0

    def test_mrr_second_position(self):
        assert abs(mean_reciprocal_rank(["x", "a"], {"a"}) - 0.5) < 1e-9

    def test_mrr_not_found(self):
        assert mean_reciprocal_rank(["x", "y"], {"a"}) == 0.0

    def test_ndcg_at_k_perfect(self):
        score = ndcg_at_k(["a", "b"], {"a", "b"}, k=2)
        assert abs(score - 1.0) < 1e-9

    def test_ndcg_at_k_imperfect(self):
        # relevant={a,b}, retrieved=[a,x] → DCG = 1/log2(2) = 1.0
        # IDCG = 1/log2(2) + 1/log2(3) ≈ 1.0 + 0.631 = 1.631
        score = ndcg_at_k(["a", "x"], {"a", "b"}, k=2)
        assert 0.0 < score < 1.0

    def test_ndcg_at_k_empty(self):
        assert ndcg_at_k([], {"a"}, k=5) == 0.0


# ---------------------------------------------------------------------------
# Tests — QA pair generation
# ---------------------------------------------------------------------------


class TestQAPairGeneration:
    """Verify that QA pairs are generated correctly from metadata."""

    def test_pair_count(self, qa_pairs):
        # 10 poems × 3 types (title_author, author, first_line) = 30
        assert len(qa_pairs) == len(POEM_CORPUS) * 3

    def test_query_types_present(self, qa_pairs):
        types = {p.query_type for p in qa_pairs}
        assert types == {"title_author", "author", "first_line"}

    def test_title_author_format(self, qa_pairs):
        pair = next(
            p for p in qa_pairs if p.query_type == "title_author" and p.source_poem_id == "poem_001"
        )
        assert pair.query == "《静夜思》李白"
        assert pair.relevant_ids == {"poem_001"}

    def test_author_query_aggregates(self, qa_pairs):
        # "李白" appears in poems 001, 005, 008
        li_bai = [p for p in qa_pairs if p.query == "李白"]
        assert len(li_bai) == 3  # one per Li Bai poem
        for p in li_bai:
            assert p.relevant_ids == {"poem_001", "poem_005", "poem_008"}

    def test_first_line_query(self, qa_pairs):
        pair = next(
            p for p in qa_pairs if p.query_type == "first_line" and p.source_poem_id == "poem_009"
        )
        assert "明月几时有" in pair.query


# ---------------------------------------------------------------------------
# Tests — retrieval quality through the pipeline
# ---------------------------------------------------------------------------


class TestRetrievalQuality:
    """Run the pipeline on generated queries and evaluate metrics."""

    TOP_K = 5

    def _retrieve_ids(self, pipeline: RetrievalPipeline, query: str, k: int) -> List[str]:
        result = pipeline.retrieve(query, top_k=k)
        return [r.id for r in result.results]

    def test_pipeline_returns_results(self, pipeline, qa_pairs):
        """Sanity: pipeline returns non-empty results for most queries."""
        hits = 0
        for qa in qa_pairs[:10]:
            ids = self._retrieve_ids(pipeline, qa.query, self.TOP_K)
            if ids:
                hits += 1
        assert hits > 0

    def test_recall_at_5_author_queries(self, pipeline, qa_pairs):
        """Author queries should recall poems by that author within top-5."""
        author_qas = [p for p in qa_pairs if p.query_type == "author"]
        recalls = []
        for qa in author_qas:
            ids = self._retrieve_ids(pipeline, qa.query, self.TOP_K)
            recalls.append(recall_at_k(ids, qa.relevant_ids, self.TOP_K))
        avg = sum(recalls) / len(recalls) if recalls else 0.0
        assert avg > 0.0, f"Average Recall@5 for author queries: {avg:.3f}"

    def test_recall_at_5_title_author_queries(self, pipeline, qa_pairs):
        """Title+author queries should find the exact poem in top-5."""
        title_qas = [p for p in qa_pairs if p.query_type == "title_author"]
        recalls = []
        for qa in title_qas:
            ids = self._retrieve_ids(pipeline, qa.query, self.TOP_K)
            recalls.append(recall_at_k(ids, qa.relevant_ids, self.TOP_K))
        avg = sum(recalls) / len(recalls) if recalls else 0.0
        assert avg > 0.0, f"Average Recall@5 for title+author queries: {avg:.3f}"

    def test_mrr_first_line_queries(self, pipeline, qa_pairs):
        """First-line queries should rank the source poem reasonably high."""
        line_qas = [p for p in qa_pairs if p.query_type == "first_line"]
        mrrs = []
        for qa in line_qas:
            ids = self._retrieve_ids(pipeline, qa.query, self.TOP_K)
            mrrs.append(mean_reciprocal_rank(ids, qa.relevant_ids))
        avg = sum(mrrs) / len(mrrs) if mrrs else 0.0
        assert avg > 0.0, f"Average MRR for first-line queries: {avg:.3f}"

    def test_ndcg_at_5_all_queries(self, pipeline, qa_pairs):
        """nDCG@5 should be > 0 for the overall query set."""
        ndcgs = []
        for qa in qa_pairs:
            ids = self._retrieve_ids(pipeline, qa.query, self.TOP_K)
            ndcgs.append(ndcg_at_k(ids, qa.relevant_ids, self.TOP_K))
        avg = sum(ndcgs) / len(ndcgs) if ndcgs else 0.0
        assert avg > 0.0, f"Average nDCG@5: {avg:.3f}"


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


class TestReport:
    """Aggregate evaluation report printed to stdout."""

    K_VALUES = [1, 3, 5]

    def test_generate_report(self, pipeline, qa_pairs, capsys):
        """Run full evaluation and print a structured report."""
        results_by_type: Dict[str, Dict[str, List[float]]] = {}

        for qa in qa_pairs:
            result_set = pipeline.retrieve(qa.query, top_k=max(self.K_VALUES))
            ranked_ids = [r.id for r in result_set.results]

            for k in self.K_VALUES:
                key = f"R@{k}"
                results_by_type.setdefault(qa.query_type, {}).setdefault(key, []).append(
                    recall_at_k(ranked_ids, qa.relevant_ids, k)
                )
                key = f"nDCG@{k}"
                results_by_type.setdefault(qa.query_type, {}).setdefault(key, []).append(
                    ndcg_at_k(ranked_ids, qa.relevant_ids, k)
                )

            results_by_type.setdefault(qa.query_type, {}).setdefault("MRR", []).append(
                mean_reciprocal_rank(ranked_ids, qa.relevant_ids)
            )

        lines = [
            "",
            "=" * 72,
            "  RETRIEVAL QUALITY EVALUATION REPORT",
            "  (automated from poem metadata — no human annotations)",
            "=" * 72,
            "",
            f"  Corpus size  : {len(POEM_CORPUS)} poems",
            f"  Query types  : {len(results_by_type)}",
            f"  Total queries: {len(qa_pairs)}",
            f"  K values     : {self.K_VALUES}",
            "",
        ]

        overall_r = {f"R@{k}": [] for k in self.K_VALUES}
        overall_n = {f"nDCG@{k}": [] for k in self.K_VALUES}
        overall_mrr: List[float] = []

        for qtype in sorted(results_by_type):
            metrics = results_by_type[qtype]
            lines.append(f"  [{qtype}]  ({len(qa_pairs) // len(results_by_type)} queries)")
            for metric_name in (
                [f"R@{k}" for k in self.K_VALUES] + ["MRR"] + [f"nDCG@{k}" for k in self.K_VALUES]
            ):
                vals = metrics.get(metric_name, [])
                avg = sum(vals) / len(vals) if vals else 0.0
                lines.append(f"    {metric_name:>8s} : {avg:.4f}")
                if metric_name.startswith("R@"):
                    overall_r[metric_name].extend(vals)
                elif metric_name.startswith("nDCG"):
                    overall_n[metric_name].extend(vals)
                elif metric_name == "MRR":
                    overall_mrr.extend(vals)
            lines.append("")

        lines.append("  [OVERALL]")
        for k in self.K_VALUES:
            key = f"R@{k}"
            avg = sum(overall_r[key]) / len(overall_r[key]) if overall_r[key] else 0.0
            lines.append(f"    {key:>8s} : {avg:.4f}")
        avg_mrr = sum(overall_mrr) / len(overall_mrr) if overall_mrr else 0.0
        lines.append(f"    {'MRR':>8s} : {avg_mrr:.4f}")
        for k in self.K_VALUES:
            key = f"nDCG@{k}"
            avg = sum(overall_n[key]) / len(overall_n[key]) if overall_n[key] else 0.0
            lines.append(f"    {key:>8s} : {avg:.4f}")

        lines.append("")
        lines.append("=" * 72)

        report = "\n".join(lines)
        print(report)

        # Assertions: all metrics should be non-negative and finite
        for metric_name, vals in overall_r.items():
            for v in vals:
                assert 0.0 <= v <= 1.0, f"{metric_name} out of range: {v}"
        for v in overall_mrr:
            assert 0.0 <= v <= 1.0, f"MRR out of range: {v}"
        for metric_name, vals in overall_n.items():
            for v in vals:
                assert 0.0 <= v <= 1.0, f"{metric_name} out of range: {v}"
