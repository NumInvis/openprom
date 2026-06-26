"""Tool JSON Schemas for LLM function calling.

All tools consumed by the generation/completion agents are declared here.
"""

from typing import Any, Dict, Callable
from dataclasses import dataclass


@dataclass
class Tool:
    """A callable tool exposed to the LLM."""

    name: str
    description: str
    parameters: Dict[str, Any]
    func: Callable[..., Any]

    def to_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# Shared parameter fragments
_TEXT_PARAM = {
    "type": "string",
    "description": "待检测的诗词文本。律诗/绝句按行用换行符\\n分隔；对联用\\n分隔上联和下联。",
}

_METER_TYPE_PARAM = {
    "type": "string",
    "enum": ["shi", "ci", "couplet"],
    "description": "格律类型：shi（诗/绝句/律诗）、ci（词牌）、couplet（对联）。",
}


CHECK_METER_SCHEMA = {
    "type": "object",
    "properties": {
        "text": _TEXT_PARAM,
        "meter_type": _METER_TYPE_PARAM,
        "pattern_name": {
            "type": "string",
            "description": "可选：指定诗体/词牌名称，如“七律平起首句入韵”。不指定则自动匹配。",
        },
        "strict": {
            "type": "boolean",
            "description": "是否使用更严格的格律阈值（默认 false）。",
        },
    },
    "required": ["text", "meter_type"],
}

GET_RHYME_CANDIDATES_SCHEMA = {
    "type": "object",
    "properties": {
        "char": {
            "type": "string",
            "description": "需要替换或寻找韵脚的字（单个汉字）。",
            "minLength": 1,
            "maxLength": 1,
        },
        "tone": {
            "type": "string",
            "enum": ["ping", "ze"],
            "description": "需要的声调：ping（平声）或 ze（仄声）。",
        },
        "count": {
            "type": "integer",
            "description": "返回候选字数量（默认 8）。",
            "minimum": 1,
            "maximum": 20,
        },
    },
    "required": ["char", "tone"],
}

EXPLAIN_RULE_SCHEMA = {
    "type": "object",
    "properties": {
        "rule": {
            "type": "string",
            "enum": ["pingze", "duizhang", "rhyme", "sanpingwei", "sanzewei"],
            "description": "需要解释的规则。",
        }
    },
    "required": ["rule"],
}


def build_tools_registry(
    check_meter_func: Callable,
    get_rhyme_candidates_func: Callable,
    explain_rule_func: Callable,
) -> Dict[str, Tool]:
    """Build a name->Tool registry from callables."""
    return {
        "check_meter": Tool(
            name="check_meter",
            description=(
                "检测给定中文诗词文本是否符合指定格律（诗、词、对联）。"
                "返回是否合规、匹配率、具体错误位置以及韵脚建议。"
                "在生成或补全对联/律诗后，必须调用此工具验证，未通过不得交付。"
            ),
            parameters=CHECK_METER_SCHEMA,
            func=check_meter_func,
        ),
        "get_rhyme_candidates": Tool(
            name="get_rhyme_candidates",
            description=(
                "当韵脚或某字的平仄不符合格律时，返回同韵部（平水韵）且声调匹配的候选字。"
                "可用于替换错误位置的字以修正格律。"
            ),
            parameters=GET_RHYME_CANDIDATES_SCHEMA,
            func=get_rhyme_candidates_func,
        ),
        "explain_rule": Tool(
            name="explain_rule",
            description="解释指定的诗词格律规则，帮助模型自我修正。",
            parameters=EXPLAIN_RULE_SCHEMA,
            func=explain_rule_func,
        ),
    }
