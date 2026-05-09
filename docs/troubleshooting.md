# 故障排除

## 常见问题

### Qdrant 连接失败

**错误：** `ConnectionError: Cannot connect to Qdrant at localhost:6333`

**原因：** Qdrant 服务未启动或地址配置错误。

**解决：**
1. 确认 Qdrant 正在运行：
```bash
docker ps | grep qdrant
# 如果没有运行：
docker start qdrant
# 或重新创建：
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:latest
```

2. 检查环境变量：
```bash
echo $QDRANT_HOST  # 应为 localhost 或实际地址
echo $QDRANT_PORT  # 应为 6333
```

3. 测试连接：
```bash
curl http://localhost:6333/collections
```

### Claude API 调用失败

**错误：** `AI 服务暂时不可用，请稍后重试。`

**原因：** Anthropic API 密钥无效、额度用尽或网络问题。

**解决：**
1. 检查 API 密钥：
```bash
echo $ANTHROPIC_API_KEY  # 确认已设置
```

2. 测试 API 连通性：
```python
import anthropic
client = anthropic.Anthropic()
msg = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=10,
    messages=[{"role": "user", "content": "hi"}]
)
print(msg.content[0].text)
```

3. 系统会自动重试 3 次（间隔递增），如果仍然失败则返回错误。

### 文档上传失败

**错误：** `不支持的文件格式 .xxx`

**支持的格式：** .pdf, .docx, .doc, .txt

**错误：** `文件过大`

**限制：** 单文件最大 100MB

**错误：** `文档解析后内容为空`

**原因：** PDF 可能是扫描件（图片型），无法提取文本。

**解决：** 使用 OCR 工具先将扫描件转为可搜索 PDF，或手动提取文本为 .txt 格式。

### 租户映射失败

**错误：** `无法识别用户身份`

**原因：** CowAgent context 中缺少必要的用户信息。

**排查：**
1. 检查 CowAgent 日志中的 context 内容
2. 确认 channel 配置正确（飞书/钉钉的 App ID 等）
3. 确认消息中包含 `from_user_id` 字段

### Redis 缓存不生效

**现象：** 重复查询没有命中缓存

**排查：**
1. 确认 Redis 连接正常：
```bash
redis-cli ping  # 应返回 PONG
```

2. 检查日志中是否有 `Redis unavailable, caching disabled` 警告

3. 缓存 TTL 默认 300 秒，超时后自动失效

### 知识库同步失败

**错误：** `/kb sync` 无响应或报错

**排查：**
1. 确认 Git 仓库 URL 正确且可访问
2. 确认有读取权限（SSH key 或 token）
3. 检查磁盘空间是否充足
4. 查看日志中的具体 Git 错误

## 日志配置

启用详细日志：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("skills.ray-jr-kb").setLevel(logging.DEBUG)
logging.getLogger("vector_store").setLevel(logging.DEBUG)
logging.getLogger("rag_engine").setLevel(logging.DEBUG)
```

## 性能问题

### 查询响应慢

可能原因：
1. **Qdrant 未预热** — 首次查询需要加载索引，后续会快
2. **未启用 Redis 缓存** — 配置 `REDIS_URL` 启用缓存
3. **文档过多** — 考虑调小 `RAG_TOP_K`（默认 5）
4. **网络延迟** — Claude API 调用受网络影响

### 上传速度慢

可能原因：
1. **文档过大** — 大文件分块多，嵌入耗时长
2. **嵌入 API 限流** — 系统已使用批量嵌入（32/批）优化
3. **Qdrant 写入慢** — 检查 Qdrant 资源使用情况

## 联系支持

如遇到无法解决的问题，请在 GitHub Issues 中提交：
https://github.com/rayallen1990/-ray_jr/issues
