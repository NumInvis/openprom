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
