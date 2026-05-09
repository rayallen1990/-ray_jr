# Ray_jr 工业知识库平台 - CowAgent Skill 集成文档

## 概述

Ray_jr 是一个基于 RAG（检索增强生成）的工业知识库平台，通过 CowAgent Skill 插件机制实现多渠道接入（微信、飞书、钉钉）。用户可以通过聊天命令上传文档、查询知识库，系统自动完成文档解析、向量化、存储和智能问答。

## 架构

```
用户消息 → CowAgent Channel → Skill Handler → RAG Pipeline → 回复
                                     ↓
                              Tenant Mapper (多租户隔离)
                                     ↓
                    ┌────────────────────────────────────┐
                    │  Document Parser → Chunker         │
                    │  Embedding → Vector Store (Qdrant) │
                    │  RAG Engine (Claude API)           │
                    └────────────────────────────────────┘
```

## 目录结构

```
ray_jr/
├── skills/ray-jr-kb/           # CowAgent Skill 插件
│   ├── skill_handler.py        # 命令路由和处理入口
│   ├── tools/                  # Skill 工具集
│   │   ├── __init__.py
│   │   ├── document_parser.py  # PDF/Word 文档解析
│   │   ├── embedding.py        # 向量嵌入生成
│   │   ├── rag_engine.py       # RAG 查询引擎
│   │   ├── tenant_mapper.py    # 用户→租户映射
│   │   └── vector_store.py     # Qdrant 向量存储
│   └── tests/                  # 单元测试
├── packages/                   # 核心包（可独立使用）
│   ├── document_parser/        # 文档解析库
│   ├── rag_engine/             # RAG 引擎核心
│   ├── vector_store/           # 向量存储抽象层
│   ├── tenant_isolation/       # 多租户中间件
│   └── auth_middleware/        # JWT 认证中间件
├── app/                        # FastAPI 应用（独立部署模式）
│   ├── main.py
│   ├── config.py               # 配置管理
│   ├── kb_sync.py              # 知识库仓库同步
│   └── api/v1/
│       └── skill_handler.py    # HTTP API 版本
└── docs/                       # 文档
```

## 快速开始

详见 [部署指南](deployment.md) 和 [用户指南](user-guide.md)。

## 文档索引

- [用户指南](user-guide.md) — 命令使用说明
- [部署指南](deployment.md) — 环境搭建和部署
- [开发指南](development.md) — 开发者参考
- [故障排除](troubleshooting.md) — 常见问题解决
