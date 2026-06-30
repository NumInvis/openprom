"""Tests for OpenPROM API routers."""

from fastapi.testclient import TestClient

from openprom.api import app


client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_meter_check_couplet():
    resp = client.post(
        "/api/v1/meter/check", json={"text": "春风化雨\n秋月凝霜", "meter_type": "couplet"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["meter_type"] == "couplet"
    assert "is_compliant" in data


def test_meter_check_shi():
    resp = client.post(
        "/api/v1/meter/check", json={"text": "春眠不觉晓\n处处闻啼鸟", "meter_type": "shi"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["meter_type"] == "shi"
    assert "matched_meters" in data


def test_meter_list():
    resp = client.get("/api/v1/meter/list?meter_type=shi")
    assert resp.status_code == 200
    data = resp.json()
    assert "patterns" in data
    assert len(data["patterns"]) > 0


def test_couplet_analyze_length_mismatch():
    resp = client.post(
        "/api/v1/couplet/analyze",
        json={"upper": "春风化雨润", "lower": "秋月凝霜", "stream": False},
    )
    assert resp.status_code == 400


def test_generate_couplet_missing_prompt():
    resp = client.post("/api/v1/couplet/generate", json={})
    assert resp.status_code == 422


def test_couplet_history_with_session_id():
    """Analyze with X-Session-ID should be retrievable from history."""
    from unittest.mock import patch, MagicMock
    from openprom.services.couplet_scorer import CoupletScorer

    session_id = "test-session-abc-123"

    # Build a minimal mock score object that _build_response expects.
    score = MagicMock()
    score.upper = "春风化雨润桃李"
    score.lower = "秋月凝霜照桂兰"
    score.formal_score = 80.0
    score.technique_score = 80.0
    score.artistic_score = 80.0
    score.impression_score = 80.0
    score.total_score = 80.0
    score.grade = "良好"
    score.pingze_score = 0.9
    score.warnings = []
    score.comments = {}
    score.word_analysis = []
    score.llm_technique_evaluation = {}
    score.llm_rhetoric_evaluation = {}

    with patch.object(CoupletScorer, "analyze", return_value=score):
        resp = client.post(
            "/api/v1/couplet/analyze",
            json={"upper": score.upper, "lower": score.lower, "stream": False},
            headers={"X-Session-ID": session_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        assert "request_id" in data

        history_resp = client.get(
            "/api/v1/couplet/history",
            headers={"X-Session-ID": session_id},
        )
        assert history_resp.status_code == 200
        history = history_resp.json()
        assert len(history["items"]) >= 1
        assert any(item["upper"] == score.upper for item in history["items"])


# ---------------------------------------------------------------------------
# P0-1 regression: `python -m openprom.api` previously passed the string
# "openprom.api:app" to uvicorn.run, causing a second import of the module
# and a crash: "Duplicated timeseries in CollectorRegistry: porm_requests".
# The fix: main() must pass the app object directly when not reloading.
# ---------------------------------------------------------------------------
def test_main_entrypoint_uses_app_object_not_string(monkeypatch):
    """main() must pass the app object (not a string) when not reloading,
    so uvicorn does not re-import the module and trigger duplicate metric
    registration."""
    import openprom.api as api_mod

    captured = {}

    class FakeUvicorn:
        @staticmethod
        def run(app_or_str, host, port, reload):
            captured["app_or_str"] = app_or_str
            captured["host"] = host
            captured["port"] = port
            captured["reload"] = reload

    monkeypatch.setattr(api_mod, "is_debug", lambda: False)
    monkeypatch.setattr(api_mod, "get_host", lambda: "0.0.0.0")
    monkeypatch.setattr(api_mod, "get_port", lambda: 8000)
    import sys

    monkeypatch.setitem(sys.modules, "uvicorn", FakeUvicorn)
    api_mod.main()
    # When reload=False, main must pass the app object, not the string.
    assert captured["app_or_str"] is api_mod.app
    assert captured["reload"] is False


# ---------------------------------------------------------------------------
# P1-1: meter check must auto-split a shi pasted as a single line on Chinese
# sentence-end punctuation, instead of treating it as one 20-char line.
# ---------------------------------------------------------------------------
def test_meter_check_shi_auto_splits_single_line_on_punctuation():
    """A seven-character jueju pasted with 。/，must split into 4 lines."""
    resp = client.post(
        "/api/v1/meter/check",
        json={
            "text": "白日依山尽，黄河入海流。欲穷千里目，更上一层楼。",
            "meter_type": "shi",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # The normalized text must be 4 lines now, not one 20-char line.
    assert data["text"].count("\n") == 3
    # A compliant classical jueju should match at least one pattern validly.
    assert any(m["match_rate"] > 0.5 for m in data["matched_meters"])


def test_meter_check_shi_newline_input_still_works():
    """Explicit newline input (the old supported style) must still work."""
    resp = client.post(
        "/api/v1/meter/check",
        json={
            "text": "白日依山尽\n黄河入海流\n欲穷千里目\n更上一层楼",
            "meter_type": "shi",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"].count("\n") == 3
    assert any(m["match_rate"] > 0.5 for m in data["matched_meters"])


def test_meter_check_couplet_not_split_on_punctuation():
    """Couplet must keep using newline split, not sentence-end punctuation."""
    resp = client.post(
        "/api/v1/meter/check",
        json={"text": "海阔凭鱼跃\n天高任鸟飞", "meter_type": "couplet"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"].count("\n") == 1
