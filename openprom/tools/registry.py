"""Tool registry for OpenPROM agents."""

from typing import Dict

from openprom.tools.schemas import Tool, build_tools_registry
from openprom.services import meter_tool
from openprom.services.hermes.tools import build_hermes_tools


def get_tool_registry() -> Dict[str, Tool]:
    """Return the default tool registry used by generation agents."""
    tools = build_tools_registry(
        check_meter_func=meter_tool.check_meter,
        get_rhyme_candidates_func=meter_tool.get_rhyme_candidates,
        explain_rule_func=meter_tool.explain_rule,
    )
    tools.update(build_hermes_tools())
    return tools
