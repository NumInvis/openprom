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
    resp = client.post("/api/v1/meter/check", json={
        "text": "春风化雨\n秋月凝霜",
        "meter_type": "couplet"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["meter_type"] == "couplet"
    assert "is_compliant" in data


def test_meter_check_shi():
    resp = client.post("/api/v1/meter/check", json={
        "text": "春眠不觉晓\n处处闻啼鸟",
        "meter_type": "shi"
    })
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
    resp = client.post("/api/v1/couplet/analyze", json={
        "upper": "春风化雨润",
        "lower": "秋月凝霜",
        "stream": False
    })
    assert resp.status_code == 400


def test_generate_couplet_missing_prompt():
    resp = client.post("/api/v1/couplet/generate", json={})
    assert resp.status_code == 422
