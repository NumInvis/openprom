# TASK-001 测试说明 — 前置清理

## 测试范围

本次任务为纯清理操作（删除僵尸模块、修改 __init__.py 导出），无新增业务逻辑。测试重点是**回归验证**：确认删除操作未破坏项目导入链与测试框架。

## 测试用例

| 用例编号 | 用例名称 | 测试方法 | 预期结果 |
|----------|----------|----------|----------|
| TC-001 | 根包导入测试 | `python -c "import openprom"` | 正常执行，不抛 ImportError |
| TC-002 | 测试收集测试 | `pytest tests/ --co -q` | 收集到 9 个测试用例，无报错 |
| TC-003 | 僵尸引用扫描 | `grep -r` 扫描 `classify_similarity_level`、`from openprom.utils.config`、`from openprom.core import` | 全项目无匹配结果 |

## 备注

- 未运行完整 pytest 执行（`test_couplet.py` 需要真实 API Key，`test_web_interface.py` 需要浏览器环境）
- 本次仅需验证测试框架可正常收集用例即可
