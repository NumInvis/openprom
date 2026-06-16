"""Regulated verse (lüshi / jueju) generation and completion service with RAG.

Uses the meter tool in an LLM tool loop to ensure every delivered poem passes
the formal meter check. Retrieves ancient poems as few-shot examples.
"""

import logging
from typing import Any, Dict, Iterable, Optional

from openprom.infrastructure.config.settings import get_settings
from openprom.services.llm_client import LLMClient, get_llm_client
from openprom.services.rag.poetry_knowledge import get_poetry_knowledge
from openprom.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)

SHI_SYSTEM_PROMPT = """你是一位精通中国古典律诗、绝句的 AI 助手。

任务：根据用户输入生成或补全一首律诗或绝句。

规则：
1. 律诗为 8 句，绝句为 4 句；每句 5 字（五言）或 7 字（七言）。
2. 偶数句（二、四、六、八句）必须押韵，通常押平声韵；首句可入韵也可不入韵。
3. 必须符合指定诗体的平仄格式（平起/仄起、入韵/不入韵）。
4. 中间两联（律诗的三四句、五六句）需对仗。
5. 语言要典雅含蓄，学习古人诗作中的意象、用典与炼字，避免现代白话与口水化表达。
6. 生成前可调用 retrieve_poems 或 retrieve_imagery 获取古人诗作参考；需要韵脚或对仗灵感时可调用 retrieve_lines。
7. 生成后必须调用 check_meter 工具进行格律检测；未通过则根据工具反馈修正。
8. 如果韵脚无法下降，调用 get_rhyme_candidates 获取同韵部候选字。
9. 最终交付的内容必须是 check_meter 返回 is_compliant=true 的结果。

请用中文思考并输出最终诗作。"""

_FORM_TO_LINES = {
    "五绝": 4,
    "七绝": 4,
    "五律": 8,
    "七律": 8,
}

_FORM_TO_CHARS = {
    "五绝": 5,
    "七绝": 7,
    "五律": 5,
    "七律": 7,
}


def _resolve_form(form: Optional[str]) -> str:
    settings = get_settings()
    return form or settings.generation.shi_default_form


def _build_prompt(
    mode: str,
    prompt: str,
    form: Optional[str] = None,
    tone_preference: Optional[str] = None,
) -> str:
    settings = get_settings()
    form = _resolve_form(form)
    lines = _FORM_TO_LINES.get(form, 8)
    chars = _FORM_TO_CHARS.get(form, 7)

    tone_part = ""
    if tone_preference:
        tone_part = f"，采用{tone_preference}格式"

    if mode == "generate":
        base = f"请根据主题/提示“{prompt}”创作一首 {form}（{lines}句，每句{chars}字{tone_part}）。"
    else:
        base = (
            f"请补全/续作一首 {form}（{lines}句，每句{chars}字{tone_part}），"
            f"用户已给出部分内容：{prompt}"
        )

    base += (
        f"\n要求：\n"
        f"- 共 {lines} 句，每句 {chars} 字\n"
        f"- 借鉴古人诗作的意象、对仗与炼字，力求典雅含蓄\n"
        f"- 先输出候选诗作，然后调用 check_meter(text=..., meter_type=\"shi\") 检测\n"
        f"- 未通过检测则修正，最多尝试 {settings.generation.shi_max_revision_rounds} 轮\n"
        f"- 如韵脚无法下降，调用 get_rhyme_candidates 获取候选韵字\n"
    )
    return base


def _normalize_result(content: str) -> str:
    """Extract poem lines from LLM output."""
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

    lines = [line.strip().lstrip(">*•- ") for line in text.split("\n") if line.strip()]

    # Collect candidate Chinese lines (5 or 7 chars ideally)
    candidates = []
    for line in lines:
        if line.startswith(("```", "#", "|", "【", "《", "-", "*", "格律", "赏析", ">")):
            continue
        chars_only = re.sub(r"[^\u4e00-\u9fff]", "", line)
        if len(chars_only) in (5, 7) and len(chars_only) >= len(line) * 0.5:
            candidates.append(chars_only)

    if len(candidates) >= 4:
        # Find the longest consecutive run of equal-length lines
        best_start, best_len = 0, 0
        i = 0
        while i < len(candidates):
            length = len(candidates[i])
            j = i + 1
            while j < len(candidates) and len(candidates[j]) == length:
                j += 1
            run_len = j - i
            if run_len > best_len:
                best_len = run_len
                best_start = i
            i = j
        if best_len >= 4:
            poem = candidates[best_start:best_start + best_len]
            if best_len in (4, 8):
                return "\n".join(poem)
            return "\n".join(poem[:8])

    # Fallback
    cleaned = []
    for line in lines:
        if line.startswith(("```", "#", "|")):
            continue
        cleaned.append(line)
    return "\n".join(cleaned[-16:])


class ShiGenerator:
    """Agent for regulated-verse generation and completion."""

    def __init__(self, client: Optional[LLMClient] = None):
        self._client = client or get_llm_client()
        self._tools = list(get_tool_registry().values())
        self._settings = get_settings()
        self._knowledge = get_poetry_knowledge()

    def _build_augmented_prompt(
        self,
        mode: str,
        prompt: str,
        form: Optional[str] = None,
        tone_preference: Optional[str] = None,
    ) -> str:
        base = _build_prompt(mode, prompt, form, tone_preference)
        if not self._settings.rag.enabled:
            return base

        try:
            resolved_form = _resolve_form(form)
            examples = self._knowledge.retrieve_examples(
                theme=prompt,
                form=resolved_form if self._settings.rag.filter_by_form else None,
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
        form: Optional[str] = None,
        tone_preference: Optional[str] = None,
        max_rounds: Optional[int] = None,
    ) -> Dict[str, Any]:
        prompt_text = self._build_augmented_prompt("generate", prompt, form, tone_preference)
        max_rounds = max_rounds or self._settings.generation.shi_max_revision_rounds
        result = self._client.chat_with_tools(
            prompt=prompt_text,
            tools=self._tools,
            system_prompt=SHI_SYSTEM_PROMPT,
            max_rounds=max_rounds,
        )
        content = _normalize_result(result.get("content", ""))
        return {"poem": content, "raw_content": result.get("content", ""), "messages": result.get("messages", [])}

    def complete(
        self,
        prompt: str,
        form: Optional[str] = None,
        tone_preference: Optional[str] = None,
        max_rounds: Optional[int] = None,
    ) -> Dict[str, Any]:
        prompt_text = self._build_augmented_prompt("complete", prompt, form, tone_preference)
        max_rounds = max_rounds or self._settings.generation.shi_max_revision_rounds
        result = self._client.chat_with_tools(
            prompt=prompt_text,
            tools=self._tools,
            system_prompt=SHI_SYSTEM_PROMPT,
            max_rounds=max_rounds,
        )
        content = _normalize_result(result.get("content", ""))
        return {"poem": content, "raw_content": result.get("content", ""), "messages": result.get("messages", [])}

    def generate_stream(
        self,
        prompt: str,
        form: Optional[str] = None,
        tone_preference: Optional[str] = None,
        max_rounds: Optional[int] = None,
    ) -> Iterable[str]:
        prompt_text = self._build_augmented_prompt("generate", prompt, form, tone_preference)
        max_rounds = max_rounds or self._settings.generation.shi_max_revision_rounds
        yield from self._client.stream_progress(
            prompt=prompt_text,
            tools=self._tools,
            system_prompt=SHI_SYSTEM_PROMPT,
            max_rounds=max_rounds,
        )

    def complete_stream(
        self,
        prompt: str,
        form: Optional[str] = None,
        tone_preference: Optional[str] = None,
        max_rounds: Optional[int] = None,
    ) -> Iterable[str]:
        prompt_text = self._build_augmented_prompt("complete", prompt, form, tone_preference)
        max_rounds = max_rounds or self._settings.generation.shi_max_revision_rounds
        yield from self._client.stream_progress(
            prompt=prompt_text,
            tools=self._tools,
            system_prompt=SHI_SYSTEM_PROMPT,
            max_rounds=max_rounds,
        )


def generate_shi(prompt: str, form: Optional[str] = None, tone_preference: Optional[str] = None) -> Dict[str, Any]:
    return ShiGenerator().generate(prompt, form, tone_preference)


def complete_shi(prompt: str, form: Optional[str] = None, tone_preference: Optional[str] = None) -> Dict[str, Any]:
    return ShiGenerator().complete(prompt, form, tone_preference)
