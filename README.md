# Ray-JR 工业控制知识库平台

基于 RAG（检索增强生成）的工业控制领域知识库系统，支持多租户隔离、多渠道接入。

## 技术栈

- **后端**: FastAPI + SQLAlchemy 2.0 + PostgreSQL
- **向量存储**: Qdrant（带 Redis 缓存）
- **LLM**: DeepSeek / OpenAI 兼容 API（可切换）
- **文档解析**: PDF (PyMuPDF) / Word (python-docx) / TXT / Markdown
- **认证**: JWT + 多租户隔离
- **集成**: CowAgent Skill 插件（飞书/钉钉/微信）

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/rayallen1990/-ray_jr.git
cd -ray_jr

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY 等配置

# 3. 启动基础服务
docker compose up -d

# 4. 安装依赖
pip install -r requirements.txt

# 5. 启动应用
uvicorn app.main:app --reload --port 8000
```

## 核心功能

| 功能 | 说明 |
|------|------|
| `/kb ask <问题>` | RAG 知识库问答（含 Query Rewrite） |
| `/kb upload` | 上传文档（PDF/Word/TXT） |
| `/kb list` | 列出已上传文档 |
| `/kb status` | 查看知识库状态 |
| `/kb sync` | 从 Git 仓库同步知识库 |

## 项目结构

```
app/                    # FastAPI 应用
├── api/v1/            # REST API 路由 (chat, documents, auth)
├── models/            # ORM 模型 (User, Tenant, Document, AuditLog)
├── config.py          # 配置管理
└── main.py            # 应用入口

packages/              # 可复用模块
├── auth_middleware/   # JWT 认证
├── tenant_isolation/  # 多租户隔离中间件
├── vector_store/      # Qdrant 向量存储 + Redis 缓存
├── rag_engine/        # RAG 引擎（支持 DeepSeek/OpenAI/Anthropic）
└── document_parser/   # 文档解析与分块

skills/ray-jr-kb/      # CowAgent Skill 插件
├── skill_handler.py   # 命令路由入口
└── tools/             # 工具模块 (embedding, query_rewriter, tenant_mapper)

docs/                  # 详细文档
```

## 文档

详细文档请参阅 [docs/](./docs/) 目录：

- [用户指南](./docs/user-guide.md)
- [部署文档](./docs/deployment.md)
- [开发文档](./docs/development.md)
- [故障排除](./docs/troubleshooting.md)
