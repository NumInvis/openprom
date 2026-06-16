# OpenPROM 变更日志

## v4.3.0 (2026-06-15)

### 架构重构：纯 AI 应用层

- 移除所有本地模型（`models/bert-base-chinese/`）与相关依赖
- 新增 `openprom/services/` 应用服务层，统一 LLM 调用、Tool 调用循环、流式输出
- 新增 `openprom/tools/` 工具层，将格律检测包装为 LLM 可调用的 Tool
- 新增 `openprom/routers/` 路由层，按资源拆分 API 端点
- 重写 `openprom/api.py` 为简洁的应用入口

### 新增六大能力

- **对联评分** `/api/v1/couplet/analyze`
- **对联生成** `/api/v1/couplet/generate`
- **对联补全** `/api/v1/couplet/complete`
- **律诗生成** `/api/v1/shi/generate`
- **律诗补全** `/api/v1/shi/complete`
- **格律检测** `/api/v1/meter/check`

### 工具链式 Agent

- 生成/补全类接口使用 LLM Tool Calling 闭环
- `check_meter` 作为必调工具，未通过格律检测不得交付
- 当韵脚/平仄无法下降时，主动调用 `get_rhyme_candidates` 提供候选韵字
- 支持多轮自修正（ configurable via `config/settings.yaml` ）

### 配置更新

- 默认 LLM 端点改为 `https://wincode.winning.com.cn/ai/v1/chat`
- 默认模型改为 `qwen3.7-plus`
- `config/settings.yaml` 新增 `tools`、`generation`、`agent` 配置段

### 前端升级

- 新增顶部 Tab 导航：评分、对联生成、对联补全、律诗生成、律诗补全、格律检测
- 生成/补全面板支持 SSE 流式展示生成与修正过程
- 保留原有墨韵新中式视觉风格

### 测试

- 新增 `tests/test_services.py` 服务层单元测试
- 新增 `tests/test_routers.py` API 路由测试
- 更新 `tests/test_couplet.py`、`tests/test_integration.py` 以适配新架构

---

## v4.2.0 (2026-04-24)

### 前端重构

- 全新"墨韵新中式" Luxury/Refined 视觉风格
- 引入书法字体（Ma Shan Zheng、ZCOOL XiaoWei）
- 宣纸纹理背景 + 渐变网格动画
- 玻璃拟态卡片（backdrop-filter）
- 暗色/亮色主题切换（localStorage 持久化）

### 后端优化

- 评分器请求级复用（单例模式，延迟初始化）
- OpenAI client 线程安全初始化（双检锁）
- MeterEngine 全局引擎线程安全（双检锁）
- 三仄尾/三平尾检查保留"中声"参与判断
- API 失败 fallback 从 50 分改为 30 分 + 错误标记

---

## v4.1.0 (2026-04-24)

- REST API 服务 (FastAPI)
- 数据持久化层 (SQLite + SQLAlchemy)
- Redis 缓存服务
- 结构化日志 (JSON 格式)
- Prometheus 监控指标
- 流式 API 输出 (SSE)
- Docker 部署支持

---

## v4.0.0 (2026)

- 双 API 评分系统
- BERT 语义相似度计算
- 马鞍工程控制
- TUI 界面
