"""Hermes skills: reusable retrieval capabilities exposed to agents."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from openprom.services.hermes.retriever import HermesRetriever, get_hermes_retriever


class HermesSkill(ABC):
    """Base class for a Hermes skill."""

    name: str = ""
    description: str = ""

    @abstractmethod
    def invoke(self, **kwargs: Any) -> Any:
        raise NotImplementedError


class ClassicPoetrySkill(HermesSkill):
    """Retrieve whole classic poems as few-shot examples."""

    name = "retrieve_poems"
    description = (
        "根据主题、体裁或朝代检索古人诗作全文，作为创作的参考范例。"
        "返回诗作标题、作者、朝代与正文。"
    )

    def __init__(self, retriever: Optional[HermesRetriever] = None):
        self.retriever = retriever or get_hermes_retriever()

    def invoke(
        self,
        theme: str,
        form: Optional[str] = None,
        dynasty: Optional[str] = None,
        top_k: int = 3,
    ) -> str:
        poems = self.retriever.retrieve_poems(
            query=theme,
            form=form,
            dynasty=dynasty,
            top_k=top_k,
        )
        if not poems:
            return "未检索到相关的古人诗作。"
        parts = ["【古人诗作参考】"]
        for p in poems:
            meta = p.get("metadata", {})
            header = " ".join(filter(None, [
                meta.get("dynasty"),
                meta.get("author"),
                meta.get("title"),
            ]))
            parts.append(f"《{header}》")
            parts.append(p.get("text", ""))
            parts.append("")
        return "\n".join(parts).strip()


class ImagerySkill(HermesSkill):
    """Retrieve imagery and diction notes from classic poems."""

    name = "retrieve_imagery"
    description = (
        "检索与主题相关的古人诗作，提取其中的意象、用词与炼字技巧，"
        "供创作时借鉴，避免现代白话化。"
    )

    def __init__(self, retriever: Optional[HermesRetriever] = None):
        self.retriever = retriever or get_hermes_retriever()

    def invoke(
        self,
        theme: str,
        form: Optional[str] = None,
        top_k: int = 3,
    ) -> str:
        poems = self.retriever.retrieve_poems(
            query=theme,
            form=form,
            top_k=top_k,
        )
        if not poems:
            return "未检索到相关的意象参考。"
        notes = ["【意象与用词参考】"]
        for p in poems:
            text = p.get("text", "")
            meta = p.get("metadata", {})
            header = " ".join(filter(None, [
                meta.get("dynasty"),
                meta.get("author"),
                meta.get("title"),
            ]))
            if text:
                notes.append(f"- {header or '古人'}：{text.replace(chr(10), ' / ')}")
        return "\n".join(notes)


class LineInspirationSkill(HermesSkill):
    """Retrieve individual lines or couplets for rhyme/imagery inspiration."""

    name = "retrieve_lines"
    description = (
        "检索与主题相关的古人诗句或对联，用于获取韵脚、对仗或意象灵感。"
    )

    def __init__(self, retriever: Optional[HermesRetriever] = None):
        self.retriever = retriever or get_hermes_retriever()

    def invoke(self, theme: str, top_k: int = 5) -> str:
        lines = self.retriever.retrieve_lines(theme, top_k=top_k)
        if not lines:
            return "未检索到相关诗句。"
        parts = ["【诗句参考】"]
        for item in lines:
            text = item.get("text", "")
            meta = item.get("metadata", {})
            header = " ".join(filter(None, [
                meta.get("dynasty"),
                meta.get("author"),
                meta.get("title"),
            ]))
            for ln in text.split("\n"):
                ln = ln.strip()
                if ln:
                    parts.append(f"- {header or '古人'}：{ln}")
        return "\n".join(parts)


def get_hermes_skills(retriever: Optional[HermesRetriever] = None) -> Dict[str, HermesSkill]:
    retriever = retriever or get_hermes_retriever()
    skills: Dict[str, HermesSkill] = {
        ClassicPoetrySkill.name: ClassicPoetrySkill(retriever),
        ImagerySkill.name: ImagerySkill(retriever),
        LineInspirationSkill.name: LineInspirationSkill(retriever),
    }
    return skills
