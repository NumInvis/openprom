# OpenPROM - 诗词 AI 助手

版本：4.3.0  
模型：your-model-name  
LLM 端点：`https://your-llm-gateway.example.com/ai/v1`  
许可证：MIT

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## 简介

OpenPROM 是基于 **LLM + 规则引擎** 的纯 AI 应用层中文诗词助手，采用工具链（Tool Calling）+ Agentic Loop 架构。

### 核心特性

- ✅ **六大能力**: 对联评分、对联生成、对联补全、律诗生成、律诗补全、格律检测
- ✅ **工具链式 Agent**: 格律检测作为 LLM Tool，生成/补全必须通过格律检测才能交付
- ✅ **自动韵字提示**: 当格律无法自行修正时，主动提供同韵部候选字给 LLM
- ✅ **四层评分架构**: 形式合规 (30%) + 对仗技术 (30%) + 艺术表现 (30%) + AI 印象 (10%)
- ✅ **双 API 评分系统**: 第一印象评估 + 深度技法分析
- ✅ **马鞍工程控制**: 输入层 + 过程层 + 输出层 + 决策层全方位质量控制
- ✅ **REST API 服务**: FastAPI 驱动，支持流式输出 (SSE)
- ✅ **数据持久化**: SQLite/PostgreSQL 支持，历史记录可追溯
- ✅ **Redis 缓存**: 智能缓存层，支持内存降级
- ✅ **可观测性**: Prometheus 监控 + 结构化日志
- ✅ **Docker 部署**: 一键启动，包含完整监控栈
- ✅ **主题切换**: 暗色/亮色模式
- ✅ **评鉴历史**: 本地存储历史记录

---

## 快速开始

### 1. 安装

```bash
git clone https://github.com/yourusername/openprom.git
cd openprom
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入 OPENPROM_API_KEY
```

### 3. 启动服务

```bash
# 方式 1: Web 界面 + API 服务 (推荐)
python -m openprom.api

# 方式 2: Docker Compose (推荐)
docker-compose up -d
```

### 4. 访问 Web 界面

打开浏览器访问：

- **Web 界面**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

### ⚠️ 弃用通知

CLI 和 TUI 模式已弃用，请迁移到 Web 界面使用。

---

## 使用方式

### 🌐 Web 界面

启动服务后，打开浏览器访问 **http://localhost:8000**

Web 界面提供:
- ✨ 墨韵新中式视觉设计（书法字体 + 宣纸纹理）
- 📊 直观的分数展示（动画圆环 + 维度卡片）
- 💬 详细的评鉴分析
- 📤 一键分享结果
- 🌓 暗色/亮色主题切换
- 📜 评鉴历史记录

### 🔌 REST API

#### 对联评分（标准模式）

```bash
curl -X POST "http://localhost:8000/api/v1/couplet/analyze" \
  -H "Content-Type: application/json" \
  -d '{"upper": "春风送暖入屠苏", "lower": "秋雨生凉到草庐"}'
```

#### 对联评分（流式模式）

```bash
curl -X POST "http://localhost:8000/api/v1/couplet/analyze" \
  -H "Content-Type: application/json" \
  -d '{"upper": "春风送暖入屠苏", "lower": "秋雨生凉到草庐", "stream": true}'
```

#### 格律检测

```bash
curl -X POST "http://localhost:8000/api/v1/meter/check" \
  -H "Content-Type: application/json" \
  -d '{"text": "床前明月光", "meter_type": "shi"}'
```

### Python SDK

```python
from openprom import CoupletAnalyzer

analyzer = CoupletAnalyzer(
    api_key="your-api-key",
    base_url="http://localhost:8000",
    model="Qwen3.5-9B-Instruct"
)

result = analyzer.analyze("春风化雨", "秋月寒霜")

print(f"总分：{result.total_score}")
print(f"等级：{result.grade}")
print(f"评语：{result.comments}")
```

### ⚠️ 已弃用

以下交互方式已弃用，请迁移到 Web 界面:
- ❌ CLI 命令行
- ❌ TUI 终端界面

---

## 配置

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OPENPROM_API_KEY` | API 密钥 | 必需 |
| `OPENPROM_BASE_URL` | API Base URL | `https://your-llm-gateway.example.com/ai/v1` |
| `OPENPROM_MODEL` | 模型名称 | `your-model-name` |
| `OPENPROM_DATABASE_URL` | 数据库 URL | `sqlite:///./openprom.db` |
| `OPENPROM_REDIS_URL` | Redis URL | `redis://localhost:6379/0` |
| `OPENPROM_CACHE_ENABLED` | 启用缓存 | `false` |
| `OPENPROM_LOG_LEVEL` | 日志级别 | `INFO` |
| `OPENPROM_LOG_FORMAT` | 日志格式 | `text` |

### config/settings.yaml

```yaml
model:
  model_name: "Qwen3.5-9B-Instruct"
  use_gpu: true
  
scoring:
  technique_weights:
    qwen_cosine: 0.60
    llm_technique: 0.20
    llm_rhetoric: 0.20
  
  total_weights:
    formal: 0.30
    technique: 0.30
    artistic: 0.30
    impression: 0.10
```

---

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | API 根路径 |
| `/health` | GET | 健康检查 |
| `/api/v1/couplet/analyze` | POST | 对联评分 |
| `/api/v1/couplet/generate` | POST | 对联生成（SSE） |
| `/api/v1/couplet/complete` | POST | 对联补全（SSE） |
| `/api/v1/shi/generate` | POST | 律诗生成（SSE） |
| `/api/v1/shi/complete` | POST | 律诗补全（SSE） |
| `/api/v1/meter/check` | POST | 格律检测 |
| `/api/v1/meters/list` | GET | 列出格律模板 |
| `/api/v1/couplet/history` | GET | 评鉴历史记录 |
| `/api/v1/couplet/statistics` | GET | 评鉴统计信息 |
| `/metrics` | GET | Prometheus 指标 |
| `/docs` | GET | OpenAPI 文档 |

---

## 评分标准

| 维度 | 权重 | 说明 |
|------|------|------|
| 形式合规 | 30% | 平仄、字数、格律检测 |
| 对仗技术 | 30% | LLM 技法与修辞分析 |
| 艺术表现 | 30% | LLM 深度文学分析 |
| AI 印象 | 10% | AI 整体印象评分 |

### 等级划分

| 分数 | 等级 |
|------|------|
| 90-100 | 优秀 |
| 75-89 | 良好 |
| 60-74 | 及格 |
| 0-59 | 不合格 |

---

## 架构设计

```
openprom/
├── api.py                    # REST API 服务
├── main.py                   # CLI 入口
├── core/                     # 领域层
│   ├── dual_api_scorer.py    # 双 API 评分系统
│   ├── fusion_engine.py      # NLP-LLM 融合引擎
│   └── saddle_engineering.py # 马鞍工程控制
├── engines/                  # 引擎层
│   ├── meter.py              # 诗律词谱匹配
│   └── pingze.py             # 平仄检测
├── infrastructure/           # 基础设施层
│   ├── database.py           # 数据持久化
│   ├── cache.py              # Redis 缓存
│   ├── logging.py            # 结构化日志
│   └── config/               # 配置管理
├── ui/                       # 用户界面
│   └── tui.py                # TUI 界面
└── utils/                    # 工具层
    ├── env_config.py         # 环境变量配置
    ├── scoring.py            # 评分计算
    └── json_parser.py        # JSON 解析
```

---

## 技术栈

- **核心**: Python 3.9+
- **LLM**: Qwen3.5-9B-Instruct
- **NLP**: Transformers, PyTorch, BERT
- **API**: FastAPI, Uvicorn
- **数据库**: SQLite, SQLAlchemy
- **缓存**: Redis
- **监控**: Prometheus, Grafana
- **部署**: Docker, Docker Compose

---

## 部署

### Docker Compose（推荐）

```bash
docker-compose up -d
```

启动服务：
- API: http://localhost:8000
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090
- Redis: localhost:6379

### 生产环境

详见 [DEPLOYMENT.md](DEPLOYMENT.md)

---

## 监控与日志

### Prometheus 指标

- `porm_requests_total`: 总请求数
- `porm_request_latency_seconds`: 请求延迟
- `porm_cache_hits_total`: 缓存命中数

### 日志格式

```json
{
  "timestamp": "2026-04-24T12:00:00Z",
  "level": "INFO",
  "logger": "openprom.api",
  "message": "对联评分 | 上联=春风送暖... | 分数=87.5",
  "extra": {
    "total_score": 87.5,
    "grade": "良好"
  }
}
```

---

## 开发

### 安装开发依赖

```bash
pip install -r requirements.txt
pip install pytest ruff black
```

### 运行测试

```bash
pytest tests/
```

### 代码检查

```bash
ruff check openprom/
black --check openprom/
```

---

## 常见问题

### API 密钥错误

确保已设置 `OPENPROM_API_KEY` 环境变量：

```bash
export OPENPROM_API_KEY=your_api_key
```

### 模型加载失败

检查模型目录是否存在：

```bash
ls -la models/
```

### Redis 连接失败

确保 Redis 服务运行：

```bash
docker-compose ps redis
```

---

## 变更日志

### v4.2.0 (2026-04-24)

**前端重构**:
- 全新墨韵新中式设计（书法字体 + 宣纸纹理 + 渐变网格）
- 暗色/亮色主题切换
- 历史记录本地存储
- 字数实时匹配提示
- 墨水加载动画
- 响应式多断点适配

**后端优化**:
- 评分器请求级复用（延迟降低 50%+）
- FusionEngine 线程安全模型加载
- [CLS] token 语义特征提取
- jieba 分词句法分析（优雅降级）
- 高斯贝叶斯融合算法
- 缓存 TTL + LRU 淘汰策略
- MeterEngine 线程安全 + PING/PING_REQUIRED 区分
- 三仄尾/三平尾检查算法修正
- 新增历史记录/统计 API 端点

### v4.1.0 (2026-04-24)

**新增**:
- REST API 服务 (FastAPI)
- 数据持久化层 (SQLite + SQLAlchemy)
- Redis 缓存服务
- 结构化日志 (JSON 格式)
- Prometheus 监控指标
- 流式 API 输出 (SSE)
- Docker 部署支持

**修复**:
- 移除硬编码 API 密钥，改用环境变量
- 修复 FusionEngine 模型路径硬编码
- 统一归一化算法

### v4.0.0 (2026)

- 双 API 评分系统
- BERT 语义相似度计算
- 马鞍工程控制
- TUI 界面

---

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 支持

- **文档**: http://localhost:8000/docs
- **部署指南**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **GitHub Issues**: 提交 Bug 和功能请求
