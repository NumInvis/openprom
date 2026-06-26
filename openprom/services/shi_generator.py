"""Regulated verse generation — 3-phase architecture.

Phase 1 (Inspire)  — LLM gathers inspiration via tools.
Phase 2 (Create)   — Single LLM call, high temperature, meter context injected.
Phase 3 (Refine)   — check_meter + targeted fix, max 2 rounds.

Streaming paths still use LLMClient.stream_progress directly.
"""

import logging
import time
import uuid
from typing import Any, Dict, Iterable, Optional

from openprom.infrastructure.config.settings import get_settings
from openprom.services.llm_client import LLMClient, get_llm_client
from openprom.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)

_FORM_TO_LINES = {"五绝": 4, "七绝": 4, "五律": 8, "七律": 8}
_FORM_TO_CHARS = {"五绝": 5, "七绝": 7, "五律": 5, "七律": 7}


# ---------------------------------------------------------------------------
# System prompts — minimal
# ---------------------------------------------------------------------------

_INSPIRE_PROMPT = (
    "你是诗歌创作助手。帮助诗人搜集灵感。\n"
    "调用 retrieve_poetry 检索古人诗作，或 web_search 搜索知识。\n"
    "也可以直接跳过。准备好后，用3-5句话总结创作方向和可用的意象/典故。"
)

_CREATE_PROMPT = (
    "你是当代最顶尖的诗人，深谙古典律诗绝句的精髓。\n"
    "先有感受，再求形式；先有真意，再求工稳。\n"
    "直接输出诗句，每句一行，不要任何解释、标题、赏析。"
)

_REFINE_PROMPT = (
    "精准修改以下诗作的格律问题，保持原作意境和风格。\n"
    "直接输出修改后的诗句，每句一行，不要任何解释。"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_form(form: Optional[str]) -> str:
    settings = get_settings()
    return form or settings.generation.shi_default_form


def _normalize_result(content: str) -> str:
    """Extract poem lines from LLM output."""
    import json
    import re

    text = content
    stripped = content.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and "text" in data and isinstance(data["text"], str):
                text = data["text"]
        except json.JSONDecodeError:
            pass

    lines_raw = [line.strip().lstrip(">*•- ") for line in text.split("\n") if line.strip()]

    candidates = []
    for line in lines_raw:
        if line.startswith(("```", "#", "|", "【", "《", "-", "*", "格律", "赏析", ">")):
            continue
        chars_only = re.sub(r"[^\u4e00-\u9fff]", "", line)
        if len(chars_only) in (5, 7) and len(chars_only) >= len(line) * 0.5:
            candidates.append(chars_only)

    if len(candidates) >= 4:
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
            poem = candidates[best_start : best_start + best_len]
            if best_len in (4, 8):
                return "\n".join(poem)
            return "\n".join(poem[:8])

    cleaned = [line for line in lines_raw if not line.startswith(("```", "#", "|"))]
    return "\n".join(cleaned[-16:])


def _persist_trace(trace) -> None:
    try:
        from openprom.infrastructure.task_trace import get_task_trace_store

        get_task_trace_store().save(trace)
    except Exception as e:
        logger.debug("Trace persistence skipped: %s", e)


def _get_meter_context(form: str) -> str:
    try:
        from openprom.tools.poetry_tools import check_meter_unified

        result = check_meter_unified(action="meter_template", form=form)
        if result.get("found"):
            return "\n".join(f"{p['name']}：{p['pattern']}" for p in result["patterns"][:4])
        return ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# ShiGenerator — 3-phase architecture
# ---------------------------------------------------------------------------


class ShiGenerator:
    """Regulated verse generation via 3-phase architecture."""

    def __init__(self, client: Optional[LLMClient] = None):
        self._client = client or get_llm_client()
        self._tools = list(get_tool_registry().values())
        self._settings = get_settings()

    def _phase_inspire(
        self, theme: str, mode: str, form: str, lines: int, chars: int, trace
    ) -> str:
        if mode == "generate":
            user_prompt = f"主题：{theme}\n体裁：{form}（{lines}句，每句{chars}字）。请搜集灵感。"
        else:
            user_prompt = (
                f"已给出内容：{theme}\n体裁：{form}（{lines}句，每句{chars}字）。请搜集补全灵感。"
            )

        result = self._client.chat_with_tools(
            prompt=user_prompt,
            tools=self._tools,
            system_prompt=_INSPIRE_PROMPT,
            max_rounds=2,
            temperature=0.7,
        )

        content = result.get("content", "")
        trace.add_step("llm_call", {"phase": "inspire", "content_preview": content[:200]})
        return content

    def _phase_create(
        self,
        theme: str,
        mode: str,
        form: str,
        lines: int,
        chars: int,
        tone_preference: Optional[str],
        inspiration: str,
        trace,
    ) -> str:
        meter_ctx = _get_meter_context(form)
        tone_part = f"，采用{tone_preference}格式" if tone_preference else ""

        if mode == "generate":
            prompt = (
                f"主题：{theme}\n体裁：{form}（{lines}句，每句{chars}字{tone_part}）\n\n"
                f"格律参考：\n{meter_ctx}\n\n"
                f"灵感素材：\n{inspiration[:500]}\n\n"
                f"请创作。直接输出诗句，每句一行。"
            )
        else:
            prompt = (
                f"已给出内容：{theme}\n体裁：{form}（{lines}句，每句{chars}字{tone_part}）\n\n"
                f"格律参考：\n{meter_ctx}\n\n"
                f"灵感素材：\n{inspiration[:500]}\n\n"
                f"请补全。直接输出完整诗作，每句一行。"
            )

        result = self._client.chat(prompt=prompt, system_prompt=_CREATE_PROMPT, temperature=0.9)
        content = result.get("content", "")
        trace.add_step(
            "llm_call", {"phase": "create", "temperature": 0.9, "content_preview": content[:200]}
        )
        return content

    def _phase_refine(self, draft: str, trace) -> str:
        from openprom.tools.poetry_tools import check_meter_unified

        for round_idx in range(2):
            check = check_meter_unified(action="check", text=draft, meter_type="shi")

            if check.get("is_compliant"):
                trace.add_step("meter_check", {"round": round_idx + 1, "passed": True})
                return draft

            fixes = check.get("fixes", [])
            violations = check.get("violations", [])

            fix_lines = []
            for f in fixes:
                desc = f.get("description", "")
                candidates = f.get("rhyme_candidates", [])
                if candidates:
                    fix_lines.append(f"{desc}（候选：{''.join(candidates[:8])}）")
                else:
                    fix_lines.append(desc)

            fix_text = "\n".join(fix_lines) if fix_lines else "\n".join(violations)

            refine_prompt = (
                f"以下诗作有格律问题，请精准修改：\n\n{draft}\n\n"
                f"问题：\n{fix_text}\n\n"
                f"请直接输出修改后的诗句，每句一行，不要解释。"
            )

            result = self._client.chat(
                prompt=refine_prompt, system_prompt=_REFINE_PROMPT, temperature=0.3
            )
            draft = result.get("content", draft)
            trace.add_step(
                "llm_call", {"phase": "refine", "round": round_idx + 1, "fixes_applied": len(fixes)}
            )

        return draft

    def generate(
        self,
        prompt: str,
        form: Optional[str] = None,
        tone_preference: Optional[str] = None,
        max_rounds: Optional[int] = None,
    ) -> Dict[str, Any]:
        from openprom.agents import TaskTrace

        form = _resolve_form(form)
        lines = _FORM_TO_LINES.get(form, 8)
        chars = _FORM_TO_CHARS.get(form, 7)

        trace = TaskTrace(
            task_name="generate_shi",
            task_id=f"sg-{uuid.uuid4().hex[:12]}",
            started_at=time.time(),
        )

        try:
            inspiration = self._phase_inspire(prompt, "generate", form, lines, chars, trace)
            draft = self._phase_create(
                prompt, "generate", form, lines, chars, tone_preference, inspiration, trace
            )
            final = self._phase_refine(draft, trace)

            normalized = _normalize_result(final)
            trace.success = True
            trace.finished_at = time.time()
            _persist_trace(trace)

            return {"poem": normalized, "raw_content": final, "trace": trace}
        except Exception as e:
            trace.success = False
            trace.error = str(e)
            trace.finished_at = time.time()
            _persist_trace(trace)
            raise

    def complete(
        self,
        prompt: str,
        form: Optional[str] = None,
        tone_preference: Optional[str] = None,
        max_rounds: Optional[int] = None,
    ) -> Dict[str, Any]:
        from openprom.agents import TaskTrace

        form = _resolve_form(form)
        lines = _FORM_TO_LINES.get(form, 8)
        chars = _FORM_TO_CHARS.get(form, 7)

        trace = TaskTrace(
            task_name="complete_shi",
            task_id=f"sc-{uuid.uuid4().hex[:12]}",
            started_at=time.time(),
        )

        try:
            inspiration = self._phase_inspire(prompt, "complete", form, lines, chars, trace)
            draft = self._phase_create(
                prompt, "complete", form, lines, chars, tone_preference, inspiration, trace
            )
            final = self._phase_refine(draft, trace)

            normalized = _normalize_result(final)
            trace.success = True
            trace.finished_at = time.time()
            _persist_trace(trace)

            return {"poem": normalized, "raw_content": final, "trace": trace}
        except Exception as e:
            trace.success = False
            trace.error = str(e)
            trace.finished_at = time.time()
            _persist_trace(trace)
            raise

    def generate_stream(
        self,
        prompt: str,
        form: Optional[str] = None,
        tone_preference: Optional[str] = None,
        max_rounds: Optional[int] = None,
    ) -> Iterable[str]:
        form = _resolve_form(form)
        lines = _FORM_TO_LINES.get(form, 8)
        chars = _FORM_TO_CHARS.get(form, 7)
        prompt_text = f"主题：{prompt}\n体裁：{form}（{lines}句，每句{chars}字）。请创作。"
        max_rounds = max_rounds or self._settings.generation.shi_max_revision_rounds
        yield from self._client.stream_progress(
            prompt=prompt_text,
            tools=self._tools,
            system_prompt=_CREATE_PROMPT,
            max_rounds=max_rounds,
        )

    def complete_stream(
        self,
        prompt: str,
        form: Optional[str] = None,
        tone_preference: Optional[str] = None,
        max_rounds: Optional[int] = None,
    ) -> Iterable[str]:
        form = _resolve_form(form)
        lines = _FORM_TO_LINES.get(form, 8)
        chars = _FORM_TO_CHARS.get(form, 7)
        prompt_text = f"已给出内容：{prompt}\n体裁：{form}（{lines}句，每句{chars}字）。请补全。"
        max_rounds = max_rounds or self._settings.generation.shi_max_revision_rounds
        yield from self._client.stream_progress(
            prompt=prompt_text,
            tools=self._tools,
            system_prompt=_CREATE_PROMPT,
            max_rounds=max_rounds,
        )


def generate_shi(
    prompt: str, form: Optional[str] = None, tone_preference: Optional[str] = None
) -> Dict[str, Any]:
    return ShiGenerator().generate(prompt, form, tone_preference)


def complete_shi(
    prompt: str, form: Optional[str] = None, tone_preference: Optional[str] = None
) -> Dict[str, Any]:
    return ShiGenerator().complete(prompt, form, tone_preference)
