"""AgentRunner: executes a TaskConfig with full observability.

Wraps LLMClient.chat_with_tools and emits a TaskTrace recording every
LLM round, tool call, RAG retrieval, and final outcome. The trace is
optionally persisted via TaskTraceStore.

This is the L2 (Orchestration) entry point envisioned in
doc/02-target-architecture.md §2.2.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from openprom.agents import TaskConfig, TaskTrace, get_task_registry

logger = logging.getLogger(__name__)


class AgentRunner:
    """Executes a registered Task and produces a TaskTrace.

    Usage:
        runner = AgentRunner()
        result = runner.run(
            task_name="generate_couplet",
            user_prompt="春风送暖入屠苏",
            system_prompt="你是对联大师...",
        )
        # result["content"] -> final LLM output
        # result["trace"]   -> TaskTrace
    """

    def __init__(
        self,
        llm_client=None,
        tool_registry: Optional[Dict[str, Any]] = None,
        task_registry=None,
        trace_store=None,
        persist_traces: bool = True,
    ):
        self._llm = llm_client
        self._tool_registry = tool_registry
        self._tasks = task_registry or get_task_registry()
        self._trace_store = trace_store
        self._persist = persist_traces

    def _ensure_llm(self):
        if self._llm is None:
            from openprom.services.llm_client import get_llm_client
            self._llm = get_llm_client()
        return self._llm

    def _ensure_tools(self) -> Dict[str, Any]:
        if self._tool_registry is None:
            from openprom.tools.registry import get_tool_registry
            self._tool_registry = get_tool_registry()
        return self._tool_registry

    def _select_tools(self, task: TaskConfig) -> List[Any]:
        """Pick the Tool objects this task is allowed to use, by name."""
        registry = self._ensure_tools()
        if not task.tools:
            return list(registry.values())
        selected = []
        for name in task.tools:
            tool = registry.get(name)
            if tool is None:
                logger.warning("Task %s declared unknown tool: %s", task.name, name)
                continue
            selected.append(tool)
        return selected

    def run(
        self,
        task_name: str,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        max_rounds_override: Optional[int] = None,
        extra_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a task end-to-end and return {content, trace, messages}.

        Args:
            task_name: Name registered in TaskRegistry.
            user_prompt: User's input (theme, partial poem, couplet to score, etc).
            system_prompt: Override the task's default system prompt.
            max_rounds_override: Override the task's max_llm_rounds.
            extra_context: Additional context to prepend to the user prompt
                (e.g. retrieved poems formatted for prompt injection).
        """
        task = self._tasks.get(task_name)
        if task is None:
            raise ValueError(f"Unknown task: {task_name}")

        trace = TaskTrace(
            task_name=task_name,
            task_id=f"t-{uuid.uuid4().hex[:12]}",
            started_at=time.time(),
        )

        try:
            # Stage 1: optional RAG context augmentation
            augmented_prompt = user_prompt
            if extra_context:
                augmented_prompt = f"{extra_context}\n\n{user_prompt}"
            elif task.use_rag:
                rag_t0 = time.time()
                retrieved = self._do_retrieval(task, user_prompt)
                rag_dur = (time.time() - rag_t0) * 1000
                if retrieved:
                    augmented_prompt = f"{retrieved}\n\n{user_prompt}"
                trace.add_step(
                    "rag_retrieval",
                    {
                        "task_type": task.rag_task_type,
                        "query": user_prompt[:80],
                        "context_len": len(retrieved) if retrieved else 0,
                    },
                    duration_ms=rag_dur,
                )

            # Stage 2: tool-calling loop
            tools = self._select_tools(task)
            sys_prompt = system_prompt or task.system_prompt or None
            max_rounds = max_rounds_override or task.max_llm_rounds

            def progress_cb(event: str, payload: Dict[str, Any]) -> None:
                # Map progress events to trace steps
                if event == "thinking":
                    trace.add_step("llm_call", {"round": payload.get("round")})
                elif event == "tool_call":
                    trace.add_step(
                        "tool_call",
                        {"tool": payload.get("tool"), "arguments": payload.get("arguments")},
                    )
                elif event == "tool_result":
                    last = trace.steps[-1] if trace.steps else None
                    if last and last.step_type == "tool_call":
                        last.data["result"] = self._summarize_tool_result(
                            payload.get("result")
                        )

            llm_t0 = time.time()
            llm = self._ensure_llm()
            result = llm.chat_with_tools(
                prompt=augmented_prompt,
                tools=tools,
                system_prompt=sys_prompt,
                max_rounds=max_rounds,
                temperature=task.temperature,
                progress_callback=progress_cb,
            )
            llm_dur = (time.time() - llm_t0) * 1000

            content = result.get("content", "")
            trace.add_step(
                "result",
                {"content_preview": content[:120], "messages_count": len(result.get("messages", []))},
                duration_ms=llm_dur,
            )
            trace.success = True
            trace.finished_at = time.time()
            self._maybe_persist(trace)
            return {
                "content": content,
                "messages": result.get("messages", []),
                "trace": trace,
            }
        except Exception as e:
            trace.success = False
            trace.error = str(e)
            trace.finished_at = time.time()
            self._maybe_persist(trace)
            logger.exception("Task %s failed", task_name)
            raise

    def _do_retrieval(self, task: TaskConfig, query: str) -> str:
        """Run retrieval and format for prompt injection.

        Dual-path: uses knowledge layer v2 pipeline when both
        ``features.knowledge_layer_v2`` and ``knowledge.enabled`` are true;
        otherwise falls back to the legacy Hermes retriever via
        ``services.rag.poetry_knowledge``.
        """
        try:
            from openprom.infrastructure.config.settings import get_settings
            settings = get_settings()

            features = getattr(settings, "features", None)
            knowledge_cfg = getattr(settings, "knowledge", None)
            v2_enabled = bool(
                features
                and getattr(features, "knowledge_layer_v2", False)
                and knowledge_cfg
                and getattr(knowledge_cfg, "enabled", False)
            )

            if v2_enabled:
                return self._do_retrieval_v2(task, query)

            if getattr(settings.rag, "enabled", False):
                return self._do_retrieval_legacy(query, settings)

            return ""
        except Exception as e:
            logger.debug("RAG retrieval skipped: %s", e)
            return ""

    @staticmethod
    def _do_retrieval_v2(task: TaskConfig, query: str) -> str:
        """Knowledge layer v2 pipeline path."""
        from openprom.knowledge.retrieval.pipeline import get_retrieval_pipeline

        pipeline = get_retrieval_pipeline()
        result_set = pipeline.retrieve(query=query, task_type=task.rag_task_type)
        return result_set.to_prompt_text()

    @staticmethod
    def _do_retrieval_legacy(query: str, settings) -> str:
        """Legacy Hermes retriever path (via poetry_knowledge adapter)."""
        from openprom.services.rag.poetry_knowledge import get_poetry_knowledge

        pk = get_poetry_knowledge()
        examples = pk.retrieve_examples(
            theme=query,
            form=None,
            top_k=settings.rag.retrieve_top_k,
        )
        if not examples:
            return ""
        return pk.format_imagery(examples)

    @staticmethod
    def _summarize_tool_result(result: Any) -> Any:
        """Truncate large tool results for trace storage."""
        if isinstance(result, str):
            return result[:200]
        if isinstance(result, dict):
            keys = list(result.keys())[:8]
            return {k: AgentRunner._summarize_tool_result(result[k]) for k in keys}
        if isinstance(result, list):
            return [AgentRunner._summarize_tool_result(x) for x in result[:5]]
        return result

    def _maybe_persist(self, trace: TaskTrace) -> None:
        if not self._persist:
            return
        try:
            store = self._trace_store
            if store is None:
                from openprom.infrastructure.task_trace import get_task_trace_store
                store = get_task_trace_store()
            store.save(trace)
        except Exception as e:
            logger.debug("Trace persistence skipped: %s", e)


_global_runner: Optional[AgentRunner] = None


def get_agent_runner() -> AgentRunner:
    """Get or create the singleton AgentRunner."""
    global _global_runner
    if _global_runner is None:
        _global_runner = AgentRunner()
    return _global_runner


def reset_runner() -> None:
    """Reset singleton (for testing)."""
    global _global_runner
    _global_runner = None
