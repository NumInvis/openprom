"""Tests for TaskRegistry, TaskConfig, TaskTrace, and QueryPlanner."""

import pytest

from openprom.agents import TaskConfig, TaskRegistry, TaskTrace, get_task_registry
from openprom.knowledge.retrieval.pipeline import QueryPlanner


class TestTaskRegistry:
    def test_register_and_get(self):
        reg = TaskRegistry()
        cfg = TaskConfig(name="demo", description="a demo task")
        reg.register(cfg)
        assert reg.get("demo") is cfg
        assert reg.get("demo").description == "a demo task"

    def test_get_missing_returns_none(self):
        reg = TaskRegistry()
        assert reg.get("nonexistent") is None

    def test_list_tasks(self):
        reg = TaskRegistry()
        reg.register(TaskConfig(name="alpha"))
        reg.register(TaskConfig(name="beta"))
        assert sorted(reg.list_tasks()) == ["alpha", "beta"]


class TestTaskConfigDefaults:
    def test_defaults(self):
        cfg = TaskConfig(name="t")
        assert cfg.description == ""
        assert cfg.system_prompt == ""
        assert cfg.tools == []
        assert cfg.max_llm_rounds == 3
        assert cfg.use_rag is True
        assert cfg.rag_task_type == "general"
        assert cfg.use_saddle is False
        assert cfg.streaming is True
        assert cfg.temperature == 0.7


class TestGetTaskRegistry:
    def test_returns_five_tasks(self):
        reg = get_task_registry()
        names = set(reg.list_tasks())
        expected = {
            "generate_couplet",
            "complete_couplet",
            "generate_shi",
            "complete_shi",
            "analyze_couplet",
        }
        assert names == expected

    def test_singleton(self):
        a = get_task_registry()
        b = get_task_registry()
        assert a is b


class TestTaskTrace:
    def test_add_step(self):
        trace = TaskTrace(task_name="demo")
        trace.add_step("llm_call", {"prompt": "hello"}, duration_ms=12.5)
        assert len(trace.steps) == 1
        assert trace.steps[0].step_type == "llm_call"
        assert trace.steps[0].data == {"prompt": "hello"}
        assert trace.steps[0].duration_ms == 12.5

    def test_to_dict(self):
        trace = TaskTrace(task_name="demo", task_id="t-1", started_at=1.0, finished_at=2.0)
        trace.add_step("rag_retrieval", {"query": "q"}, duration_ms=5.0)
        d = trace.to_dict()
        assert d["task_name"] == "demo"
        assert d["task_id"] == "t-1"
        assert d["rag_calls"] == 1
        assert d["total_duration_ms"] == pytest.approx(1000.0)
        assert len(d["steps"]) == 1
        assert d["steps"][0]["type"] == "rag_retrieval"

    def test_to_dict_empty_trace(self):
        trace = TaskTrace(task_name="empty")
        d = trace.to_dict()
        assert d["llm_calls"] == 0
        assert d["tool_calls"] == 0
        assert d["rag_calls"] == 0


class TestQueryPlanner:
    def test_plan_returns_correct_profile(self):
        qp = QueryPlanner()
        profile = qp.plan("generate_couplet")
        assert profile["top_k"] == 5
        assert profile["top_k_recall"] == 15
        assert "couplet" in profile["preferred_chunk_types"]

    def test_plan_fallback_to_general(self):
        qp = QueryPlanner()
        profile = qp.plan("unknown_task")
        assert profile["top_k"] == 5
        assert profile["top_k_recall"] == 20
        assert profile["preferred_chunk_types"] == []

    def test_list_tasks(self):
        qp = QueryPlanner()
        tasks = qp.list_tasks()
        assert "generate_couplet" in tasks
        assert "generate_shi" in tasks
        assert "analyze_couplet" in tasks
        assert "general" in tasks

    def test_custom_profiles(self):
        custom = {
            "custom": {"top_k": 99, "top_k_recall": 999, "preferred_chunk_types": []},
            "general": {"top_k": 5, "top_k_recall": 20, "preferred_chunk_types": []},
        }
        qp = QueryPlanner(profiles=custom)
        assert qp.plan("custom")["top_k"] == 99
        assert qp.plan("custom")["top_k_recall"] == 999
        assert qp.plan("custom")["top_k_recall"] == 999
