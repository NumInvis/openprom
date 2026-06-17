"""Knowledge layer skills: domain-specific retrieval capabilities.

These skills return structured RetrievalResult objects instead of raw text,
enabling LLMs to "reason by attributes" rather than just "read a paragraph".

Upgraded from services/hermes/skills.py with:
- Structured RetrievalResult output
- Semi-structured annotated text for prompt injection
- Rule signal integration
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from openprom.knowledge.retrieval.pipeline import RetrievalPipeline, get_retrieval_pipeline
from openprom.knowledge.schema import RetrievalResultSet

logger = logging.getLogger(__name__)


class KnowledgeSkill(ABC):
    """Base class for a knowledge layer skill."""

    name: str = ""
    description: str = ""

    @abstractmethod
    def invoke(self, **kwargs: Any) -> RetrievalResultSet:
        """Execute the skill and return structured results."""
        raise NotImplementedError


class ClassicPoetrySkill(KnowledgeSkill):
    """Retrieve whole classic poems as few-shot examples."""

    name = "retrieve_poems"
    description = (
        "根据主题、体裁或朝代检索古人诗作全文，作为创作的参考范例。"
        "返回诗作标题、作者、朝代与正文，带格律与韵部标注。"
    )

    def __init__(self, pipeline: Optional[RetrievalPipeline] = None):
        self.pipeline = pipeline or get_retrieval_pipeline()

    def invoke(
        self,
        theme: str,
        form: Optional[str] = None,
        dynasty: Optional[str] = None,
        top_k: int = 3,
    ) -> RetrievalResultSet:
        filters: Dict[str, Any] = {}
        if form:
            filters["form"] = form
        if dynasty:
            filters["dynasty"] = dynasty
        return self.pipeline.retrieve(
            query=theme,
            top_k=top_k,
            top_k_recall=top_k * 5,
            filters=filters if filters else None,
            target_form=form,
        )


class ImagerySkill(KnowledgeSkill):
    """Retrieve imagery and diction notes from classic poems."""

    name = "retrieve_imagery"
    description = (
        "检索与主题相关的古人诗作，提取其中的意象、用词与炼字技巧，"
        "供创作时借鉴，避免现代白话化。"
    )

    def __init__(self, pipeline: Optional[RetrievalPipeline] = None):
        self.pipeline = pipeline or get_retrieval_pipeline()

    def invoke(
        self,
        theme: str,
        form: Optional[str] = None,
        top_k: int = 3,
    ) -> RetrievalResultSet:
        filters = {"form": form} if form else None
        return self.pipeline.retrieve(
            query=theme,
            top_k=top_k,
            top_k_recall=top_k * 5,
            filters=filters,
            target_form=form,
        )


class LineInspirationSkill(KnowledgeSkill):
    """Retrieve individual lines or couplets for inspiration."""

    name = "retrieve_lines"
    description = (
        "检索与主题相关的古人诗句或对联，用于获取韵脚、对仗或意象灵感。"
    )

    def __init__(self, pipeline: Optional[RetrievalPipeline] = None):
        self.pipeline = pipeline or get_retrieval_pipeline()

    def invoke(self, theme: str, top_k: int = 5) -> RetrievalResultSet:
        return self.pipeline.retrieve(
            query=theme,
            top_k=top_k,
            top_k_recall=top_k * 5,
        )


class RhymeContextSkill(KnowledgeSkill):
    """Retrieve classic ending lines in the same rhyme category."""

    name = "retrieve_rhyme_context"
    description = (
        "检索同韵部的经典收尾句与韵律分析，帮助选择合适的韵脚。"
    )

    def __init__(self, pipeline: Optional[RetrievalPipeline] = None):
        self.pipeline = pipeline or get_retrieval_pipeline()

    def invoke(
        self,
        rhyme_char: str,
        rhyme_category: Optional[str] = None,
        top_k: int = 3,
    ) -> RetrievalResultSet:
        query = f"韵脚 {rhyme_char}"
        if rhyme_category:
            query += f" {rhyme_category}韵"
        return self.pipeline.retrieve(
            query=query,
            top_k=top_k,
            top_k_recall=top_k * 5,
            target_rhyme_category=rhyme_category,
        )


class FormExampleSkill(KnowledgeSkill):
    """Retrieve compliant poems of a specific form with meter annotations."""

    name = "retrieve_form_examples"
    description = (
        "检索指定格律体裁的合规范诗，并附格律标注，帮助理解该体裁的规则。"
    )

    def __init__(self, pipeline: Optional[RetrievalPipeline] = None):
        self.pipeline = pipeline or get_retrieval_pipeline()

    def invoke(
        self,
        form: str,
        theme: Optional[str] = None,
        top_k: int = 3,
    ) -> RetrievalResultSet:
        query = theme or f"{form}格律范例"
        return self.pipeline.retrieve(
            query=query,
            top_k=top_k,
            top_k_recall=top_k * 5,
            filters={"form": form},
            target_form=form,
        )


def get_knowledge_skills(
    pipeline: Optional[RetrievalPipeline] = None,
) -> Dict[str, KnowledgeSkill]:
    """Get all available knowledge skills."""
    pipeline = pipeline or get_retrieval_pipeline()
    return {
        ClassicPoetrySkill.name: ClassicPoetrySkill(pipeline),
        ImagerySkill.name: ImagerySkill(pipeline),
        LineInspirationSkill.name: LineInspirationSkill(pipeline),
        RhymeContextSkill.name: RhymeContextSkill(pipeline),
        FormExampleSkill.name: FormExampleSkill(pipeline),
    }
