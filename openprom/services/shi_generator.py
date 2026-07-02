"""Regulated verse generation — 3-phase architecture.

Phase 1 (Inspire)  — LLM gathers inspiration via tools.
Phase 2 (Create)   — Single LLM call, high temperature, meter context injected.
Phase 3 (Refine)   — check_meter + targeted fix, max 2 rounds.

Streaming paths still use LLMClient.stream_progress directly.
"""

import logging
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional

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
    "你是诗歌创作助手。可调用工具检索古人诗作或搜索典故。"
)

_CREATE_PROMPT = (
    "你是当代古典诗人。\n\n"
    "【忌用】陈词滥调：壮志、豪情、乘风破浪、沧海、红尘、岁月、芳华、"
    "天涯、长空、断肠、相思、离愁、寂寞、凄凉、惆怅、惘然、凭栏。\n\n"
    "【力作要点】\n"
    "1. 含具体物象，不以空词抒情。\n"
    "2. 起承转合完整，末句有余韵。\n"
    "3. 字句硬朗，每字有质地。\n\n"
    "输出诗句，每句一行，无标题，无标点。"
)

_REFINE_PROMPT = (
    "修改以下诗作的格律问题，保持意境和风格。\n"
    "直接输出诗句，每句一行，不要解释。"
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

    @staticmethod
    def _filter_tools(tools: List, exclude: frozenset) -> List:
        """Return tool list minus excluded names."""
        return [t for t in tools if t.name not in exclude]

    def _phase_inspire(
        self, theme: str, mode: str, form: str, lines: int, chars: int, trace
    ) -> str:
        if mode == "generate":
            user_prompt = f"主题：{theme}\n体裁：{form}（{lines}句×{chars}字）。"
        else:
            user_prompt = f"待补全内容：{theme}\n体裁：{form}（{lines}句×{chars}字）。"

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

        inspire_tools = self._filter_tools(self._tools, frozenset({"check_meter", "self_critique"}))
        result = self._client.chat_with_tools(
            prompt=user_prompt,
            tools=inspire_tools,
            system_prompt=_INSPIRE_PROMPT,
            max_rounds=3,
            temperature=0.7,
            progress_callback=progress_cb,
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
                f"主题：{theme}\n体裁：{form}（{lines}句×{chars}字{tone_part}）\n"
                f"格律：\n{meter_ctx}\n"
                f"参考：\n{inspiration[:500]}"
            )
        else:
            prompt = (
                f"待补全：{theme}\n体裁：{form}（{lines}句×{chars}字{tone_part}）\n"
                f"格律：\n{meter_ctx}\n"
                f"参考：\n{inspiration[:500]}"
            )

        result = self._client.chat(prompt=prompt, system_prompt=_CREATE_PROMPT, temperature=0.9)
        content = result.get("content", "")
        trace.add_step(
            "llm_call", {"phase": "create", "temperature": 0.9, "content_preview": content[:200]}
        )
        return content

    def _phase_refine(self, draft: str, trace, max_rounds: int = 3) -> str:
        from openprom.tools.poetry_tools import check_meter_unified

        rounds = max(1, int(max_rounds or 2))
        for round_idx in range(rounds):
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
                f"{draft}\n\n"
                f"格律问题：\n{fix_text}\n\n"
                f"修改后输出诗句，每句一行："
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
            final = self._phase_refine(
                draft, trace, max_rounds=max_rounds or self._settings.generation.shi_max_revision_rounds
            )

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
            final = self._phase_refine(
                draft, trace, max_rounds=max_rounds or self._settings.generation.shi_max_revision_rounds
            )

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
        return self._run_streamed(
            prompt=prompt,
            form=form,
            lines=lines,
            chars=chars,
            tone_preference=tone_preference,
            max_rounds=max_rounds,
            mode="generate",
            task_name="generate_shi_stream",
            trace_prefix="sgs",
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
        return self._run_streamed(
            prompt=prompt,
            form=form,
            lines=lines,
            chars=chars,
            tone_preference=tone_preference,
            max_rounds=max_rounds,
            mode="complete",
            task_name="complete_shi_stream",
            trace_prefix="scs",
        )

    def _run_streamed(
        self,
        prompt: str,
        form: str,
        lines: int,
        chars: int,
        tone_preference: Optional[str],
        max_rounds: Optional[int],
        mode: str,
        task_name: str,
        trace_prefix: str,
    ) -> Iterable[str]:
        """Shared 3-phase streamed generation for generate/complete."""
        from openprom.agents import TaskTrace
        import queue

        trace = TaskTrace(
            task_name=task_name,
            task_id=f"{trace_prefix}-{uuid.uuid4().hex[:12]}",
            started_at=time.time(),
        )
        event_queue: "queue.Queue[Optional[str]]" = queue.Queue()

        is_generate = mode == "generate"

        def _emit(evt: str, payload: Dict[str, Any]) -> None:
            import json
            event_queue.put(json.dumps({"event": evt, **payload}, ensure_ascii=False))

        def _run() -> None:
            try:
                # Phase 1: Inspire
                _emit("phase", {"phase": "inspire", "label": "灵感搜集"})
                inspire_tools = self._filter_tools(self._tools, frozenset({"check_meter", "self_critique"}))

                def _inspire_cb(event: str, data: Dict[str, Any]) -> None:
                    if event == "thinking":
                        _emit("thinking", {"phase": "inspire", "round": data.get("round")})
                    elif event == "tool_call":
                        _emit("tool_call", {"phase": "inspire", "tool": data.get("tool"), "arguments": data.get("arguments")})
                    elif event == "tool_result":
                        res = data.get("result")
                        _emit("tool_result", {"phase": "inspire", "tool": data.get("tool"), "result": res if not isinstance(res, dict) else str(res)[:300]})

                user_prompt = (
                    f"主题：{prompt}\n体裁：{form}（{lines}句×{chars}字）。"
                    if is_generate else
                    f"待补全内容：{prompt}\n体裁：{form}（{lines}句×{chars}字）。"
                )
                inspire_result = self._client.chat_with_tools(
                    prompt=user_prompt,
                    tools=inspire_tools,
                    system_prompt=_INSPIRE_PROMPT,
                    max_rounds=3,
                    temperature=0.7,
                    progress_callback=_inspire_cb,
                )
                inspiration = inspire_result.get("content", "")

                # Phase 2: Create
                _emit("phase", {"phase": "create", "label": "创作"})
                meter_ctx = _get_meter_context(form)
                tone_part = f"，{tone_preference}格式" if tone_preference else ""
                topic_line = f"主题：{prompt}" if is_generate else f"待补全：{prompt}"
                create_result = self._client.chat(
                    prompt=(
                        f"{topic_line}\n体裁：{form}（{lines}句×{chars}字{tone_part}）\n"
                        f"格律：\n{meter_ctx}\n"
                        f"参考：\n{inspiration[:500]}"
                    ),
                    system_prompt=_CREATE_PROMPT,
                    temperature=0.9,
                )
                _emit("done", {"content": create_result.get("content", "")})

                # Phase 3: Refine
                _emit("phase", {"phase": "refine", "label": "格律修正"})
                draft = create_result.get("content", "")
                refined = self._phase_refine(draft, trace, max_rounds=max_rounds or self._settings.generation.shi_max_revision_rounds)

                normalized = _normalize_result(refined)
                trace.success = True
                trace.finished_at = time.time()
                _persist_trace(trace)
                _emit("final", {"content": normalized})
            except Exception as e:
                logger.exception("%s failed", task_name)
                _emit("error", {"message": str(e)})
            finally:
                event_queue.put(None)

        import threading
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        while True:
            try:
                line = event_queue.get(timeout=5.0)
            except queue.Empty:
                continue
            if line is None:
                break
            yield line

        thread.join(timeout=5.0)


def generate_shi(
    prompt: str, form: Optional[str] = None, tone_preference: Optional[str] = None
) -> Dict[str, Any]:
    return ShiGenerator().generate(prompt, form, tone_preference)


def complete_shi(
    prompt: str, form: Optional[str] = None, tone_preference: Optional[str] = None
) -> Dict[str, Any]:
    return ShiGenerator().complete(prompt, form, tone_preference)
