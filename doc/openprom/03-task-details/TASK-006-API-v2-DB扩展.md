# TASK-006 Phase 3 API v2 + DB 扩展

## 目标
扩展数据模型和 API 响应结构，支持逐字平仄/对仗展示、session 隔离、错误码体系。

## 涉及文件与改动点

### 1. openprom/infrastructure/database.py
- CoupletAnalysis 新增：`is_public`, `favorite`, `tags`, `request_id`
- 新增 `UserSession` 表
- 新增 `UserFeedback` 表
- 新增 `DailyBest` 表

### 2. openprom/api.py
- 新增 Pydantic 模型：`DimensionBreakdown`, `WordAnalysis`, `AnalysisDetail`, `ErrorResponse`
- `CoupletResponse` 扩展：`id`, `session_id`, `request_id`, `error_code`, `breakdown`, `detail`（Optional，向后兼容）
- 错误码体系：`PormErrorCode` 枚举 + `PormHTTPException`
- `history` 端点：支持筛选排序，返回 `total_count`

## 验收标准
- [ ] `pytest tests/test_integration.py` 全部通过
- [ ] `python -c "from openprom.api import CoupletResponse; print('ok')"` 正常
- [ ] 数据库新增表可通过 `get_db_manager().create_tables()` 创建
