# TASK-004 测试说明 — 结构加固

## 测试范围

验证结构加固修改的代码正确性和回归安全性。

## 测试用例

| 用例编号 | 用例名称 | 测试方法 | 预期结果 |
|----------|----------|----------|----------|
| TC-001 | cache 延迟初始化 | `from openprom.infrastructure.cache import get_cache_service; get_cache_service()` | 正常返回实例 |
| TC-002 | json_parser 对象解析 | `parse_llm_json_response('{"key": "value"}')` | `{'key': 'value'}` |
| TC-003 | json_parser 数组解析 | `parse_llm_json_response('[1,2,3]')` | `[1, 2, 3]` |
| TC-004 | json_parser 单引号修复 | `parse_llm_json_response("{'key': 'value'}")` | `{'key': 'value'}` |
| TC-005 | json_parser 嵌入文本 | `parse_llm_json_response('text {"a":1} text')` | `{'a': 1}` |
| TC-006 | 集成测试回归 | `pytest tests/test_integration.py` | 8 passed |

## 备注

- json_parser 测试使用临时 Python 脚本执行，已删除
