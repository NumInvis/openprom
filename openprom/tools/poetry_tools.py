"""Unified poetry tool implementations.

Only 4 tools, each a Swiss-army knife:
1. check_meter — all 格律 operations (action-dispatched)
2. retrieve_poetry — all 古诗词检索 (mode-dispatched)
3. web_search — the entire internet
4. self_critique — self-evaluation framework

No hardcoded "knowledge" — the LLM already knows Chinese poetry better
than any small dict.  Tools only provide what the LLM *cannot* reliably
compute: structured rhymebook/meter data and the entire internet.
"""

import logging
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from openprom.data.loader import RhymeBook, MeterPattern

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. check_meter — unified 格律 tool (action-dispatched)
# ---------------------------------------------------------------------------


def check_meter_unified(
    action: str = "check",
    text: str = "",
    meter_type: str = "shi",
    pattern_name: Optional[str] = None,
    strict: bool = False,
    char: str = "",
    tone: Optional[str] = None,
    count: int = 8,
    book: str = "平水韵",
    form: str = "",
    tone_pattern: Optional[str] = None,
    rule: str = "",
) -> Dict[str, Any]:
    """格律工具：检测格律、查韵脚候选、查字声韵、查格律谱、解释规则。"""
    from openprom.services import meter_tool

    if action == "check":
        if not text:
            return {"error": "action=check 需要 text 参数"}
        return meter_tool.check_meter(
            text=text, meter_type=meter_type, pattern_name=pattern_name, strict=strict
        )

    if action == "rhyme_candidates":
        if not char:
            return {"error": "action=rhyme_candidates 需要 char 参数"}
        if not tone:
            return {"error": "action=rhyme_candidates 需要 tone 参数"}
        candidates = meter_tool.get_rhyme_candidates(char=char, tone=tone, count=count)
        return {"char": char, "tone": tone, "candidates": candidates}

    if action == "char_phonetics":
        if not char:
            return {"error": "action=char_phonetics 需要 char 参数"}
        return _char_phonetics(char, book)

    if action == "meter_template":
        if not form:
            return {"error": "action=meter_template 需要 form 参数"}
        return _meter_template_lookup(form, tone_pattern)

    if action == "explain_rule":
        if not rule:
            return {"error": "action=explain_rule 需要 rule 参数"}
        explanation = meter_tool.explain_rule(rule=rule)
        return {"rule": rule, "explanation": explanation}

    return {"error": f"未知 action: {action}"}


def _char_phonetics(char: str, book: str = "平水韵") -> Dict[str, Any]:
    """查询汉字在韵书中的声韵信息。"""
    try:
        rb = RhymeBook.get()
        tone_val = rb.get_tone(char, book=book)
        category = rb.get_rhyme_category(char, book=book)
        if tone_val is None and category is None:
            return {"char": char, "found": False, "message": f"韵书《{book}》中未收录此字"}
        tone_name = {1: "平声", -1: "仄声", None: "未知"}.get(tone_val, "未知")
        return {
            "char": char,
            "found": True,
            "book": book,
            "tone": tone_name,
            "tone_code": tone_val,
            "rhyme_category": category or "未归类",
        }
    except Exception as e:
        logger.debug("char_phonetics failed: %s", e)
        return {"char": char, "found": False, "error": str(e)}


def _meter_template_lookup(form: str, tone_pattern: Optional[str] = None) -> Dict[str, Any]:
    """查询诗体的完整格律谱。"""
    try:
        mp = MeterPattern.get()
        names = mp.search_shi(form)

        if tone_pattern:
            tp_label = "平起" if tone_pattern == "ping" else "仄起"
            names = [n for n in names if tp_label in n]

        matched = []
        for name in names:
            pattern = mp.get_shi_pattern(name)
            if pattern is None:
                continue
            tone_names = []
            for line in pattern:
                row = []
                for t in line:
                    if t == 1:
                        row.append("平")
                    elif t == -1:
                        row.append("仄")
                    elif t == 0:
                        row.append("可")
                    elif t == 3:
                        row.append("平!")
                    elif t == 4:
                        row.append("仄!")
                    else:
                        row.append("?")
                tone_names.append("".join(row))
            matched.append({"name": name, "pattern": ", ".join(tone_names)})

        if not matched:
            return {
                "form": form,
                "found": False,
                "available_forms": mp.list_shi_patterns()[:20],
            }

        return {"form": form, "found": True, "count": len(matched), "patterns": matched}
    except Exception as e:
        logger.debug("meter_template_lookup failed: %s", e)
        return {"form": form, "found": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 2. retrieve_poetry — unified 古诗词检索 (mode-dispatched)
# ---------------------------------------------------------------------------


def retrieve_poetry(
    theme: str,
    mode: str = "poems",
    form: Optional[str] = None,
    dynasty: Optional[str] = None,
    top_k: int = 3,
) -> Dict[str, Any]:
    """检索古诗词库（几十万首）。"""
    try:
        from openprom.services.hermes.retriever import get_hermes_retriever
        from openprom.services.hermes.skills import (
            ClassicPoetrySkill,
            ImagerySkill,
            LineInspirationSkill,
        )

        retriever = get_hermes_retriever()

        if mode == "poems":
            skill = ClassicPoetrySkill(retriever)
            results = skill.invoke(theme=theme, form=form, dynasty=dynasty, top_k=top_k)
            return {"mode": "poems", "theme": theme, "count": len(results), "results": results}

        if mode == "imagery":
            skill = ImagerySkill(retriever)
            results = skill.invoke(theme=theme, form=form, top_k=top_k)
            return {"mode": "imagery", "theme": theme, "count": len(results), "results": results}

        if mode == "lines":
            skill = LineInspirationSkill(retriever)
            results = skill.invoke(theme=theme, top_k=top_k)
            return {"mode": "lines", "theme": theme, "count": len(results), "results": results}

        return {"error": f"未知 mode: {mode}"}
    except Exception as e:
        logger.debug("retrieve_poetry failed: %s", e)
        return {"theme": theme, "mode": mode, "found": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 3. web_search — the entire internet
# ---------------------------------------------------------------------------

_DDG_URL = "https://html.duckduckgo.com/html/"


def web_search(query: str, num_results: int = 5) -> Dict[str, Any]:
    """通用网络搜索（DuckDuckGo HTML）。整个互联网信息可用。"""
    try:
        data = urllib.parse.urlencode({"q": query, "kl": "cn-zh"}).encode("utf-8")
        req = urllib.request.Request(
            _DDG_URL,
            data=data,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OpenPROM/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        results = _parse_ddg_html(html, num_results)
        if not results:
            return {"query": query, "found": False, "message": "未找到相关结果"}

        return {"query": query, "found": True, "count": len(results), "results": results}
    except Exception as e:
        logger.debug("web_search failed: %s", e)
        return {"query": query, "found": False, "error": str(e)}


def _parse_ddg_html(html: str, limit: int) -> List[Dict[str, str]]:
    """从 DuckDuckGo HTML 页面提取搜索结果。"""
    results = []
    for m in re.finditer(
        r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    ):
        url = m.group(1)
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        snippet = re.sub(r"<[^>]+>", "", m.group(3)).strip()
        if title:
            results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= limit:
            break
    return results


# ---------------------------------------------------------------------------
# 4. self_critique — self-evaluation framework
# ---------------------------------------------------------------------------


def self_critique(
    work: str,
    form: str = "",
    dimensions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """自评反思：返回结构化评价框架，引导LLM自我审视。"""
    all_dims = {
        "imagery": {
            "label": "意象",
            "questions": [
                "意象是否新鲜独到，还是陈词滥调？",
                "意象之间是否构成有机的意境，而非简单堆砌？",
                "是否有让人眼前一亮的陌生化表达？",
            ],
        },
        "diction": {
            "label": "炼字",
            "questions": [
                "每个字是否不可替代？有无更精准的字？",
                "有无口水化、现代白话化的表达？",
                "动词是否有力？形容词是否恰到好处？",
            ],
        },
        "structure": {
            "label": "章法",
            "questions": [
                "起承转合是否自然流转？",
                "上下联/各联之间气韵是否贯通？",
                "有无板滞之处？有无散漫之处？",
            ],
        },
        "emotion": {
            "label": "情致",
            "questions": [
                "情感是否真挚动人，而非无病呻吟？",
                "是否做到含蓄蕴藉，言有尽而意无穷？",
                "情感与意象是否水乳交融？",
            ],
        },
        "originality": {
            "label": "独创",
            "questions": [
                "在同类题材中是否有新意？",
                "是否避开了常见的构思套路？",
                "有无属于自己的独特发现？",
            ],
        },
        "technique": {
            "label": "技巧",
            "questions": [
                "对仗是否工稳而不板滞？",
                "用典是否自然无痕？",
                "声韵是否和谐悦耳？",
            ],
        },
    }

    selected = dimensions or list(all_dims.keys())
    framework = []
    for dim in selected:
        if dim in all_dims:
            d = all_dims[dim]
            framework.append({"dimension": d["label"], "key": dim, "questions": d["questions"]})

    return {
        "work": work[:100] + "..." if len(work) > 100 else work,
        "form": form or "未指定",
        "framework": framework,
        "instruction": (
            "请以上述维度逐条审视你的作品，找出不足之处并修正。"
            "不必每个维度都改，但每个维度都要认真思考。"
        ),
    }
