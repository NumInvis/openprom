# TASK-005 修复api.py缓存条件顺序与清理无用导入

## 任务描述
1. api.py 中缓存查找在 `enable_cache=False` 时仍执行 Redis/内存查询，浪费资源并增加统计偏差
2. `Depends` 从 fastapi 导入但从未使用

## 技术要求
- 将 cache_service.get() 调用移入 `enable_cache` 条件内
- 移除未使用的 `Depends` 导入

## 实现步骤
1. 修改 `analyze_couplet` 函数中的缓存逻辑：将 `cache_service.get()` 移到 `if request.enable_cache:` 条件内
2. 删除 `from fastapi import Depends` 导入

## 涉及文件
- `porm/api.py`

## 验收标准
- enable_cache=False 时不执行任何缓存查询
- Depends 导入已移除