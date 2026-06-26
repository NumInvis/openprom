"""Unified poetry tool schemas.

Only 4 tools exist — each is a Swiss-army knife with an action/mode
parameter rather than a constellation of tiny one-shot tools.
"""

from typing import Any, Dict

# ---------------------------------------------------------------------------
# 1. check_meter — the ONLY mandatory tool.  All 格律-related operations
#    are unified here via an ``action`` parameter.
# ---------------------------------------------------------------------------

CHECK_METER_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "check",
                "rhyme_candidates",
                "char_phonetics",
                "meter_template",
                "explain_rule",
            ],
            "description": (
                "执行的操作：\n"
                "  check — 格律检测（默认）\n"
                "  rhyme_candidates — 获取同韵部候选字\n"
                "  char_phonetics — 查汉字在平水韵中的声韵\n"
                "  meter_template — 查诗体格律谱\n"
                "  explain_rule — 解释格律规则"
            ),
            "default": "check",
        },
        # action=check
        "text": {
            "type": "string",
            "description": "待检测文本（action=check 时必填）。律诗按行用\\n分隔，对联用\\n分隔上下联。",
        },
        "meter_type": {
            "type": "string",
            "enum": ["shi", "ci", "couplet"],
            "description": "格律类型（action=check 时必填）。",
        },
        "pattern_name": {
            "type": "string",
            "description": "可选：指定格律模板名（action=check 时可选）。",
        },
        "strict": {
            "type": "boolean",
            "description": "是否严格模式（action=check 时可选，默认 false）。",
            "default": False,
        },
        # action=rhyme_candidates
        "char": {
            "type": "string",
            "description": "单个汉字（action=rhyme_candidates 或 char_phonetics 时必填）。",
            "minLength": 1,
            "maxLength": 1,
        },
        "tone": {
            "type": "string",
            "enum": ["ping", "ze"],
            "description": "需要的声调（action=rhyme_candidates 时必填）。",
        },
        "count": {
            "type": "integer",
            "description": "返回候选数量（action=rhyme_candidates 时可选，默认 8）。",
            "minimum": 1,
            "maximum": 20,
            "default": 8,
        },
        # action=char_phonetics
        "book": {
            "type": "string",
            "description": '韵书名（action=char_phonetics 时可选，默认"平水韵"）。',
            "default": "平水韵",
        },
        # action=meter_template
        "form": {
            "type": "string",
            "description": '诗体名（action=meter_template 时必填），如"五绝""七律"。',
        },
        "tone_pattern": {
            "type": "string",
            "enum": ["ping", "ze"],
            "description": "可选：平起(ping)或仄起(ze)（action=meter_template 时可选）。",
        },
        # action=explain_rule
        "rule": {
            "type": "string",
            "enum": ["pingze", "duizhang", "rhyme", "sanpingwei", "sanzewei"],
            "description": "规则名（action=explain_rule 时必填）。",
        },
    },
    "required": ["action"],
}


# ---------------------------------------------------------------------------
# 2. retrieve_poetry —检索古诗词库（几十万首）。全部检索合并为一个工具。
# ---------------------------------------------------------------------------

RETRIEVE_POETRY_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "mode": {
            "type": "string",
            "enum": ["poems", "imagery", "lines"],
            "description": (
                "检索模式：\n"
                "  poems — 检索与主题相关的古人诗作全文，作为创作参考\n"
                "  imagery — 检索并提取古人诗作中的意象与典雅表达\n"
                "  lines — 检索与主题相关的古人诗句，用于韵脚/对仗/意象灵感"
            ),
            "default": "poems",
        },
        "theme": {
            "type": "string",
            "description": '创作主题或关键词，如"春山""边塞""离别"。',
        },
        "form": {
            "type": "string",
            "description": '可选：体裁过滤，如"五绝""七律"或"couplet"。',
        },
        "dynasty": {
            "type": "string",
            "description": '可选：朝代过滤，如"唐""宋"。',
        },
        "top_k": {
            "type": "integer",
            "description": "返回结果数（默认 3，最大 10）。",
            "minimum": 1,
            "maximum": 10,
            "default": 3,
        },
    },
    "required": ["theme"],
}


# ---------------------------------------------------------------------------
# 3. web_search — 搜索整个互联网获取任意知识。
# ---------------------------------------------------------------------------

WEB_SEARCH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": (
                "搜索查询。可用于查证典故出处、历史背景、植物百科、地理考据、字词源流等任意知识。"
            ),
        },
        "num_results": {
            "type": "integer",
            "description": "返回结果数量（默认 5）。",
            "minimum": 1,
            "maximum": 10,
            "default": 5,
        },
    },
    "required": ["query"],
}


# ---------------------------------------------------------------------------
# 4. self_critique — 自评反思框架。
# ---------------------------------------------------------------------------

SELF_CRITIQUE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "work": {
            "type": "string",
            "description": "待自评的作品全文。",
        },
        "form": {
            "type": "string",
            "description": "可选：作品体裁（五律/七律/对联等），帮助针对性评价。",
        },
        "dimensions": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["imagery", "diction", "structure", "emotion", "originality", "technique"],
            },
            "description": "可选：指定评价维度。默认全维度。",
        },
    },
    "required": ["work"],
}
