"""Hermes knowledge & skill layer.

Hermes provides retrieval-augmented classical poetry knowledge to the OpenPROM
generation and scoring agents. It wraps a vector store with hybrid keyword
search, chunking, and a small registry of LLM-callable skills.
"""

from openprom.services.hermes.retriever import HermesRetriever, get_hermes_retriever
from openprom.services.hermes.skills import (
    ClassicPoetrySkill,
    ImagerySkill,
    LineInspirationSkill,
    get_hermes_skills,
)
from openprom.services.hermes.tools import build_hermes_tools
from openprom.services.hermes.indexer import PoetryIndexer

__all__ = [
    "HermesRetriever",
    "get_hermes_retriever",
    "ClassicPoetrySkill",
    "ImagerySkill",
    "LineInspirationSkill",
    "get_hermes_skills",
    "build_hermes_tools",
    "PoetryIndexer",
]
