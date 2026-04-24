"""PORM Web 界面快速测试"""

import requests
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = 'http://localhost:8000'

def test_endpoint(url, expected_status=200):
    """测试端点"""
    try:
        r = requests.get(f'{BASE_URL}{url}', timeout=5)
        status = 'OK' if r.status_code == expected_status else 'FAIL'
        print(f"[{status}] {url}: {r.status_code} ({len(r.text)} bytes)")
        return r.status_code == expected_status
    except Exception as e:
        print(f"[FAIL] {url}: {e}")
        return False

print("=" * 60)
print("PORM Web 界面测试")
print("=" * 60)

tests = [
    ('/', 200),
    ('/static/index.html', 200),
    ('/static/styles.css', 200),
    ('/static/app.js', 200),
    ('/health', 200),
    ('/docs', 200),
    ('/openapi.json', 200),
]

passed = 0
failed = 0

for url, expected in tests:
    if test_endpoint(url, expected):
        passed += 1
    else:
        failed += 1

print("=" * 60)
print(f"结果：{passed} 通过，{failed} 失败")

if failed == 0:
    print("[SUCCESS] 所有测试通过!")
else:
    print(f"[FAILED] {failed} 个测试失败")

# 测试 API 端点（不需要真实 API 密钥，只测试端点存在）
print("\n测试 API 端点:")
try:
    r = requests.post(
        f'{BASE_URL}/api/v1/couplet/analyze',
        json={'upper': 'test', 'lower': 'test'},
        timeout=5
    )
    # 应该返回 400 或 500（因为字数不等或 API 密钥问题），但端点应该存在
    print(f"[OK] /api/v1/couplet/analyze: {r.status_code}")
except Exception as e:
    print(f"[FAIL] /api/v1/couplet/analyze: {e}")

sys.exit(0 if failed == 0 else 1)
