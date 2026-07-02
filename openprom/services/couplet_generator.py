"""Couplet generation — 3-phase architecture.

Phase 1 (Inspire)  — LLM gathers inspiration via tools (retrieve_poetry, web_search).
                     The creative flow is uninterrupted; tools serve the poet.
Phase 2 (Create)   — Single LLM call, high temperature. Meter pattern injected as
                     context so the LLM creates WITH form in mind, not against it.
Phase 3 (Refine)   — check_meter returns actionable fixes; LLM applies targeted
                     corrections. Max 2 rounds. Temperature drops to 0.3 for precision.

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


# ---------------------------------------------------------------------------
# System prompts — minimal, evocative, not prescriptive
# ---------------------------------------------------------------------------

_INSPIRE_PROMPT = (
    "你是诗歌创作助手。帮助诗人搜集灵感。\n"
    "调用 retrieve_poetry 检索古人诗作，或 web_search 搜索知识。\n"
    "也可以直接跳过。准备好后，用3-5句话总结创作方向和可用的意象/典故。"
)

_CREATE_PROMPT = (
    "你是当代最顶尖的对联大师。\n"
    "先有灵感，再求工稳；先有境界，再求技巧。\n"
    "直接输出上下联，用换行分隔，不要任何解释。"
)

_REFINE_PROMPT = (
    "精准修改以下对联的格律问题，保持原作意境和风格。\n"
    "直接输出修改后的上下联，用换行分隔，不要任何解释。"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_result(content: str) -> str:
    """Extract the final couplet lines from LLM content."""
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

    # Try explicit markers
    upper = lower = None
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith(("```", "|")):
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

    # Heuristic: last two lines of equal length, mostly Chinese
    chinese_lines = []
    for line in text.split("\n"):
        line = line.strip().lstrip(">*•- ")
        if not line or line.startswith(("```", "#", "|", "【", "《", "-", "*")):
            continue
        if len(line) <= 12 and len(re.findall(r"[\u4e00-\u9fff]", line)) >= len(line) * 0.5:
            chinese_lines.append(line)

    if len(chinese_lines) >= 2:
        for i in range(len(chinese_lines) - 1, 0, -1):
            if len(chinese_lines[i]) == len(chinese_lines[i - 1]) and len(chinese_lines[i]) >= 4:
                return f"{chinese_lines[i - 1]}\n{chinese_lines[i]}"
        return f"{chinese_lines[-2]}\n{chinese_lines[-1]}"

    return text.strip()[-200:]


def _persist_trace(trace) -> None:
    """Best-effort trace persistence."""
    try:
        from openprom.infrastructure.task_trace import get_task_trace_store

        get_task_trace_store().save(trace)
    except Exception as e:
        logger.debug("Trace persistence skipped: %s", e)


def _get_meter_context(length: int) -> str:
    """Query the meter template and return a human-readable pattern string."""
    try:
        from openprom.tools.poetry_tools import check_meter_unified

        form = "七律" if length == 7 else "五律" if length == 5 else "七律"
        result = check_meter_unified(action="meter_template", form=form)
        if result.get("found"):
            lines = []
            for p in result["patterns"][:4]:
                lines.append(f"{p['name']}：{p['pattern']}")
            return "\n".join(lines)
        return ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# CoupletGenerator — 3-phase architecture
# ---------------------------------------------------------------------------


class CoupletGenerator:
    """Couplet generation via 3-phase architecture.

    Phase 1 (Inspire): tool-calling for gathering inspiration.
    Phase 2 (Create): single LLM call, high temperature, meter as context.
    Phase 3 (Refine): check_meter + targeted fix, max 2 rounds.
    """

    def __init__(self, client: Optional[LLMClient] = None):
        self._client = client or get_llm_client()
        self._tools = list(get_tool_registry().values())
        self._settings = get_settings()

    # -- Phase 1: Inspire ------------------------------------------------

    def _phase_inspire(self, theme: str, mode: str, length: int, trace) -> str:
        """Gather inspiration via tool-calling. LLM decides what to use."""
        if mode == "generate":
            user_prompt = f"主题：{theme}\n每联{length}字对联。请搜集灵感。"
        else:
            user_prompt = f"上联：{theme}\n需要补全{length}字下联。请搜集灵感。"

        def progress_cb(event: str, payload: Dict[str, Any]) -> None:
            """Map chat_with_tools events to trace steps for observability."""
            if event == "tool_call":
                trace.add_step(
                    "tool_call",
                    {"tool": payload.get("tool"), "arguments": payload.get("arguments")},
                )
            elif event == "tool_result":
                last = trace.steps[-1] if trace.steps else None
                if last and last.step_type == "tool_call":
                    result = payload.get("result")
                    if isinstance(result, dict):
                        last.data["result_preview"] = str(result)[:200]
                    else:
                        last.data["result_preview"] = str(result)[:200]

        result = self._client.chat_with_tools(
            prompt=user_prompt,
            tools=self._tools,
            system_prompt=_INSPIRE_PROMPT,
            max_rounds=3,
            temperature=0.7,
            progress_callback=progress_cb,
        )

        content = result.get("content", "")
        trace.add_step(
            "llm_call",
            {
                "phase": "inspire",
                "content_preview": content[:200],
            },
        )
        return content

    # -- Phase 2: Create -------------------------------------------------

    def _phase_create(
        self,
        theme: str,
        mode: str,
        length: int,
        inspiration: str,
        trace,
    ) -> str:
        """Single LLM call — free creation with meter context injected."""
        meter_ctx = _get_meter_context(length)

        if mode == "generate":
            prompt = (
                f"主题：{theme}\n每联{length}字。\n\n"
                f"格律参考：\n{meter_ctx}\n\n"
                f"灵感素材：\n{inspiration[:500]}\n\n"
                f"请创作一副对联。直接输出上下联，用换行分隔。"
            )
        else:
            prompt = (
                f"上联：{theme}\n补全{length}字下联。\n\n"
                f"格律参考：\n{meter_ctx}\n\n"
                f"灵感素材：\n{inspiration[:500]}\n\n"
                f"请补全下联。直接输出完整上下联，用换行分隔。"
            )

        result = self._client.chat(
            prompt=prompt,
            system_prompt=_CREATE_PROMPT,
            temperature=0.9,
        )

        content = result.get("content", "")
        trace.add_step(
            "llm_call",
            {
                "phase": "create",
                "temperature": 0.9,
                "content_preview": content[:200],
            },
        )
        return content

    # -- Phase 3: Refine -------------------------------------------------

    def _phase_refine(self, draft: str, meter_type: str, trace, max_rounds: int = 3) -> str:
        """Verify meter and apply targeted fixes.

        ``max_rounds`` caps the number of check→fix iterations. Defaults to 2
        to preserve historical behavior when callers don't pass it explicitly.
        """
        from openprom.tools.poetry_tools import check_meter_unified

        rounds = max(1, int(max_rounds or 2))
        for round_idx in range(rounds):
            check = check_meter_unified(action="check", text=draft, meter_type=meter_type)

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
                f"以下对联有格律问题，请精准修改：\n\n{draft}\n\n"
                f"问题：\n{fix_text}\n\n"
                f"请直接输出修改后的上下联，用换行分隔，不要解释。"
            )

            result = self._client.chat(
                prompt=refine_prompt,
                system_prompt=_REFINE_PROMPT,
                temperature=0.3,
            )
            draft = result.get("content", draft)
            trace.add_step(
                "llm_call",
                {
                    "phase": "refine",
                    "round": round_idx + 1,
                    "fixes_applied": len(fixes),
                },
            )

        return draft

    # -- Public API ------------------------------------------------------

    def generate(
        self,
        prompt: str,
        length: Optional[int] = None,
        max_rounds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate a couplet from a theme/prompt."""
        from openprom.agents import TaskTrace

        settings = self._settings
        length = length or settings.generation.couplet_default_length

        trace = TaskTrace(
            task_name="generate_couplet",
            task_id=f"cg-{uuid.uuid4().hex[:12]}",
            started_at=time.time(),
        )

        try:
            inspiration = self._phase_inspire(prompt, "generate", length, trace)
            draft = self._phase_create(prompt, "generate", length, inspiration, trace)
            final = self._phase_refine(
                draft, "couplet", trace, max_rounds=max_rounds or settings.generation.couplet_max_revision_rounds
            )

            normalized = _normalize_result(final)
            trace.success = True
            trace.finished_at = time.time()
            _persist_trace(trace)

            return {
                "couplet": normalized,
                "raw_content": final,
                "trace": trace,
            }
        except Exception as e:
            trace.success = False
            trace.error = str(e)
            trace.finished_at = time.time()
            _persist_trace(trace)
            raise

    def complete(
        self,
        prompt: str,
        length: Optional[int] = None,
        max_rounds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Complete a couplet from a partial input."""
        from openprom.agents import TaskTrace

        settings = self._settings
        length = length or settings.generation.couplet_default_length

        trace = TaskTrace(
            task_name="complete_couplet",
            task_id=f"cc-{uuid.uuid4().hex[:12]}",
            started_at=time.time(),
        )

        try:
            inspiration = self._phase_inspire(prompt, "complete", length, trace)
            draft = self._phase_create(prompt, "complete", length, inspiration, trace)
            final = self._phase_refine(
                draft, "couplet", trace, max_rounds=max_rounds or settings.generation.couplet_max_revision_rounds
            )

            normalized = _normalize_result(final)
            trace.success = True
            trace.finished_at = time.time()
            _persist_trace(trace)

            return {
                "couplet": normalized,
                "raw_content": final,
                "trace": trace,
            }
        except Exception as e:
            trace.success = False
            trace.error = str(e)
            trace.finished_at = time.time()
            _persist_trace(trace)
            raise

    def generate_stream(
        self,
        prompt: str,
        length: Optional[int] = None,
        max_rounds: Optional[int] = None,
    ) -> Iterable[str]:
        """Yield SSE data lines (streaming path — uses tool loop directly)."""
        prompt_text = f"主题：{prompt}\n每联{length or 7}字对联。请创作。"
        max_rounds = max_rounds or self._settings.generation.couplet_max_revision_rounds
        yield from self._client.stream_progress(
            prompt=prompt_text,
            tools=self._tools,
            system_prompt=_CREATE_PROMPT,
            max_rounds=max_rounds,
        )

    def complete_stream(
        self,
        prompt: str,
        length: Optional[int] = None,
        max_rounds: Optional[int] = None,
    ) -> Iterable[str]:
        """Yield SSE data lines (streaming path — uses tool loop directly)."""
        prompt_text = f"上联：{prompt}\n请补全下联。"
        max_rounds = max_rounds or self._settings.generation.couplet_max_revision_rounds
        yield from self._client.stream_progress(
            prompt=prompt_text,
            tools=self._tools,
            system_prompt=_CREATE_PROMPT,
            max_rounds=max_rounds,
        )


def generate_couplet(prompt: str, length: Optional[int] = None) -> Dict[str, Any]:
    return CoupletGenerator().generate(prompt, length)


def complete_couplet(prompt: str, length: Optional[int] = None) -> Dict[str, Any]:
    return CoupletGenerator().complete(prompt, length)
