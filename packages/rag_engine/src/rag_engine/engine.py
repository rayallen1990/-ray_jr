"""RAG engine core - retrieval + generation with retry, batch embedding support"""

import time
import logging
from typing import List, AsyncIterator, Callable, Optional

from .prompt import PromptTemplate

logger = logging.getLogger(__name__)


class RagResponse:
    def __init__(self, answer: str, sources: List[str]):
        self.answer = answer
        self.sources = sources


class RagEngine:
    """RAG engine: retrieves relevant docs then generates answer via Claude API"""

    def __init__(
        self,
        vector_store,
        api_key: str,
        model: str = "claude-sonnet-4-5-20250929",
        top_k: int = 5,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.vector_store = vector_store
        self.api_key = api_key
        self.model = model
        self.top_k = top_k
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._prompt = PromptTemplate()

    def _get_client(self):
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic required: pip install anthropic")
        return anthropic.Anthropic(api_key=self.api_key)

    def embed_batch(self, texts: List[str], embed_fn: Callable) -> List[List[float]]:
        """Generate embeddings for a batch of texts.

        embed_fn may accept a list (batch) or a single string.
        Falls back to sequential calls if batch call fails.
        """
        if not texts:
            return []
        try:
            result = embed_fn(texts)
            if isinstance(result, list) and result and isinstance(result[0], list):
                logger.info("Batch embedded %d texts", len(texts))
                return result
            logger.debug("embed_fn returned single vector; falling back to sequential")
        except Exception as e:
            logger.warning("Batch embed failed (%s), falling back to sequential", e)

        vectors = []
        for text in texts:
            vectors.append(embed_fn(text))
        return vectors

    def query(self, question: str, namespace: str, embed_fn: Optional[Callable] = None) -> RagResponse:
        """Retrieve relevant docs and generate answer with retry on API errors."""
        if embed_fn is None:
            raise ValueError("embed_fn is required to embed the query")

        try:
            query_vector = embed_fn(question)
        except Exception as e:
            logger.error("Embedding failed for query: %s", e)
            raise RuntimeError(f"Failed to embed query: {e}")

        try:
            docs = self.vector_store.search(query_vector, namespace=namespace, top_k=self.top_k)
        except ConnectionError as e:
            logger.error("Vector store unavailable: %s", e)
            raise RuntimeError(f"知识库检索失败，请稍后重试。({e})")

        if not docs:
            logger.info("No documents found for query in namespace '%s'", namespace)
            return RagResponse(answer="未找到相关文档，请尝试其他问题。", sources=[])

        system_prompt, user_prompt = self._prompt.build(question, docs)
        client = self._get_client()

        last_error = None
        for attempt in range(self.max_retries):
            try:
                message = client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                answer = message.content[0].text
                sources = [d.metadata.get("source", d.id) for d in docs]
                logger.info("Query answered (attempt %d)", attempt + 1)
                return RagResponse(answer=answer, sources=sources)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait = self.retry_delay * (attempt + 1)
                    logger.warning("Claude API error (attempt %d/%d): %s — retrying in %.1fs",
                                   attempt + 1, self.max_retries, e, wait)
                    time.sleep(wait)
                else:
                    logger.error("Claude API failed after %d attempts: %s", self.max_retries, e)

        raise RuntimeError(f"AI 服务暂时不可用，请稍后重试。({last_error})")

    async def stream(
        self, question: str, namespace: str, embed_fn: Optional[Callable] = None
    ) -> AsyncIterator[str]:
        """Stream answer tokens via Claude streaming API."""
        if embed_fn is None:
            raise ValueError("embed_fn is required")

        try:
            query_vector = embed_fn(question)
        except Exception as e:
            raise RuntimeError(f"Failed to embed query: {e}")

        try:
            docs = self.vector_store.search(query_vector, namespace=namespace, top_k=self.top_k)
        except ConnectionError as e:
            raise RuntimeError(f"知识库检索失败，请稍后重试。({e})")

        if not docs:
            yield "未找到相关文档，请尝试其他问题。"
            return

        system_prompt, user_prompt = self._prompt.build(question, docs)
        client = self._get_client()

        try:
            with client.messages.stream(
                model=self.model,
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error("Streaming failed: %s", e)
            raise RuntimeError(f"AI 服务暂时不可用，请稍后重试。({e})")
