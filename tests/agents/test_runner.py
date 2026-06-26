"""Tests for AgentRunner orchestration with mocked LLM and tools."""

import pytest
from unittest.mock import MagicMock

from openprom.agents import TaskConfig, TaskRegistry, TaskTrace, reset_task_registry
from openprom.agents.runner import AgentRunner, reset_runner


@pytest.fixture(autouse=True)
def _reset_singletons():
    reset_runner()
    reset_task_registry()
    yield
    reset_runner()
    reset_task_registry()


@pytest.fixture
def fake_tool():
    tool = MagicMock()
    tool.name = "check_meter"
    return tool


@pytest.fixture
def fake_registry(fake_tool):
    return {"check_meter": fake_tool}


@pytest.fixture
def task_reg():
    reg = TaskRegistry()
    reg.register(
        TaskConfig(
            name="demo_task",
            description="demo",
            tools=["check_meter"],
            max_llm_rounds=2,
            use_rag=False,
            temperature=0.5,
        )
    )
    return reg


def _fake_llm(content="OUTPUT"):
    llm = MagicMock()

    def chat_with_tools(
        prompt, tools, system_prompt=None, max_rounds=3, temperature=0.7, progress_callback=None
    ):
        if progress_callback:
            progress_callback("thinking", {"round": 1, "max_rounds": max_rounds})
            progress_callback("tool_call", {"tool": "check_meter", "arguments": {"text": "x"}})
            progress_callback("tool_result", {"tool": "check_meter", "result": {"ok": True}})
            progress_callback("thinking", {"round": 2, "max_rounds": max_rounds})
            progress_callback("done", {"content": content})
        return {"content": content, "messages": [{"role": "assistant", "content": content}]}

    llm.chat_with_tools = MagicMock(side_effect=chat_with_tools)
    return llm


class TestAgentRunner:
    def test_unknown_task_raises(self, task_reg, fake_registry):
        runner = AgentRunner(
            llm_client=_fake_llm(),
            tool_registry=fake_registry,
            task_registry=task_reg,
            persist_traces=False,
        )
        with pytest.raises(ValueError):
            runner.run(task_name="nonexistent", user_prompt="x")

    def test_basic_run_returns_content_and_trace(self, task_reg, fake_registry):
        runner = AgentRunner(
            llm_client=_fake_llm("OUTPUT"),
            tool_registry=fake_registry,
            task_registry=task_reg,
            persist_traces=False,
        )
        result = runner.run(task_name="demo_task", user_prompt="topic")
        assert result["content"] == "OUTPUT"
        trace = result["trace"]
        assert isinstance(trace, TaskTrace)
        assert trace.success is True
        assert trace.task_name == "demo_task"
        assert trace.task_id.startswith("t-")
        assert trace.error is None

    def test_trace_contains_llm_tool_and_result_steps(self, task_reg, fake_registry):
        runner = AgentRunner(
            llm_client=_fake_llm(),
            tool_registry=fake_registry,
            task_registry=task_reg,
            persist_traces=False,
        )
        result = runner.run(task_name="demo_task", user_prompt="x")
        types = [s.step_type for s in result["trace"].steps]
        assert types.count("llm_call") == 2
        assert types.count("tool_call") == 1
        assert "result" in types

    def test_tool_call_step_records_arguments_and_result(self, task_reg, fake_registry):
        runner = AgentRunner(
            llm_client=_fake_llm(),
            tool_registry=fake_registry,
            task_registry=task_reg,
            persist_traces=False,
        )
        result = runner.run(task_name="demo_task", user_prompt="x")
        tool_steps = [s for s in result["trace"].steps if s.step_type == "tool_call"]
        assert len(tool_steps) == 1
        assert tool_steps[0].data["tool"] == "check_meter"
        assert tool_steps[0].data["arguments"] == {"text": "x"}
        assert "result" in tool_steps[0].data

    def test_extra_context_is_prepended(self, task_reg, fake_registry):
        llm = _fake_llm()
        runner = AgentRunner(
            llm_client=llm,
            tool_registry=fake_registry,
            task_registry=task_reg,
            persist_traces=False,
        )
        runner.run(task_name="demo_task", user_prompt="USER_PROMPT", extra_context="EXTRA_CTX")
        called_prompt = llm.chat_with_tools.call_args.kwargs["prompt"]
        assert "EXTRA_CTX" in called_prompt
        assert "USER_PROMPT" in called_prompt

    def test_max_rounds_override(self, task_reg, fake_registry):
        llm = _fake_llm()
        runner = AgentRunner(
            llm_client=llm,
            tool_registry=fake_registry,
            task_registry=task_reg,
            persist_traces=False,
        )
        runner.run(task_name="demo_task", user_prompt="x", max_rounds_override=7)
        assert llm.chat_with_tools.call_args.kwargs["max_rounds"] == 7

    def test_only_declared_tools_are_passed(self, task_reg):
        registry = {"check_meter": MagicMock(), "retrieve_poems": MagicMock()}
        registry["check_meter"].name = "check_meter"
        registry["retrieve_poems"].name = "retrieve_poems"
        llm = _fake_llm()
        runner = AgentRunner(
            llm_client=llm,
            tool_registry=registry,
            task_registry=task_reg,
            persist_traces=False,
        )
        runner.run(task_name="demo_task", user_prompt="x")
        passed = llm.chat_with_tools.call_args.kwargs["tools"]
        assert len(passed) == 1
        assert passed[0] is registry["check_meter"]

    def test_failure_emits_failed_trace_via_persist(self, task_reg, fake_registry):
        store = MagicMock()
        llm = MagicMock()
        llm.chat_with_tools = MagicMock(side_effect=RuntimeError("LLM down"))
        runner = AgentRunner(
            llm_client=llm,
            tool_registry=fake_registry,
            task_registry=task_reg,
            trace_store=store,
            persist_traces=True,
        )
        with pytest.raises(RuntimeError):
            runner.run(task_name="demo_task", user_prompt="x")
        assert store.save.called
        saved = store.save.call_args.args[0]
        assert saved.success is False
        assert "LLM down" in (saved.error or "")

    def test_trace_persistence_when_enabled(self, task_reg, fake_registry):
        store = MagicMock()
        runner = AgentRunner(
            llm_client=_fake_llm(),
            tool_registry=fake_registry,
            task_registry=task_reg,
            trace_store=store,
            persist_traces=True,
        )
        runner.run(task_name="demo_task", user_prompt="x")
        assert store.save.called
        assert store.save.call_args.args[0].success is True

    def test_trace_persistence_disabled(self, task_reg, fake_registry):
        store = MagicMock()
        runner = AgentRunner(
            llm_client=_fake_llm(),
            tool_registry=fake_registry,
            task_registry=task_reg,
            trace_store=store,
            persist_traces=False,
        )
        runner.run(task_name="demo_task", user_prompt="x")
        assert not store.save.called

    def test_summarize_truncates_long_strings(self):
        out = AgentRunner._summarize_tool_result("x" * 1000)
        assert len(out) <= 200

    def test_summarize_truncates_long_lists(self):
        out = AgentRunner._summarize_tool_result(list(range(100)))
        assert len(out) == 5

    def test_summarize_truncates_dict_keys(self):
        d = {f"k{i}": i for i in range(50)}
        out = AgentRunner._summarize_tool_result(d)
        assert len(out) <= 8


class TestRagAugmentation:
    def test_rag_step_emitted_when_use_rag_true(self, fake_registry, monkeypatch):
        reg = TaskRegistry()
        reg.register(
            TaskConfig(
                name="rag_task",
                tools=["check_meter"],
                use_rag=True,
                rag_task_type="generate_couplet",
                max_llm_rounds=1,
            )
        )

        class _StubResultSet:
            def to_prompt_text(self):
                return "STUB_CONTEXT"

        class _StubPipeline:
            def retrieve(self, **kwargs):
                return _StubResultSet()

        import openprom.knowledge.retrieval.pipeline as pipe_mod

        monkeypatch.setattr(pipe_mod, "get_retrieval_pipeline", lambda: _StubPipeline())

        runner = AgentRunner(
            llm_client=_fake_llm(),
            tool_registry=fake_registry,
            task_registry=reg,
            persist_traces=False,
        )
        result = runner.run(task_name="rag_task", user_prompt="QUERY")
        types = [s.step_type for s in result["trace"].steps]
        assert "rag_retrieval" in types

    def test_rag_failure_does_not_break_run(self, fake_registry, monkeypatch):
        reg = TaskRegistry()
        reg.register(
            TaskConfig(
                name="rag_task",
                tools=["check_meter"],
                use_rag=True,
                rag_task_type="generate_couplet",
                max_llm_rounds=1,
            )
        )

        def _boom():
            raise RuntimeError("chroma down")

        import openprom.knowledge.retrieval.pipeline as pipe_mod

        monkeypatch.setattr(pipe_mod, "get_retrieval_pipeline", _boom)

        runner = AgentRunner(
            llm_client=_fake_llm(),
            tool_registry=fake_registry,
            task_registry=reg,
            persist_traces=False,
        )
        result = runner.run(task_name="rag_task", user_prompt="x")
        assert result["trace"].success is True

    def test_extra_context_skips_rag(self, fake_registry, monkeypatch):
        reg = TaskRegistry()
        reg.register(
            TaskConfig(
                name="rag_task",
                tools=["check_meter"],
                use_rag=True,
                rag_task_type="generate_couplet",
                max_llm_rounds=1,
            )
        )

        def _should_not_call():
            raise AssertionError("RAG should not run when extra_context provided")

        import openprom.knowledge.retrieval.pipeline as pipe_mod

        monkeypatch.setattr(pipe_mod, "get_retrieval_pipeline", _should_not_call)

        runner = AgentRunner(
            llm_client=_fake_llm(),
            tool_registry=fake_registry,
            task_registry=reg,
            persist_traces=False,
        )
        result = runner.run(task_name="rag_task", user_prompt="x", extra_context="CTX")
        types = [s.step_type for s in result["trace"].steps]
        assert "rag_retrieval" not in types
