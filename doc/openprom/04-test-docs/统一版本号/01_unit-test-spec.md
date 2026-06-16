# 单元测试说明 - 全任务集成验证

## 测试范围
- 任务描述：验证所有 6 个 TASK 的修复效果
- 测试类型：单元测试

## 测试用例

| 用例ID | 用例描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
|--------|----------|----------|----------|----------|--------|
| TC-001 | 版本号统一 | import openprom | `openprom.__version__` | 返回 "4.2.0" | P0 |
| TC-002 | CoupletResponse cached 字段 | api.py import | 创建 CoupletResponse(cached=False/True) | cached 字段可读写 | P0 |
| TC-003 | cache delete 同步 expiry | CacheService 实例 | set 3 key, delete 1, set 新 key | 无 KeyError | P0 |
| TC-004 | cache clear 同步 expiry | CacheService 实例 | set keys, clear prefix | _memory_expiry 为空 | P0 |
| TC-005 | database expunge | DatabaseManager | get_couplet_history, to_dict() | 无 DetachedInstanceError | P0 |
| TC-006 | 弃用代码清除 | import openprom | `import openprom` | 不崩溃, 无 PormTUI/launch_tui | P1 |
| TC-007 | YAML 提示文件解析 | yaml.safe_load | load all prompts/*.yaml | 全部通过 | P0 |
| TC-008 | ruff lint | ruff check | `ruff check openprom/` | All checks passed | P0 |

## 验证检查项
- [√] 所有测试用例已通过