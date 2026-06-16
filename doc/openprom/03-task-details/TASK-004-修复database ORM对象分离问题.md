# TASK-004 修复database.py ORM对象分离问题

## 任务描述
`get_couplet_history` 和 `search_couplets` 返回 ORM 对象但在 session 关闭后访问属性会触发 DetachedInstanceError。`save_couplet_analysis` 和 `get_couplet_analysis` 正确使用了 `session.expunge()`，但这两个查询方法没有。

## 技术要求
- 在 `get_couplet_history` 和 `search_couplets` 中，对返回的每个 ORM 对象调用 `session.expunge(record)` 后再返回
- 或者在 session 上下文内直接转换为 dict 后返回

## 实现步骤
1. 读取 `openprom/infrastructure/database.py` 的 `get_couplet_history` 和 `search_couplets` 方法
2. 在返回 ORM 对象列表前，对每个对象调用 `session.expunge()`
3. 确保所有查询方法都正确处理 session 生命周期

## 涉及文件
- `openprom/infrastructure/database.py`

## 验收标准
- get_couplet_history 返回的对象在 session 关闭后仍可访问属性
- search_couplets 返回的对象在 session 关闭后仍可访问属性
- 不再出现 DetachedInstanceError