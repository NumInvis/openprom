"""真实接口测试：逐个调用 OpenPROM API 并验证返回。"""

import json
import sys
import time
import traceback
from typing import Any, Dict

import requests

BASE = "http://localhost:8000"
RESULTS: Dict[str, Dict[str, Any]] = {}


def call(name: str, method: str, path: str, payload=None, headers=None, timeout=120, stream=False):
    url = f"{BASE}{path}"
    start = time.time()
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=timeout, stream=stream)
        else:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout, stream=stream)
        latency = round((time.time() - start) * 1000, 2)
        if stream:
            # consume SSE body and keep last line as JSON if possible
            lines = []
            for line in r.iter_lines(decode_unicode=True):
                if line:
                    lines.append(line)
            return {"status": r.status_code, "latency_ms": latency, "lines": lines}
        try:
            data = r.json()
        except Exception:
            data = r.text
        return {"status": r.status_code, "latency_ms": latency, "data": data}
    except Exception as e:
        return {"status": -1, "latency_ms": round((time.time() - start) * 1000, 2), "error": str(e), "trace": traceback.format_exc()}


def ok(name: str, res: Dict[str, Any]) -> bool:
    passed = res.get("status") == 200 and "error" not in res
    RESULTS[name] = {"passed": passed, **res}
    return passed


def main():
    print("=" * 60)
    print("OpenPROM 真实接口测试开始")
    print("=" * 60)

    # 1. health
    res = call("health", "GET", "/health")
    ok("health", res)
    print(f"[health] status={res.get('status')} latency={res.get('latency_ms')}ms")

    # 2. meter list
    res = call("meter_list_shi", "GET", "/api/v1/meter/list?meter_type=shi")
    ok("meter_list_shi", res)
    print(f"[meter_list_shi] status={res.get('status')} patterns={len(res.get('data', {}).get('patterns', []))}")

    res = call("meter_list_ci", "GET", "/api/v1/meter/list?meter_type=ci")
    ok("meter_list_ci", res)
    print(f"[meter_list_ci] status={res.get('status')} patterns={len(res.get('data', {}).get('patterns', []))}")

    # 3. meter check couplet
    res = call("meter_check_couplet", "POST", "/api/v1/meter/check", {
        "text": "春风化雨润桃李\n秋月凝霜照柏松",
        "meter_type": "couplet"
    })
    ok("meter_check_couplet", res)
    print(f"[meter_check_couplet] status={res.get('status')} compliant={res.get('data', {}).get('is_compliant')}")

    # 4. meter check shi (wujue)
    res = call("meter_check_shi", "POST", "/api/v1/meter/check", {
        "text": "床前明月光\n疑是地上霜\n举头望明月\n低头思故乡",
        "meter_type": "shi"
    })
    ok("meter_check_shi", res)
    print(f"[meter_check_shi] status={res.get('status')} matched={len(res.get('data', {}).get('matched_meters', []))}")

    # 5. couplet analyze (真实 LLM)
    session_id = f"test-session-{int(time.time())}"
    res = call("couplet_analyze", "POST", "/api/v1/couplet/analyze", {
        "upper": "春风化雨润桃李",
        "lower": "秋月凝霜照柏松",
        "enable_cache": False,
        "stream": False
    }, headers={"X-Session-ID": session_id})
    ok("couplet_analyze", res)
    print(f"[couplet_analyze] status={res.get('status')} total_score={res.get('data', {}).get('total_score')} grade={res.get('data', {}).get('grade')}")

    # 6. couplet analyze length mismatch
    res = call("couplet_analyze_mismatch", "POST", "/api/v1/couplet/analyze", {
        "upper": "春风化雨润桃李",
        "lower": "秋月凝霜",
        "enable_cache": False,
        "stream": False
    })
    ok_mismatch = res.get("status") == 400
    RESULTS["couplet_analyze_mismatch"] = {"passed": ok_mismatch, **res}
    print(f"[couplet_analyze_mismatch] status={res.get('status')} (expected 400)")

    # 7. couplet generate (真实 LLM)
    res = call("couplet_generate", "POST", "/api/v1/couplet/generate", {
        "prompt": "写一副关于春天的五言对联",
        "length": 5,
        "stream": False,
        "max_revision_rounds": 2
    })
    ok("couplet_generate", res)
    print(f"[couplet_generate] status={res.get('status')} content={res.get('data', {}).get('content', '')[:50]}")

    # 8. couplet complete (真实 LLM)
    res = call("couplet_complete", "POST", "/api/v1/couplet/complete", {
        "prompt": "上联：春风化雨润桃李",
        "length": 7,
        "stream": False,
        "max_revision_rounds": 2
    })
    ok("couplet_complete", res)
    print(f"[couplet_complete] status={res.get('status')} content={res.get('data', {}).get('content', '')[:50]}")

    # 9. couplet history
    res = call("couplet_history", "GET", "/api/v1/couplet/history", headers={"X-Session-ID": session_id})
    ok("couplet_history", res)
    print(f"[couplet_history] status={res.get('status')} items={len(res.get('data', {}).get('items', []))}")

    # 10. couplet statistics
    res = call("couplet_statistics", "GET", "/api/v1/couplet/statistics")
    ok("couplet_statistics", res)
    print(f"[couplet_statistics] status={res.get('status')} total={res.get('data', {}).get('total_analyses')}")

    # 11. shi generate (真实 LLM)
    res = call("shi_generate", "POST", "/api/v1/shi/generate", {
        "prompt": "以春山为主题写一首五言绝句",
        "form": "五绝",
        "stream": False,
        "max_revision_rounds": 2
    })
    ok("shi_generate", res)
    print(f"[shi_generate] status={res.get('status')} content={res.get('data', {}).get('content', '')[:60]}")

    # 12. shi complete (真实 LLM)
    res = call("shi_complete", "POST", "/api/v1/shi/complete", {
        "prompt": "春眠不觉晓，处处闻啼鸟。",
        "form": "五绝",
        "stream": False,
        "max_revision_rounds": 2
    })
    ok("shi_complete", res)
    print(f"[shi_complete] status={res.get('status')} content={res.get('data', {}).get('content', '')[:60]}")

    # 13. knowledge stats
    res = call("knowledge_stats", "GET", "/api/v1/knowledge/stats")
    ok("knowledge_stats", res)
    print(f"[knowledge_stats] status={res.get('status')} enabled={res.get('data', {}).get('enabled')} vector_size={res.get('data', {}).get('vector_store_size')}")

    # 14. knowledge search
    res = call("knowledge_search", "POST", "/api/v1/knowledge/search", {
        "query": "春山",
        "top_k": 3,
        "task_type": "general"
    })
    ok("knowledge_search", res)
    print(f"[knowledge_search] status={res.get('status')} results={len(res.get('data', {}).get('results', []))}")

    # 15. tasks list
    res = call("tasks_list", "GET", "/api/v1/tasks/")
    ok("tasks_list", res)
    print(f"[tasks_list] status={res.get('status')} tasks={len(res.get('data', {}).get('tasks', []))}")

    # 16. tasks run (真实 LLM)
    res = call("tasks_run", "POST", "/api/v1/tasks/run", {
        "task_name": "generate_couplet",
        "user_prompt": "写一副关于读书的对联，每联七字",
        "max_rounds": 2
    })
    ok("tasks_run", res)
    print(f"[tasks_run] status={res.get('status')} content={res.get('data', {}).get('content', '')[:50]}")

    # 17. metrics
    res = call("metrics", "GET", "/metrics")
    ok("metrics", res)
    print(f"[metrics] status={res.get('status')} size={len(res.get('data', '') if isinstance(res.get('data'), str) else '')}")

    # 18. root / static
    res = call("root", "GET", "/")
    ok("root", res)
    print(f"[root] status={res.get('status')} content-type={res.get('data', '')[:30] if isinstance(res.get('data'), str) else 'json'}")

    res = call("static", "GET", "/static/index.html")
    ok("static", res)
    print(f"[static] status={res.get('status')} size={len(res.get('data', '') if isinstance(res.get('data'), str) else '')}")

    # Summary
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    passed = 0
    failed = []
    for name, r in RESULTS.items():
        if r.get("passed"):
            passed += 1
        else:
            failed.append(name)
            print(f"FAIL {name}: status={r.get('status')} error={r.get('error')} data={r.get('data')}")
    total = len(RESULTS)
    print(f"通过: {passed}/{total}")
    if failed:
        print(f"失败: {', '.join(failed)}")
    print("=" * 60)
    with open("scripts/manual_api_test_results.json", "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)
    print("详细结果已保存到 scripts/manual_api_test_results.json")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
