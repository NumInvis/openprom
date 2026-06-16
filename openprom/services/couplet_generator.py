"""Couplet generation and completion service with RAG augmentation.

Drives an LLM through a tool-calling loop so that every delivered couplet has
passed the meter check. If the meter gradient cannot descend, rhyme candidates
are injected as tool results.
"""

import logging
from typing import Any, Dict, Iterable, Optional

from openprom.infrastructure.config.settings import get_settings
from openprom.services.llm_client import LLMClient, get_llm_client
from openprom.services.rag.poetry_knowledge import get_poetry_knowledge
from openprom.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)

COUPLET_SYSTEM_PROMPT = """你是一位精通中国古典诗词对联的 AI 助手。

任务：根据用户输入生成或补全一副对联。

规则：
1. 对联分为上联和下联，用换行符分隔，每联 5 或 7 字（用户指定时依用户）。
2. 上下联字数必须相等。
3. 必须满足：二四六位置平仄相对；上联尾字为仄声，下联尾字为平声；避免三平尾、三仄尾。
4. 上下联需语义相关、对仗工整，并学习古人诗作中的意象、用词与含蓄表达，避免口水化、现代白话化。
5. 生成前可调用 retrieve_poems 或 retrieve_imagery 获取古人诗作参考，以提升意象与用词典雅度。
6. 生成后必须调用 check_meter 工具进行格律检测；未通过则根据工具反馈修正。
7. 如果某字无法通过自身知识修正，必须调用 get_rhyme_candidates 获取候选字。
8. 最终交付的内容必须是 check_meter 返回 is_compliant=true 的结果。

请用中文思考并输出最终对联。"""


def _build_prompt(
    mode: str,
    prompt: str,
    length: Optional[int] = None,
) -> str:
    settings = get_settings()
    length = length or settings.generation.couplet_default_length

    if mode == "generate":
        base = f"请根据主题/提示“{prompt}”创作一副 {length} 字对联。"
    else:  # complete
        base = (
            f"请补全下联，使得上下联组成一副工整的 {length} 字对联。"
            f"用户输入：{prompt}"
        )

    base += (
        f"\n要求：\n"
        f"- 每联 {length} 字\n"
        f"- 借鉴古人诗作的意象、对仗与用词，力求典雅含蓄\n"
        f"- 先输出候选对联，然后调用 check_meter 检测\n"
        f"- 未通过检测则修正，最多尝试 {settings.generation.couplet_max_revision_rounds} 轮\n"
        f"- 如韵脚无法下降，调用 get_rhyme_candidates 获取候选韵字\n"
    )
    return base


def _normalize_result(content: str) -> str:
    """Extract the final couplet lines from LLM content."""
    import json
    import re

    text = content

    # 0. If the LLM returned a JSON tool result, extract the poem text first.
    stripped = content.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and "text" in data and isinstance(data["text"], str):
                text = data["text"]
        except json.JSONDecodeError:
            pass

    # 1. Try explicit markers
    upper = None
    lower = None
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("```") or line.startswith("|"):
            continue
        if "上联" in line and "下联" in line:
            parts = re.split(r"下联[：:]", line)
            if len(parts) == 2:
                upper = re.sub(r".*上联[：:]", "", parts[0]).strip(" *>")
                lower = parts[1].strip(" *>")
        elif re.match(r"^[\*\s]*上联[：:]", line):
            upper = re.sub(r"^[\*\s]*上联[：:]\s*", "", line).strip(" *>")
        elif re.match(r"^[\*\s]*下联[：:]", line):
            lower = re.sub(r"^[\*\s]*下联[：:]\s*", "", line).strip(" *>")

    if upper and lower:
        return f"{upper}\n{lower}"

    # 2. Heuristic: last two lines of equal length that are mostly Chinese
    chinese_lines = []
    for line in text.split("\n"):
        line = line.strip().lstrip(">*•- ")
        if not line or line.startswith(("```", "#", "|", "【", "《", "-", "*")):
            continue
        if len(line) <= 12 and len(re.findall(r"[\u4e00-\u9fff]", line)) >= len(line) * 0.5:
            chinese_lines.append(line)

    if len(chinese_lines) >= 2:
        # prefer last two of equal length
        for i in range(len(chinese_lines) - 1, 0, -1):
            if len(chinese_lines[i]) == len(chinese_lines[i - 1]) and len(chinese_lines[i]) >= 4:
                return f"{chinese_lines[i-1]}\n{chinese_lines[i]}"
        return f"{chinese_lines[-2]}\n{chinese_lines[-1]}"

    return text.strip()[-200:]


class CoupletGenerator:
    """Agent for couplet generation and completion."""

    def __init__(self, client: Optional[LLMClient] = None):
        self._client = client or get_llm_client()
        self._tools = list(get_tool_registry().values())
        self._settings = get_settings()
        self._knowledge = get_poetry_knowledge()

    def _build_augmented_prompt(
        self,
        mode: str,
        prompt: str,
        length: Optional[int] = None,
    ) -> str:
        base = _build_prompt(mode, prompt, length)
        if not self._settings.rag.enabled:
            return base

        try:
            examples = self._knowledge.retrieve_examples(
                theme=prompt,
                form=None,
                top_k=self._settings.rag.retrieve_top_k,
            )
            if examples:
                context = self._knowledge.format_imagery(examples)
                base = f"{context}\n\n{base}\n请以上述古人诗作的意象与用词为参考，但不要直接抄袭原句。"
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")
        return base

    def generate(
        self,
        prompt: str,
        length: Optional[int] = None,
        max_rounds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate a couplet from a theme/prompt."""
        prompt_text = self._build_augmented_prompt("generate", prompt, length)
        max_rounds = max_rounds or self._settings.generation.couplet_max_revision_rounds
        result = self._client.chat_with_tools(
            prompt=prompt_text,
            tools=self._tools,
            system_prompt=COUPLET_SYSTEM_PROMPT,
            max_rounds=max_rounds,
        )
        content = _normalize_result(result.get("content", ""))
        return {"couplet": content, "raw_content": result.get("content", ""), "messages": result.get("messages", [])}

    def complete(
        self,
        prompt: str,
        length: Optional[int] = None,
        max_rounds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Complete a couplet from a partial input."""
        prompt_text = self._build_augmented_prompt("complete", prompt, length)
        max_rounds = max_rounds or self._settings.generation.couplet_max_revision_rounds
        result = self._client.chat_with_tools(
            prompt=prompt_text,
            tools=self._tools,
            system_prompt=COUPLET_SYSTEM_PROMPT,
            max_rounds=max_rounds,
        )
        content = _normalize_result(result.get("content", ""))
        return {"couplet": content, "raw_content": result.get("content", ""), "messages": result.get("messages", [])}

    def generate_stream(
        self,
        prompt: str,
        length: Optional[int] = None,
        max_rounds: Optional[int] = None,
    ) -> Iterable[str]:
        """Yield SSE data lines for generation progress."""
        prompt_text = self._build_augmented_prompt("generate", prompt, length)
        max_rounds = max_rounds or self._settings.generation.couplet_max_revision_rounds
        yield from self._client.stream_progress(
            prompt=prompt_text,
            tools=self._tools,
            system_prompt=COUPLET_SYSTEM_PROMPT,
            max_rounds=max_rounds,
        )

    def complete_stream(
        self,
        prompt: str,
        length: Optional[int] = None,
        max_rounds: Optional[int] = None,
    ) -> Iterable[str]:
        """Yield SSE data lines for completion progress."""
        prompt_text = self._build_augmented_prompt("complete", prompt, length)
        max_rounds = max_rounds or self._settings.generation.couplet_max_revision_rounds
        yield from self._client.stream_progress(
            prompt=prompt_text,
            tools=self._tools,
            system_prompt=COUPLET_SYSTEM_PROMPT,
            max_rounds=max_rounds,
        )


def generate_couplet(prompt: str, length: Optional[int] = None) -> Dict[str, Any]:
    return CoupletGenerator().generate(prompt, length)


def complete_couplet(prompt: str, length: Optional[int] = None) -> Dict[str, Any]:
    return CoupletGenerator().complete(prompt, length)
