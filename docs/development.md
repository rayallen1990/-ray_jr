# 开发指南

## 项目架构

Ray_jr 采用分层架构：

```
┌─────────────────────────────────────────────┐
│  CowAgent Skill Layer (skills/ray-jr-kb/)   │  ← 命令路由 + CowAgent 集成
├─────────────────────────────────────────────┤
│  Tools Layer (skills/ray-jr-kb/tools/)      │  ← 业务逻辑封装
├─────────────────────────────────────────────┤
│  Core Packages (packages/)                  │  ← 可复用核心库
│  - document_parser                          │
│  - vector_store (Qdrant + Redis cache)      │
│  - rag_engine (Claude API)                  │
│  - tenant_isolation                         │
│  - auth_middleware                          │
├─────────────────────────────────────────────┤
│  Infrastructure                             │
│  Qdrant │ Redis │ PostgreSQL                │
└─────────────────────────────────────────────┘
```

## 核心组件

### 1. Skill Handler (`skills/ray-jr-kb/skill_handler.py`)

CowAgent Skill 的入口点。接收 CowAgent context，路由到对应的命令处理函数。

```python
async def handle_kb_upload(context: Dict[str, Any]) -> str:
    """处理 /kb upload 命令"""
    tenant_info = resolve_tenant(context)
    # ... 解析文件、分块、嵌入、索引
```

### 2. Tenant Mapper (`skills/ray-jr-kb/tools/tenant_mapper.py`)

将 CowAgent 的用户上下文映射为租户信息：

```python
from tools.tenant_mapper import resolve_tenant, TenantInfo

tenant: TenantInfo = resolve_tenant(context)
# tenant.tenant_id = "dingtalk:user123"
# tenant.namespace = "tenant:dingtalk:user123:private"
```

支持的渠道：weixin, feishu, dingtalk, web

### 3. Vector Store (`packages/vector_store/`)

Qdrant 向量数据库封装，支持 Redis 缓存：

```python
from vector_store import QdrantVectorStore, VectorDocument

store = QdrantVectorStore(
    host="localhost",
    port=6333,
    redis_url="redis://localhost:6379/0",  # 可选
    cache_ttl=300,
)

# 添加文档
store.add(documents=[VectorDocument(...)], namespace="tenant:xxx:private")

# 搜索（自动缓存）
results = store.search(query_vector, namespace="tenant:xxx:private", top_k=5)
```

### 4. RAG Engine (`packages/rag_engine/`)

基于 Claude API 的 RAG 引擎：

```python
from rag_engine.engine import RagEngine

engine = RagEngine(
    vector_store=store,
    api_key="sk-ant-xxx",
    model="claude-sonnet-4.5",
    top_k=5,
    max_retries=3,
)

# 同步查询
response = engine.query("什么是PLC？", namespace="tenant:xxx:private", embed_fn=embed)

# 流式输出
async for chunk in engine.stream("什么是PLC？", namespace="...", embed_fn=embed):
    print(chunk, end="")
```

### 5. Document Parser (`packages/document_parser/`)

文档解析和分块：

```python
from document_parser import parse_pdf, parse_word
from document_parser.chunker import chunk_text

# 解析 PDF
text = parse_pdf("manual.pdf")

# 解析 Word
text = parse_word("guide.docx")

# 分块
chunks = chunk_text(text, chunk_size=800, overlap=100)
```

## 开发环境搭建

```bash
# 克隆仓库
git clone https://github.com/rayallen1990/-ray_jr.git
cd -ray_jr

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装开发依赖
pip install -e packages/document_parser
pip install -e packages/vector_store
pip install -e packages/rag_engine
pip install -e packages/tenant_isolation
pip install -e packages/auth_middleware
pip install pytest pytest-asyncio httpx

# 启动本地 Qdrant
docker run -d --name qdrant-dev -p 6333:6333 qdrant/qdrant:latest
```

## 运行测试

```bash
# 运行所有测试
pytest tests/ skills/ray-jr-kb/tests/ -v

# 运行特定测试
pytest skills/ray-jr-kb/tests/test_tenant_mapper.py -v
pytest skills/ray-jr-kb/tests/test_skill_handler.py -v

# 运行带覆盖率
pytest --cov=skills/ray-jr-kb --cov=packages -v
```

## 添加新命令

1. 在 `skills/ray-jr-kb/skill_handler.py` 中添加处理函数：

```python
async def handle_kb_newcmd(context: Dict[str, Any]) -> str:
    """处理 /kb newcmd 命令"""
    tenant_info = resolve_tenant(context)
    # 实现逻辑
    return "结果"
```

2. 在命令路由中注册（skill_handler.py 的路由逻辑）

3. 添加对应测试到 `skills/ray-jr-kb/tests/`

## CowAgent Context 结构

CowAgent 传递给 Skill 的 context 结构：

```python
{
    "channel_type": "dingtalk",  # weixin | feishu | dingtalk | web
    "msg": {
        "from_user_id": "user123",
        "from_user_nickname": "张三",
        "is_group": False,
        "other_user_id": "group_abc",    # 群聊时的群 ID
        "actual_user_id": "real_user",   # 群聊中实际发言人
        "content": "/kb ask 什么是PLC？",
        "attachments": [                  # /kb upload 时的附件
            {
                "filename": "manual.pdf",
                "content": b"...",        # 文件内容
                "file_path": "/tmp/xxx",  # 或文件路径
            }
        ],
    },
    "session_id": "sess_xxx",
}
```

## 代码规范

- 类型注解：所有公开函数使用 type hints
- 日志：使用 `logging` 模块，不使用 print
- 错误处理：面向用户的错误使用中文消息
- 异步：IO 操作使用 async/await
- 测试：每个工具模块对应一个测试文件
