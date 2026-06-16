# TASK-003 测试说明 — 前端止血

## 测试范围

验证前端止血修改的代码正确性和回归安全性。

## 测试用例

| 用例编号 | 用例名称 | 测试方法 | 预期结果 |
|----------|----------|----------|----------|
| TC-001 | BERT 引用清零 | grep 扫描 `bertScore`、`qwen_analysis`、`cosine_similarity` | 无匹配 |
| TC-002 | 假进度删除确认 | grep 扫描 `setInterval` | 无匹配 |
| TC-003 | Session 模块存在 | grep 扫描 `Session.getId`、`X-Session-ID` | 有匹配且语法正确 |
| TC-004 | 主题默认 light | grep 扫描 `data-theme` | `data-theme="light"` |
| TC-005 | XSS 修复确认 | grep 扫描 `warningsList.innerHTML =`（非空赋值） | 无危险匹配 |
| TC-006 | 后端集成回归 | `pytest tests/test_integration.py` | 8 passed |

## 备注

- 前端交互测试（点击、输入、渲染）依赖浏览器环境，计划在 TASK-005 中通过 Playwright 覆盖
- 本次以代码审查 + 后端回归测试为主
