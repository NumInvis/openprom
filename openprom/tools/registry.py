"""Tool registry for OpenPROM agents.

Only 4 tools — each is a Swiss-army knife:
1. check_meter (mandatory) — 格律检测+韵脚候选+声韵查询+格律谱+规则解释
2. retrieve_poetry (optional) — 检索几十万首古诗词
3. web_search (optional) — 搜索整个互联网
4. self_critique (optional) — 自评反思框架
"""

from typing import Dict

from openprom.tools.schemas import Tool
from openprom.tools.poetry_schemas import (
    CHECK_METER_SCHEMA,
    RETRIEVE_POETRY_SCHEMA,
    SELF_CRITIQUE_SCHEMA,
    WEB_SEARCH_SCHEMA,
)
from openprom.tools.poetry_tools import (
    check_meter_unified,
    retrieve_poetry,
    self_critique,
    web_search,
)


def get_tool_registry() -> Dict[str, Tool]:
    """Return the 4-tool registry used by all generation agents."""

    tools: Dict[str, Tool] = {}

    # 1. check_meter — the ONLY mandatory tool
    tools["check_meter"] = Tool(
        name="check_meter",
        description=(
            "格律工具集（唯一必须调用的工具）。通过 action 参数选择操作：\n"
            "  action=check — 格律检测，返回是否合规、匹配率、错误位置、韵脚建议\n"
            "  action=rhyme_candidates — 获取同韵部候选字（需要 char + tone）\n"
            "  action=char_phonetics — 查汉字在平水韵中的声调和韵部（需要 char）\n"
            "  action=meter_template — 查诗体格律谱（需要 form，如\"七律\"）\n"
            "  action=explain_rule — 解释格律规则（需要 rule）\n"
            "最终交付前必须用 action=check 确保格律合规。"
        ),
        parameters=CHECK_METER_SCHEMA,
        func=check_meter_unified,
    )

    # 2. retrieve_poetry — optional
    tools["retrieve_poetry"] = Tool(
        name="retrieve_poetry",
        description=(
            "检索古诗词库（几十万首）。通过 mode 参数选择检索方式：\n"
            "  mode=poems — 检索与主题相关的古人诗作全文\n"
            "  mode=imagery — 提取古人诗作中的意象与典雅表达\n"
            "  mode=lines — 检索相关诗句，用于韵脚/对仗/意象灵感\n"
            "非必须——仅在你认为需要汲取前人精华时调用。"
        ),
        parameters=RETRIEVE_POETRY_SCHEMA,
        func=retrieve_poetry,
    )

    # 3. web_search — optional
    tools["web_search"] = Tool(
        name="web_search",
        description=(
            "搜索整个互联网获取任意知识：典故出处、历史背景、地理考据、"
            "植物百科、字词源流等。非必须——遇到不确定的知识点时可调用。"
        ),
        parameters=WEB_SEARCH_SCHEMA,
        func=web_search,
    )

    # 4. self_critique — optional
    tools["self_critique"] = Tool(
        name="self_critique",
        description=(
            "自评反思：返回结构化的评价框架（意象/炼字/章法/情致/独创/技巧六维度），"
            "引导你对自己的作品进行深度审视和修正。"
            "非必须，但推荐在初稿完成后调用以自我提升。"
        ),
        parameters=SELF_CRITIQUE_SCHEMA,
        func=self_critique,
    )

    return tools
