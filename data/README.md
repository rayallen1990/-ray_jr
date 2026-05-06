# 数据目录说明

本目录用于存放繁易 HMI 知识库的种子数据。

## 目录结构

```
data/
├── documents/          # 繁易官方文档（PDF/Word）
│   ├── manuals/        # 操作手册
│   └── specs/          # 产品规格书
├── faq/                # 常见问答
│   └── faq.json        # FAQ 数据（JSON 格式）
└── glossary/           # 术语表
    └── terms.json      # 术语和型号命名规则
```

## 数据格式

### FAQ 格式 (`faq/faq.json`)
```json
[
  {
    "id": 1,
    "question": "问题内容",
    "answer": "答案内容",
    "category": "分类",
    "tags": ["标签1", "标签2"]
  }
]
```

### 术语表格式 (`glossary/terms.json`)
```json
[
  {
    "term": "缩写",
    "full_name": "全称",
    "chinese": "中文名",
    "definition": "定义说明"
  }
]
```

## 数据导入

使用文档解析模块导入 PDF/Word 文档：
```python
from document_parser import PdfParser, chunk_text

parser = PdfParser()
text = parser.parse("data/documents/manuals/manual.pdf")
chunks = chunk_text(text, chunk_size=800)
```

## 数据要求

- **文档**：50 份繁易官方文档（PDF/Word 格式）
- **FAQ**：100 个常见问答（JSON 格式）
- **术语表**：200+ 个词条（JSON 格式）
