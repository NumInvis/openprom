"""Hermes skills exposed as LLM-callable tools."""

from typing import Dict

from openprom.services.hermes.retriever import HermesRetriever, get_hermes_retriever
from openprom.services.hermes.skills import (
    ClassicPoetrySkill,
    ImagerySkill,
    LineInspirationSkill,
)
from openprom.tools.schemas import Tool


_RETRIEVE_POEMS_SCHEMA = {
    "type": "object",
    "properties": {
        "theme": {
            "type": "string",
            "description": "创作主题或关键词，如“春山”“边塞”“离别”。",
        },
        "form": {
            "type": "string",
            "description": "可选：体裁过滤，如“五绝”“七绝”“五律”“七律”或“couplet”。",
        },
        "dynasty": {
            "type": "string",
            "description": "可选：朝代过滤，如“唐”“宋”。",
        },
        "top_k": {
            "type": "integer",
            "description": "返回结果数量（默认 3，最大 10）。",
            "minimum": 1,
            "maximum": 10,
            "default": 3,
        },
    },
    "required": ["theme"],
}

_RETRIEVE_IMAGERY_SCHEMA = {
    "type": "object",
    "properties": {
        "theme": {
            "type": "string",
            "description": "创作主题或关键词。",
        },
        "form": {
            "type": "string",
            "description": "可选：体裁过滤。",
        },
        "top_k": {
            "type": "integer",
            "description": "返回结果数量（默认 3，最大 10）。",
            "minimum": 1,
            "maximum": 10,
            "default": 3,
        },
    },
    "required": ["theme"],
}

_RETRIEVE_LINES_SCHEMA = {
    "type": "object",
    "properties": {
        "theme": {
            "type": "string",
            "description": "创作主题或关键词，用于寻找韵脚、对仗或意象灵感。",
        },
        "top_k": {
            "type": "integer",
            "description": "返回结果数量（默认 5，最大 10）。",
            "minimum": 1,
            "maximum": 10,
            "default": 5,
        },
    },
    "required": ["theme"],
}


def build_hermes_tools(retriever: HermesRetriever = None) -> Dict[str, Tool]:
    retriever = retriever or get_hermes_retriever()
    classic = ClassicPoetrySkill(retriever)
    imagery = ImagerySkill(retriever)
    lines = LineInspirationSkill(retriever)

    return {
        "retrieve_poems": Tool(
            name="retrieve_poems",
            description=(
                "检索与主题相关的古人诗作全文，作为创作的参考范例。"
                "在构思阶段调用，可学习其意象、用词与结构。"
            ),
            parameters=_RETRIEVE_POEMS_SCHEMA,
            func=lambda **kwargs: classic.invoke(**kwargs),
        ),
        "retrieve_imagery": Tool(
            name="retrieve_imagery",
            description=(
                "检索并提取古人诗作中的意象、炼字与典雅表达，用于避免现代白话化，提高诗味。"
            ),
            parameters=_RETRIEVE_IMAGERY_SCHEMA,
            func=lambda **kwargs: imagery.invoke(**kwargs),
        ),
        "retrieve_lines": Tool(
            name="retrieve_lines",
            description=("检索与主题相关的古人诗句或对联，用于获取韵脚、对仗或意象灵感。"),
            parameters=_RETRIEVE_LINES_SCHEMA,
            func=lambda **kwargs: lines.invoke(**kwargs),
        ),
    }
