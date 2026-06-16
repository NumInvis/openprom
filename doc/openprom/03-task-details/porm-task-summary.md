# OpenPROM 重构任务汇总

| 任务编号 | 任务名称 | 状态 | 优先级 |
|----------|----------|------|--------|
| TASK-001 | Phase 0 前置清理（删除僵尸模块、残留 pyc） | 已完成 | P0 |
| TASK-002 | Phase 1 后端止血（严格模式、分数修复、CORS、session 隔离） | 已完成 | P0 |
| TASK-003 | Phase 1 前端止血（BERT 清理、假进度、XSS、session_id） | 已完成 | P0 |
| TASK-004 | Phase 2 结构加固（统一配置、json_parser 重写、延迟初始化） | 已完成 | P1 |
| TASK-005 | Phase 2 测试重建（pytest 化、内存隔离、headless CI） | 已完成 | P1 |
| TASK-006 | Phase 3 API v2 + DB 扩展（Schema 扩展、错误码、新增表） | 已完成 | P1 |
| TASK-007 | Phase 3 数据流改造（word_analysis 透传、逐字平仄） | 已完成 | P1 |
| TASK-008 | Phase 3 前端改造（逐字平仄可视化、错误映射、主题） | 已完成 | P1 |
| TASK-009 | Phase 4 限界上下文拆分（Clean Architecture、DI 容器） | 未开始 | P2 |
| TASK-010 | Phase 5 质量闭环（新增测试、文档更新、Docker 验证） | 未开始 | P2 |
