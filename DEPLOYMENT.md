# OpenPROM 部署指南

版本：4.1.0  
最后更新：2026 年 4 月

---

## 目录

1. [快速开始](#快速开始)
2. [环境要求](#环境要求)
3. [安装配置](#安装配置)
4. [Docker 部署](#docker 部署)
5. [生产环境配置](#生产环境配置)
6. [API 使用示例](#api 使用示例)
7. [监控与日志](#监控与日志)
8. [故障排查](#故障排查)

---

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd openprom
```

### 2. 设置环境变量

```bash
# 复制环境变量示例文件
cp .env.example .env

# 编辑 .env 文件，填入 API 密钥
# OPENPROM_API_KEY=your_api_key_here
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 初始化数据库

```bash
python -c "from openprom.infrastructure.database import db_manager; db_manager.create_tables()"
```

### 5. 启动服务

```bash
# 开发模式
python -m openprom.api

# 或使用 uvicorn
uvicorn openprom.api:app --host 0.0.0.0 --port 8000 --reload
```

### 6. 访问 API 文档

打开浏览器访问：http://localhost:8000/docs

---

## 环境要求

### 最低配置

- **CPU**: 4 核心
- **内存**: 8GB RAM
- **存储**: 10GB 可用空间
- **Python**: 3.9+

### 推荐配置

- **CPU**: 8 核心+
- **内存**: 16GB+ RAM
- **存储**: 50GB+ SSD
- **GPU**: NVIDIA GPU (可选，用于加速 BERT 模型)

### 系统依赖

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3-pip python3-dev gcc libpq-dev

# CentOS/RHEL
sudo yum install -y python3-pip python3-devel gcc libpq-devel

# macOS
brew install python3
```

---

## 安装配置

### 1. 创建虚拟环境（推荐）

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate     # Windows
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

编辑 `.env` 文件：

```bash
# API 配置（必需）
OPENPROM_API_KEY=your_api_key_here
OPENPROM_BASE_URL=https://your-llm-gateway.example.com/ai/v1
OPENPROM_MODEL=Qwen3.5-9B-Instruct

# 服务配置（可选）
OPENPROM_HOST=0.0.0.0
OPENPROM_PORT=8000
OPENPROM_DEBUG=false

# 数据库配置（可选）
OPENPROM_DATABASE_URL=sqlite:///./openprom.db

# Redis 配置（可选）
OPENPROM_REDIS_URL=redis://localhost:6379/0
OPENPROM_CACHE_ENABLED=false

# 日志配置（可选）
OPENPROM_LOG_LEVEL=INFO
OPENPROM_LOG_FORMAT=text
```

### 4. 下载模型（可选）

如果使用本地 BERT 模型：

```bash
python -c "from transformers import AutoModel, AutoTokenizer; \
AutoTokenizer.from_pretrained('bert-base-chinese', cache_dir='./models'); \
AutoModel.from_pretrained('bert-base-chinese', cache_dir='./models')"
```

---

## Docker 部署

### 1. 构建镜像

```bash
docker build -t openprom:latest .
```

### 2. 使用 Docker Compose（推荐）

```bash
# 启动所有服务（API + Redis + Prometheus + Grafana）
docker-compose up -d

# 查看日志
docker-compose logs -f api

# 停止服务
docker-compose down
```

### 3. 单独运行 API

```bash
docker run -d \
  -p 8000:8000 \
  -e OPENPROM_API_KEY=your_api_key \
  -e OPENPROM_MODEL=Qwen3.5-9B-Instruct \
  -v $(pwd)/data:/app/data \
  --name openprom-api \
  openprom:latest
```

### 4. Docker 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OPENPROM_API_KEY` | API 密钥 | 无（必需） |
| `OPENPROM_BASE_URL` | API Base URL | `https://your-llm-gateway.example.com/ai/v1` |
| `OPENPROM_MODEL` | 模型名称 | `Qwen3.5-9B-Instruct` |
| `OPENPROM_DATABASE_URL` | 数据库 URL | `sqlite:///./data/openprom.db` |
| `OPENPROM_REDIS_URL` | Redis URL | `redis://redis:6379/0` |
| `OPENPROM_CACHE_ENABLED` | 启用缓存 | `false` |
| `OPENPROM_LOG_LEVEL` | 日志级别 | `INFO` |
| `OPENPROM_LOG_FORMAT` | 日志格式 | `json` |

---

## 生产环境配置

### 1. 使用 Gunicorn + Uvicorn

```bash
pip install gunicorn

gunicorn openprom.api:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile access.log \
  --error-logfile error.log \
  --log-level info
```

### 2. Nginx 反向代理

```nginx
server {
    listen 80;
    server_name openprom.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # SSE 支持
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # 静态文件（API 文档）
    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
    }
}
```

### 3. Systemd 服务配置

创建 `/etc/systemd/system/openprom.service`：

```ini
[Unit]
Description=OpenPROM API Service
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/openprom
Environment="PATH=/opt/openprom/venv/bin"
ExecStart=/opt/openprom/venv/bin/gunicorn openprom.api:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable openprom
sudo systemctl start openprom
sudo systemctl status openprom
```

---

## API 使用示例

### 1. 对联评分（标准模式）

```bash
curl -X POST "http://localhost:8000/api/v1/couplet/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "upper": "春风送暖入屠苏",
    "lower": "秋雨生凉到草庐"
  }'
```

响应示例：

```json
{
  "upper": "春风送暖入屠苏",
  "lower": "秋雨生凉到草庐",
  "formal_score": 0.95,
  "technique_score": 0.88,
  "artistic_score": 0.85,
  "impression_score": 0.82,
  "total_score": 87.5,
  "grade": "良好",
  "pingze_score": 0.90,
  "warnings": [],
  "comments": {
    "technique_comment": "对仗工整，词性匹配良好",
    "artistic_comment": "意境优美，情景交融"
  },
  "processing_time_ms": 3500.25
}
```

### 2. 对联评分（流式模式）

```bash
curl -X POST "http://localhost:8000/api/v1/couplet/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "upper": "春风送暖入屠苏",
    "lower": "秋雨生凉到草庐",
    "stream": true
  }'
```

流式响应（SSE）：

```
data: {"event": "start", "timestamp": 1234567890.123}

data: {"event": "formal_check", "data": {"status": "checking", "message": "形式检测中..."}, "timestamp": 1234567890.456}

data: {"event": "technique_analysis", "data": {"status": "complete", "technique_score": 0.88}, "timestamp": 1234567892.789}

data: {"event": "complete", "data": {...}, "timestamp": 1234567895.123}

data: {"event": "end", "timestamp": 1234567895.456}
```

### 3. 格律检测

```bash
curl -X POST "http://localhost:8000/api/v1/meter/check" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "床前明月光",
    "meter_type": "shi"
  }'
```

### 4. 健康检查

```bash
curl http://localhost:8000/health
```

---

## 监控与日志

### 1. Prometheus 指标

访问 `http://localhost:8000/metrics` 获取指标：

- `porm_requests_total`: 总请求数
- `porm_request_latency_seconds`: 请求延迟
- `porm_cache_hits_total`: 缓存命中数

### 2. Grafana 仪表盘

Docker Compose 部署后，访问 http://localhost:3000

默认账号：`admin` / `admin`

### 3. 日志查看

```bash
# JSON 格式日志（生产环境）
tail -f logs/openprom.log | jq .

# 文本格式日志（开发环境）
tail -f logs/openprom.log
```

### 4. 日志级别

| 级别 | 说明 | 使用场景 |
|------|------|----------|
| `DEBUG` | 调试信息 | 开发调试 |
| `INFO` | 一般信息 | 生产环境 |
| `WARNING` | 警告信息 | 需要注意的问题 |
| `ERROR` | 错误信息 | 需要处理的错误 |
| `CRITICAL` | 严重错误 | 系统故障 |

---

## 故障排查

### 1. API 密钥错误

**问题**: `401 Unauthorized`

**解决**:
```bash
# 检查环境变量
echo $OPENPROM_API_KEY

# 或检查 .env 文件
cat .env | grep OPENPROM_API_KEY
```

### 2. 模型加载失败

**问题**: `Model not found`

**解决**:
```bash
# 检查模型目录
ls -la models/

# 重新下载模型
python -c "from transformers import AutoModel; AutoModel.from_pretrained('bert-base-chinese', cache_dir='./models')"
```

### 3. Redis 连接失败

**问题**: `Redis connection failed`

**解决**:
```bash
# 检查 Redis 服务
docker-compose ps redis

# 查看 Redis 日志
docker-compose logs redis

# 测试连接
redis-cli -h localhost ping
```

### 4. 数据库锁定

**问题**: `database is locked`

**解决**:
```bash
# SQLite 仅支持单写入，检查是否有多个进程访问
# 生产环境建议使用 PostgreSQL

# 临时解决：删除数据库文件重新创建
rm openprom.db
python -c "from openprom.infrastructure.database import db_manager; db_manager.create_tables()"
```

### 5. 内存不足

**问题**: `Killed` 或 `OOM`

**解决**:
```bash
# 1. 使用 GPU 加速
export CUDA_VISIBLE_DEVICES=0

# 2. 减少并发
export OPENPROM_MAX_WORKERS=2

# 3. 使用更小的模型
export OPENPROM_MODEL=Qwen2.5-1.5B-Instruct

# 4. 增加 swap 空间
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## 性能优化建议

### 1. 启用 Redis 缓存

```bash
# .env 文件
OPENPROM_CACHE_ENABLED=true
OPENPROM_REDIS_URL=redis://localhost:6379/0
```

### 2. 使用 PostgreSQL

```bash
# 安装 PostgreSQL 适配器
pip install psycopg2-binary

# .env 文件
OPENPROM_DATABASE_URL=postgresql://user:password@localhost:5432/openprom
```

### 3. 调整 Worker 数量

```bash
# 根据 CPU 核心数调整
gunicorn openprom.api:app -w $(nproc) -k uvicorn.workers.UvicornWorker
```

### 4. 启用 HTTP/2

使用支持 HTTP/2 的反向代理（如 Nginx 1.9.5+）：

```nginx
listen 443 ssl http2;
```

---

## 安全建议

1. **不要将 API 密钥提交到版本控制**
   - 将 `.env` 添加到 `.gitignore`
   - 使用密钥管理服务（如 AWS Secrets Manager）

2. **启用 HTTPS**
   - 使用 Let's Encrypt 免费证书
   - 配置 Nginx SSL

3. **限制 API 访问**
   - 使用 API 密钥认证
   - 配置防火墙规则

4. **定期备份数据库**
   ```bash
   # SQLite 备份
   cp openprom.db openprom.db.backup.$(date +%Y%m%d)
   
   # PostgreSQL 备份
   pg_dump openprom > backup.sql
   ```

---

## 支持

- **GitHub Issues**: 提交 Bug 和功能请求
- **邮件**: support@openprom.local
- **文档**: http://localhost:8000/docs
