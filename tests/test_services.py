"""Tests for new application-layer services."""

from openprom.services.meter_tool import check_meter, get_rhyme_candidates, explain_rule


def test_check_meter_couplet_valid():
    """A well-formed couplet should pass formal checks."""
    # 春风化雨 (平) 对 秋月凝霜 (平) — only structural sample
    result = check_meter("春风化雨\n秋月凝霜", meter_type="couplet")
    assert "pingze_sequence" in result
    assert result["meter_type"] == "couplet"


def test_check_meter_couplet_length_mismatch():
    result = check_meter("春风化雨润\n秋月凝霜", meter_type="couplet")
    assert not result["is_compliant"]
    assert any("字数不等" in v for v in result["violations"])


def test_check_meter_shi():
    result = check_meter("春眠不觉晓\n处处闻啼鸟", meter_type="shi")
    assert result["meter_type"] == "shi"
    assert "matched_meters" in result


def test_get_rhyme_candidates():
    candidates = get_rhyme_candidates("天", tone="ping", count=5)
    assert isinstance(candidates, list)
    assert len(candidates) <= 5


def test_explain_rule():
    text = explain_rule("pingze")
    assert "平仄" in text


def test_generator_build_prompt():
    # Validate that prompts can be built without API call
    from openprom.services.couplet_generator import _build_prompt
    prompt = _build_prompt("generate", "春天", length=7)
    assert "春天" in prompt
    assert "7" in prompt


def test_shi_generator_resolve_form():
    from openprom.services.shi_generator import _resolve_form
    assert _resolve_form("五律") == "五律"
    assert _resolve_form(None) in ("七律", "五律")
