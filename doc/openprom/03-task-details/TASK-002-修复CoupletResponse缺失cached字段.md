# TASK-002 修复CoupletResponse缺失cached字段

## 任务描述
`CoupletResponse` Pydantic model 没有 `cached` 字段，导致 cache-hit 时设置的 `cached=True` 被静默丢弃，API 客户端无法区分缓存命中与新计算结果。

## 技术要求
- 在 `CoupletResponse` 中添加 `cached: Optional[bool] = None` 字段
- 在正常评分响应中默认返回 `cached=False`
- 在缓存命中响应中返回 `cached=True`

## 实现步骤
1. 修改 `openprom/api.py` 的 `CoupletResponse` class，添加 `cached: Optional[bool] = None`
2. 修改 `_score_to_response()` 函数，默认设置 `cached=False`
3. 修改缓存命中逻辑，正确传递 `cached=True`

## 涉及文件
- `openprom/api.py`

## 验收标准
- CoupletResponse 包含 cached 字段
- 缓存命中时响应中 cached=True
- 非缓存命中时响应中 cached=False