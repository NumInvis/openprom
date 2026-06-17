"""Poetry knowledge retrieval service (the Hermes-style memory/skill layer).

Retrieves ancient poems by theme, form, or line similarity and formats them
for injection into LLM generation prompts. This module is kept as a thin
adapter over openprom.services.hermes for backward compatibility.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PoetryKnowledge:
    """Retrieval-augmented poetry knowledge."""

    def __init__(self, retriever=None):
        if retriever is None:
            from openprom.services.hermes.retriever import get_hermes_retriever
            retriever = get_hermes_retriever()
        self.retriever = retriever

    def retrieve_examples(
        self,
        theme: str,
        form: Optional[str] = None,
        dynasty: Optional[str] = None,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Retrieve similar ancient poems as few-shot examples."""
        try:
            if self.retriever.store.count() == 0:
                logger.warning("Vector store is empty; no RAG examples available")
                return []
        except Exception as e:
            logger.warning(f"Vector store not ready: {e}")
            return []

        return self.retriever.retrieve_poems(
            query=theme,
            form=form,
            dynasty=dynasty,
            top_k=top_k,
        )

    def retrieve_lines(
        self,
        theme: str,
        position: Optional[str] = None,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Retrieve individual lines or couplets for imagery/rhyme inspiration."""
        return self.retriever.retrieve_lines(theme, top_k=top_k)

    def format_context(self, poems: List[Dict[str, Any]]) -> str:
        """Format retrieved poems for prompt injection."""
        if not poems:
            return ""
        parts = ["【古人诗作参考】"]
        for p in poems:
            meta = p.get("metadata", {})
            title = meta.get("title", "")
            author = meta.get("author", "")
            dynasty = meta.get("dynasty", "")
            header = " ".join(filter(None, [dynasty, author, title]))
            parts.append(f"《{header}》")
            parts.append(p.get("text", ""))
            parts.append("")
        return "\n".join(parts)

    def format_imagery(self, poems: List[Dict[str, Any]]) -> str:
        """Extract imagery and diction notes from retrieved poems."""
        if not poems:
            return ""
        notes = []
        for p in poems:
            text = p.get("text", "")
            meta = p.get("metadata", {})
            header = " ".join(filter(None, [meta.get("dynasty"), meta.get("author"), meta.get("title")]))
            if text:
                notes.append(f"- {header or '古人'}：{text.replace(chr(10), ' / ')}")
        return "\n".join(["【意象与用词参考】"] + notes)


def get_poetry_knowledge() -> PoetryKnowledge:
    return PoetryKnowledge()
