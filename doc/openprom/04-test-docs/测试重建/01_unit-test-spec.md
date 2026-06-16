# TASK-005 测试说明 — 测试重建

## 测试范围

验证测试架构重建后，所有测试用例可正确收集、执行和跳过。

## 测试用例

| 用例编号 | 用例名称 | 测试方法 | 预期结果 |
|----------|----------|----------|----------|
| TC-001 | 测试收集 | `pytest tests/ --co -q` | 收集到 10 个测试用例 |
| TC-002 | 集成测试执行 | `pytest tests/test_integration.py -v` | 8 passed |
| TC-003 | couplet 测试 skip | `pytest tests/test_couplet.py -v` | 1 skipped（无 API Key） |
| TC-004 | web 测试 skip | `pytest tests/test_web_interface.py -v` | 1 skipped（服务器未启动） |
| TC-005 | 无 ReturnNotNone 警告 | 检查 pytest 输出 | 无 `PytestReturnNotNoneWarning` |

## 备注

- `test_couplet_scoring` 需要 `OPENPROM_API_KEY` 环境变量才会执行
- `test_web_interface` 需要服务器运行在 `localhost:8000` 才会执行
