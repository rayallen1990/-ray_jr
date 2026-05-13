"""Query Rewrite module for RAG pipeline.

Rewrites user queries using Claude API to improve vector search recall,
especially for industrial control domain terminology.
"""

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

QUERY_REWRITE_ENABLED: bool = os.environ.get("QUERY_REWRITE_ENABLED", "true").lower() != "false"

_SYSTEM_PROMPT: str = (
    "你是工业控制领域的搜索查询优化专家。\n"
    "将用户的口语化问题改写为适合向量检索的专业查询。\n\n"
    "规则：\n"
    "- 保留核心意图，不改变问题含义\n"
    "- 补充相关专业术语和同义词\n"
    "- 去除无关的语气词和冗余表达\n"
    "- 如果有对话历史，补全指代词\n"
    "- 输出简洁的检索 query（不超过100字）\n"
    "- 只输出改写后的 query，不要任何解释"
)


async def rewrite_query(
    question: str,
    history: Optional[List[str]] = None,
) -> str:
    """Rewrite a user query for better vector search recall.

    Uses Claude API to transform colloquial queries into professional
    industrial control terminology. Falls back to original query on failure.

    Args:
        question: Original user question.
        history: Optional conversation history for context resolution.

    Returns:
        Rewritten query string, or original question if rewrite is disabled/fails.
    """
    if not QUERY_REWRITE_ENABLED:
        logger.debug("Query rewrite disabled, using original query")
        return question

    if not question or not question.strip():
        return question

    api_key: Optional[str] = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, skipping query rewrite")
        return question

    user_content = ""
    if history:
        user_content += "对话历史：\n" + "\n".join(history[-3:]) + "\n\n"
    user_content += f"用户问题：{question}"

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key, timeout=10.0)
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=150,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        rewritten = response.content[0].text.strip()
        if rewritten:
            logger.info("Query rewritten: '%s' -> '%s'", question, rewritten)
            return rewritten
    except ImportError:
        logger.warning("anthropic package not installed, skipping query rewrite")
    except Exception as exc:
        logger.warning("Query rewrite failed (%s), using original query", exc)

    return question
