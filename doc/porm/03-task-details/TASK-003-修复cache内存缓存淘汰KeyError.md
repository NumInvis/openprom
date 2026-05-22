# TASK-003 修复cache.py内存缓存淘汰KeyError

## 任务描述
`cache.py` 的 `delete()` 和 `clear()` 方法只清除 `_memory_cache` 但不清除 `_memory_expiry`，导致 LRU 淘汰时从 `_memory_expiry` 找到的 oldest_key 在 `_memory_cache` 中已不存在，抛出 KeyError。

## 技术要求
- `delete()` 方法同时删除 `_memory_expiry` 中对应条目
- `clear()` 方法同时清空 `_memory_expiry`
- LRU 淘汰路径添加安全检查

## 实现步骤
1. 修改 `delete()` 方法：在删除 `_memory_cache[key]` 后，同时 `del self._memory_expiry[key]`（带 KeyError 忽略）
2. 修改 `clear()` 方法：同时 `self._memory_expiry.clear()`
3. 修改 `set()` 的 LRU 淘汰逻辑：检查 oldest_key 是否仍在 `_memory_cache` 中

## 涉及文件
- `porm/infrastructure/cache.py`

## 验收标准
- delete() 后 _memory_expiry 同步清除
- clear() 后 _memory_expiry 同步清空
- LRU 淘汰不再抛 KeyError