# TASK-006 测试说明 — API v2 + DB 扩展

## 测试范围

验证数据库模型扩展和 API Schema 扩展无回归。

## 测试用例

| 用例编号 | 用例名称 | 测试方法 | 预期结果 |
|----------|----------|----------|----------|
| TC-001 | 数据库表创建 | `get_db_manager().create_tables()` | 无异常，新表可创建 |
| TC-002 | API 模型导入 | `from openprom.api import CoupletResponse, DimensionBreakdown` | 正常导入 |
| TC-003 | 集成测试回归 | `pytest tests/test_integration.py -v` | 8 passed |
| TC-004 | 错误码体系 | `from openprom.api import PormErrorCode; PormErrorCode.LENGTH_MISMATCH` | 值为 "COUPLET_001" |

## 备注

- 新表字段的业务逻辑测试（如 history 筛选）在 TASK-007 中补充
