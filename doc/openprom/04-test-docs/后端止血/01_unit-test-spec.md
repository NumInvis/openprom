# TASK-002 测试说明 — 后端止血

## 测试范围

验证后端止血修改未破坏现有功能，且致命缺陷已修复。

## 测试用例

| 用例编号 | 用例名称 | 测试方法 | 预期结果 |
|----------|----------|----------|----------|
| TC-001 | SaddleEngineering 配置读取 | 实例化后检查属性 | `strict_mode=False`, `max_violations=3` |
| TC-002 | base_analyzer 分数分离 | `analyze_formal("春风", "秋雨")` | `formal_score ≠ pingze_score`，均在 [0,1] |
| TC-003 | API 响应分数缩放 | `_score_to_response(DualAPIScore(...))` | 四维度分数为输入值 `*100` |
| TC-004 | CORS 多域名配置 | 设置 `OPENPROM_CORS_ORIGINS` 后调用 `get_cors_origins()` | 返回分割后的域名列表 |
| TC-005 | DB 延迟初始化 | `from openprom.infrastructure.database import get_db_manager; get_db_manager()` | 正常返回实例，不抛异常 |
| TC-006 | 集成测试回归 | `pytest tests/test_integration.py -v` | 8 个测试全部通过 |

## 备注

- 未测试真实 LLM 评分路径（需 API Key）
- 未测试 session_id 过滤的业务逻辑（需前端配合）
