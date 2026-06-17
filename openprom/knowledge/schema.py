"""Core data structures for the knowledge layer.

RetrievalResult is the "universal currency" between LLM tools, orchestration,
and the knowledge layer. Every retrieval call returns structured results with
provenance, scores, and rule signals — not raw text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Provenance:
    """Where a piece of knowledge came from and how trustworthy it is."""

    source: str
    """Origin identifier: 'tang300', 'quansongci', 'user_feedback', etc."""

    dynasty: Optional[str] = None
    """Dynasty of the poem (唐/宋/…). None if unknown."""

    form: Optional[str] = None
    """Poetic form (五律/七绝/对联/词牌名/…). None if unknown."""

    confidence: float = 0.95
    """Trust level 0..1. Classic curated sets ≥0.8, user feedback=0.5, unreviewed=0.3."""

    version: str = ""
    """Corpus snapshot version (e.g. '2026q2-v1')."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "dynasty": self.dynasty,
            "form": self.form,
            "confidence": self.confidence,
            "version": self.version,
        }


@dataclass(frozen=True)
class RetrievalResult:
    """A single retrieval hit with full metadata and scoring breakdown."""

    id: str
    """Unique identifier (poem id + optional chunk suffix)."""

    content: str
    """Original poem text."""

    annotated: str
    """Semi-structured text with annotations for LLM prompt injection.
    E.g.: '【范诗·五律·王维】《山居秋暝》 明月松间照，清泉石上流。
      意象：明月/松/清泉 | 格律：平起入韵 | 韵部：十一真
      相关度：0.91（语义）+ 0.88（格律匹配）'
    """

    semantic_score: float = 0.0
    """Dense vector similarity score."""

    rerank_score: Optional[float] = None
    """Cross-encoder rerank score. None if rerank not applied."""

    rule_signals: Dict[str, float] = field(default_factory=dict)
    """Deterministic rule-based features: meter_match, rhyme_consistency, form_match."""

    final_score: float = 0.0
    """Fused score after all ranking stages."""

    provenance: Provenance = field(default_factory=lambda: Provenance(source="unknown"))
    """Origin and trust metadata."""

    chunk_type: str = "poem"
    """Chunk granularity: 'poem', 'couplet', 'quatrain', 'line'."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata (title, author, tags, etc.)."""

    def to_prompt_text(self) -> str:
        """Return the annotated text suitable for LLM prompt injection."""
        return self.annotated or self.content

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "annotated": self.annotated,
            "semantic_score": self.semantic_score,
            "rerank_score": self.rerank_score,
            "rule_signals": self.rule_signals,
            "final_score": self.final_score,
            "provenance": self.provenance.to_dict(),
            "chunk_type": self.chunk_type,
            "metadata": self.metadata,
        }


@dataclass
class RetrievalResultSet:
    """A collection of retrieval results with summary stats."""

    results: List[RetrievalResult] = field(default_factory=list)
    query: str = ""
    total_candidates: int = 0
    """How many candidates were considered before final selection."""
    pipeline_stages: List[str] = field(default_factory=list)
    """Which pipeline stages were applied (e.g. ['dense', 'bm25', 'rrf', 'rerank'])."""

    def __len__(self) -> int:
        return len(self.results)

    def __iter__(self):
        return iter(self.results)

    def to_prompt_text(self) -> str:
        """Format all results into a single text block for prompt injection."""
        if not self.results:
            return ""
        parts = []
        for r in self.results:
            parts.append(r.to_prompt_text())
        return "\n\n".join(parts)

    def to_dicts(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self.results]
