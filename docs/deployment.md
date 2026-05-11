# 部署指南

## 系统要求

| 组件 | 最低版本 | 说明 |
|------|----------|------|
| Python | 3.10+ | 运行环境 |
| Qdrant | 1.7+ | 向量数据库 |
| Redis | 6.0+ | 查询缓存（可选） |
| PostgreSQL | 14+ | 元数据存储（独立部署模式） |

## 环境变量

创建 `.env` 文件：

```env
# 必需
ANTHROPIC_API_KEY=sk-ant-xxxxx          # Claude API 密钥
QDRANT_HOST=localhost                     # Qdrant 地址
QDRANT_PORT=6333                          # Qdrant HTTP 端口

# 可选
REDIS_URL=redis://localhost:6379/0        # Redis 缓存（提升查询性能）
OPENAI_API_KEY=sk-xxxxx                   # OpenAI 嵌入模型（备选）
DATABASE_URL=postgresql://user:pass@localhost:5432/ray_jr

# RAG 配置
RAG_MODEL=claude-sonnet-4.5              # LLM 模型
RAG_TOP_K=5                               # 检索文档数
RAG_MAX_CONTEXT_TOKENS=100000             # 最大上下文窗口

# 知识库仓库同步
KNOWLEDGE_BASE_REPO=https://github.com/your-org/kb-repo.git
KNOWLEDGE_BASE_PATH=./data
KNOWLEDGE_BASE_BRANCH=main
KNOWLEDGE_BASE_AUTO_SYNC=true

# JWT（独立部署模式）
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## 部署方式

### 方式一：CowAgent Skill 插件（推荐）

将 Ray_jr 作为 CowAgent 的 Skill 插件运行，获得微信/飞书/钉钉多渠道接入能力。

**步骤：**

1. 克隆 CowAgent：
```bash
git clone https://github.com/zhayujie/CowAgent.git
cd CowAgent
```

2. 将 Ray_jr Skill 复制到 CowAgent skills 目录：
```bash
git clone https://github.com/rayallen1990/-ray_jr.git
cp -r -ray_jr/skills/ray-jr-kb CowAgent/skills/
```

3. 安装 Skill 依赖：
```bash
cd CowAgent
pip install pymupdf python-docx qdrant-client anthropic sentence-transformers redis pydantic-settings python-dotenv
```

4. 配置 CowAgent 的 `config.json`，启用 ray-jr-kb Skill：
```json
{
  "skills": {
    "ray-jr-kb": {
      "enabled": true,
      "trigger_prefix": "/kb"
    }
  }
}
```

5. 启动 Qdrant：
```bash
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_data:/qdrant/storage \
  qdrant/qdrant:latest
```

6. （可选）启动 Redis 缓存：
```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

7. 启动 CowAgent：
```bash
python app.py
```

### 方式二：独立 FastAPI 服务

不依赖 CowAgent，作为独立 HTTP API 服务运行。

**步骤：**

1. 克隆仓库：
```bash
git clone https://github.com/rayallen1990/-ray_jr.git
cd -ray_jr
```

2. 创建虚拟环境并安装依赖：
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. 启动基础设施：
```bash
# Qdrant
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:latest

# PostgreSQL
docker run -d --name postgres -p 5432:5432 \
  -e POSTGRES_USER=ray_jr_user \
  -e POSTGRES_PASSWORD=changeme \
  -e POSTGRES_DB=ray_jr \
  postgres:14-alpine

# Redis（可选）
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

4. 配置环境变量（创建 `.env` 文件，参考上方环境变量表）

5. 启动服务：
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Docker Compose 部署

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  postgres:
    image: postgres:14-alpine
    environment:
      POSTGRES_USER: ray_jr_user
      POSTGRES_PASSWORD: changeme
      POSTGRES_DB: ray_jr
    ports:
      - "5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data

volumes:
  qdrant_data:
  pg_data:
```

启动：
```bash
docker-compose up -d
```

## 渠道配置

### 飞书接入

1. 在飞书开放平台创建应用
2. 获取 App ID 和 App Secret
3. 配置事件订阅 URL 或启用 WebSocket 模式
4. 在 CowAgent 配置中添加飞书 channel：

```json
{
  "channel_type": "feishu",
  "feishu_app_id": "cli_xxxxx",
  "feishu_app_secret": "xxxxx",
  "feishu_token": "xxxxx"
}
```

### 钉钉接入

1. 在钉钉开放平台创建应用
2. 获取 Client ID 和 Client Secret
3. 启用 Stream 模式（推荐）
4. 在 CowAgent 配置中添加钉钉 channel：

```json
{
  "channel_type": "dingtalk",
  "dingtalk_client_id": "xxxxx",
  "dingtalk_client_secret": "xxxxx"
}
```

### 微信接入

1. 配置微信公众号或企业微信
2. 使用 ilink bot API 长轮询模式
3. 在 CowAgent 配置中添加微信 channel：

```json
{
  "channel_type": "weixin",
  "wechat_token": "xxxxx",
  "wechat_app_id": "xxxxx",
  "wechat_app_secret": "xxxxx"
}
```

## 性能调优

### Redis 缓存

启用 Redis 后，重复查询的向量检索结果会被缓存（默认 TTL 300秒），显著降低 Qdrant 负载。

配置：
```env
REDIS_URL=redis://localhost:6379/0
```

### Qdrant 优化

- 生产环境建议使用 gRPC 端口（6334）提升吞吐
- 对于大规模数据，配置 Qdrant 集群模式
- 建议为每个 collection 设置合适的向量维度索引

### 批量嵌入

上传大文档时，系统自动使用批量嵌入（每批 32 个片段），减少 API 调用次数。
