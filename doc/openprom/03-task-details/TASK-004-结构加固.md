# TASK-004 Phase 2 结构加固

## 目标
消除代码坏味道，统一配置入口，修复 json_parser 缺陷，拆除 cache 模块级实例化。

## 涉及文件与改动点

### 1. openprom/utils/env_config.py
- 版本号 `4.1.0` → `4.2.0`
- 新增 `get_config_value(key: str, type_: type, default: Any)` 统一配置入口

### 2. openprom/utils/json_parser.py
- `_extract_json_string`：修复括号匹配逻辑（支持 `[` 开头，不匹配时正确丢弃层级）
- `_convert_single_quotes`：改为简单首尾去除，避免状态机错误

### 3. openprom/infrastructure/cache.py
- 删除模块级 `cache_service = CacheService()`
- 新增 `get_cache_service()` 工厂函数

### 4. openprom/api.py
- 替换 `cache_service` 导入和引用为 `get_cache_service()`

## 验收标准
- [ ] `get_config_value("api_key", str, "")` 正常返回
- [ ] `json_parser` 能正确提取 `{'key': 'value'}` 和 `[1,2,3]` 包裹的 JSON
- [ ] `get_cache_service()` 返回实例不抛异常
- [ ] `pytest tests/test_integration.py` 8 个测试全部通过
