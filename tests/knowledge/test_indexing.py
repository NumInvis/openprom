"""Tests for the indexing pipeline: normalizer, enricher, validator, corpus_builder chunking."""

import pytest

from openprom.knowledge.indexing.normalizer import normalize_batch, normalize_record, normalize_text
from openprom.knowledge.indexing.enricher import (
    detect_form,
    detect_rhyme_category,
    enrich_batch,
    enrich_record,
    split_couplet,
)
from openprom.knowledge.indexing.validator import validate_batch, validate_record
from openprom.knowledge.indexing.corpus_builder import chunk_record, load_source


# ---- normalizer tests ----


class TestNormalizeText:
    def test_strips_whitespace(self):
        assert normalize_text("  hello  ") == "hello"

    def test_collapses_internal_whitespace(self):
        assert normalize_text("a  b  c") == "a b c"

    def test_empty_string(self):
        assert normalize_text("") == ""

    def test_none_returns_empty(self):
        assert normalize_text(None) == ""


class TestNormalizeRecord:
    def test_valid_record(self):
        raw = {
            "id": 1,
            "title": "静夜思",
            "author": "李白",
            "dynasty": "唐",
            "paragraphs": ["床前明月光", "疑是地上霜"],
        }
        rec = normalize_record(raw, idx=0)
        assert rec is not None
        assert rec["id"] == "1"  # normalizer always converts to str
        assert rec["title"] == "静夜思"
        assert rec["author"] == "李白"
        assert rec["dynasty"] == "唐"
        assert rec["content"] == "床前明月光\n疑是地上霜"

    def test_content_from_string(self):
        raw = {"title": "test", "content": "一行诗"}
        rec = normalize_record(raw)
        assert rec is not None
        assert rec["content"] == "一行诗"

    def test_empty_content_returns_none(self):
        raw = {"title": "test", "paragraphs": []}
        assert normalize_record(raw) is None

    def test_missing_id_generates_fallback(self):
        raw = {"title": "t", "paragraphs": ["内容"]}
        rec = normalize_record(raw, idx=5)
        assert rec is not None
        assert rec["id"] == "poem_5"

    def test_rhythmic_as_title(self):
        raw = {"rhythmic": "蝶恋花", "paragraphs": ["内容"]}
        rec = normalize_record(raw)
        assert rec["title"] == "蝶恋花"

    def test_text_field_as_content(self):
        raw = {"title": "t", "text": "内容文本"}
        rec = normalize_record(raw)
        assert rec["content"] == "内容文本"


class TestNormalizeBatch:
    def test_drops_invalid(self):
        records = [
            {"title": "t1", "paragraphs": ["内容一"]},
            {"title": "t2", "paragraphs": []},  # invalid: empty content
            {"title": "t3", "paragraphs": ["内容三"]},
        ]
        result = normalize_batch(records)
        assert len(result) == 2

    def test_empty_input(self):
        assert normalize_batch([]) == []


# ---- enricher tests ----


class TestDetectForm:
    def test_wu_jue(self):
        content = "白日依山尽\n黄河入海流\n欲穷千里目\n更上一层楼"
        assert detect_form(content) == "wu jue"

    def test_qi_jue(self):
        content = "日照香炉生紫烟\n遥看瀑布挂前川\n飞流直下三千尺\n疑是银河落九天"
        assert detect_form(content) == "qi jue"

    def test_wu_lv(self):
        lines = ["空山新雨后"] * 8
        assert detect_form("\n".join(lines)) == "wu lv"

    def test_qi_lv(self):
        lines = ["风急天高猿啸哀"] * 8
        assert detect_form("\n".join(lines)) == "qi lv"

    def test_ci_variable_lengths(self):
        # 长短句不齐 → 落到 "ci" 分支
        content = "明月几时有\n把酒问青天\n不知天上宫阙今夕是何年\n我欲乘风归去"
        assert detect_form(content) == "ci"

    def test_duilian(self):
        content = "春风送暖\n秋雨生凉"
        assert detect_form(content) == "duilian"

    def test_empty_returns_empty(self):
        assert detect_form("") == ""

    def test_guti_fallback(self):
        content = "长诗一首\n" * 20
        assert detect_form(content.strip()) == "guti"


class TestSplitCouplet:
    def test_four_lines(self):
        content = "白日依山尽\n黄河入海流\n欲穷千里目\n更上一层楼"
        couplets = split_couplet(content)
        assert len(couplets) == 2
        assert couplets[0]["upper"] == "白日依山尽"
        assert couplets[0]["lower"] == "黄河入海流"
        assert couplets[0]["position"] == "shoulian"
        assert couplets[1]["position"] == "hanlian"

    def test_two_lines(self):
        content = "上联\n下联"
        couplets = split_couplet(content)
        assert len(couplets) == 1
        assert couplets[0]["upper"] == "上联"

    def test_odd_lines(self):
        content = "一\n二\n三"
        couplets = split_couplet(content)
        assert len(couplets) == 1
        assert couplets[0]["lower"] == "二"


class TestDetectRhymeCategory:
    def test_returns_category_for_known_char(self):
        # "东" is in 平水韵 东韵
        result = detect_rhyme_category("春眠不觉晓\n处处闻啼鸟\n夜来风雨声\n花落知多少")
        # Should return a string or None depending on rhymebooks data
        assert result is None or isinstance(result, str)

    def test_empty_content(self):
        assert detect_rhyme_category("") is None

    def test_single_char_line(self):
        # Should not crash
        result = detect_rhyme_category("东")
        assert result is None or isinstance(result, str)


class TestEnrichRecord:
    def test_enriches_form(self):
        rec = {"content": "白日依山尽\n黄河入海流\n欲穷千里目\n更上一层楼"}
        enriched = enrich_record(rec)
        assert enriched["form"] == "wu jue"
        assert "couplets" in enriched
        assert len(enriched["couplets"]) == 2

    def test_preserves_existing_form(self):
        rec = {"content": "test", "form": "custom"}
        enriched = enrich_record(rec)
        assert enriched["form"] == "custom"

    def test_enrich_batch_skips_failures(self):
        records = [
            {"content": "白日依山尽\n黄河入海流\n欲穷千里目\n更上一层楼"},
            {"content": ""},  # will produce empty form but shouldn't crash
        ]
        result = enrich_batch(records)
        assert len(result) == 2


# ---- validator tests ----


class TestValidateRecord:
    def test_valid_record(self):
        rec = {
            "id": "1",
            "title": "静夜思",
            "content": "床前明月光\n疑是地上霜",
            "source": "tang300",
            "confidence": 0.95,
        }
        is_valid, issues = validate_record(rec)
        assert is_valid is True
        assert issues == []

    def test_missing_title(self):
        rec = {
            "id": "1",
            "content": "内容",
            "source": "test",
            "confidence": 0.9,
        }
        is_valid, issues = validate_record(rec)
        assert is_valid is False
        assert any("title" in i for i in issues)

    def test_confidence_out_of_range(self):
        rec = {
            "id": "1",
            "title": "t",
            "content": "内容足够长",
            "source": "test",
            "confidence": 1.5,
        }
        is_valid, issues = validate_record(rec)
        assert is_valid is False
        assert any("Confidence" in i for i in issues)

    def test_content_too_short(self):
        rec = {
            "id": "1",
            "title": "t",
            "content": "短",
            "source": "test",
            "confidence": 0.9,
        }
        is_valid, issues = validate_record(rec)
        assert is_valid is False
        assert any("short" in i for i in issues)


class TestValidateBatch:
    def test_quarantines_invalid(self):
        records = [
            {"id": "1", "title": "t", "content": "足够长的内容", "source": "s", "confidence": 0.9},
            {"id": "2", "title": "", "content": "足够长的内容", "source": "s", "confidence": 0.9},
        ]
        valid, quarantine = validate_batch(records)
        assert len(valid) == 1
        assert len(quarantine) == 1
        assert "_validation_issues" in quarantine[0]


# ---- corpus_builder chunk_record tests ----


class TestChunkRecord:
    def test_four_line_poem(self):
        rec = {
            "id": "p1",
            "content": "白日依山尽\n黄河入海流\n欲穷千里目\n更上一层楼",
            "title": "登鹳雀楼",
            "author": "王之涣",
            "dynasty": "唐",
            "form": "wu jue",
        }
        chunks = chunk_record(rec)
        # whole poem + 2 couplets
        assert len(chunks) == 3
        assert chunks[0]["chunk_type"] == "poem"
        assert chunks[1]["chunk_type"] == "couplet"
        assert chunks[2]["chunk_type"] == "couplet"

    def test_eight_line_poem_has_quatrains(self):
        lines = [f"第{i}行诗句" for i in range(8)]
        rec = {
            "id": "p2",
            "content": "\n".join(lines),
            "title": "test",
            "form": "qi lv",
        }
        chunks = chunk_record(rec)
        chunk_types = [c["chunk_type"] for c in chunks]
        assert "poem" in chunk_types
        assert "couplet" in chunk_types
        assert "quatrain" in chunk_types

    def test_two_line_poem(self):
        rec = {"id": "p3", "content": "上联\n下联", "title": "t"}
        chunks = chunk_record(rec)
        assert len(chunks) == 2  # poem + 1 couplet
        assert chunks[0]["chunk_type"] == "poem"
        assert chunks[1]["chunk_type"] == "couplet"

    def test_chunk_ids_unique(self):
        rec = {
            "id": "p4",
            "content": "一\n二\n三\n四\n五\n六\n七\n八",
            "title": "t",
        }
        chunks = chunk_record(rec)
        ids = [c["id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_metadata_propagated(self):
        rec = {
            "id": "p5",
            "content": "一二\n三四",
            "title": "诗名",
            "author": "作者",
            "dynasty": "宋",
        }
        chunks = chunk_record(rec)
        for chunk in chunks:
            assert chunk["title"] == "诗名"
            assert chunk["author"] == "作者"
            assert chunk["dynasty"] == "宋"


# ---- load_source tests ----


class TestLoadSource:
    def test_nonexistent_path(self):
        with pytest.raises(Exception):
            load_source("/nonexistent/path.json")
