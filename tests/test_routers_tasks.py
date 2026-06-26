"""Tests for /api/v1/tasks router."""

from fastapi.testclient import TestClient

from openprom.api import app
from openprom.agents import reset_task_registry
from openprom.agents.runner import reset_runner

client = TestClient(app)


def teardown_function(_fn):
    reset_runner()
    reset_task_registry()


def test_list_tasks():
    resp = client.get("/api/v1/tasks/")
    assert resp.status_code == 200
    data = resp.json()
    assert "tasks" in data
    names = [t["name"] for t in data["tasks"]]
    assert any(n in names for n in ["generate_couplet", "score_couplet", "generate_shi"])


def test_run_task_unknown_returns_404():
    resp = client.post(
        "/api/v1/tasks/run",
        json={
            "task_name": "totally_unknown_task",
            "user_prompt": "hi",
        },
    )
    assert resp.status_code == 404


def test_run_task_success(monkeypatch):
    from openprom.agents.runner import AgentRunner
    from openprom.agents import TaskTrace

    def _fake_run(
        self,
        *,
        task_name,
        user_prompt,
        system_prompt=None,
        max_rounds_override=None,
        extra_context=None,
    ):
        trace = TaskTrace(task_name=task_name, task_id="t-test123")
        trace.add_step("llm_call", {"round": 1})
        trace.success = True
        return {"content": "FAKE_CONTENT", "messages": [], "trace": trace}

    monkeypatch.setattr(AgentRunner, "run", _fake_run)
    resp = client.post(
        "/api/v1/tasks/run",
        json={
            "task_name": "generate_couplet",
            "user_prompt": "春风",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["content"] == "FAKE_CONTENT"
    assert data["trace"]["task_id"] == "t-test123"
    assert data["trace"]["success"] is True


def test_list_traces_empty_ok():
    resp = client.get("/api/v1/tasks/traces?limit=5")
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        assert isinstance(resp.json(), list)


def test_get_trace_not_found():
    resp = client.get("/api/v1/tasks/traces/does-not-exist")
    assert resp.status_code in (404, 503)
