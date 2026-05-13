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
    """RAG engine: retrieves relevant docs then generates answer via OpenAI-compatible API.

    Supports DeepSeek, OpenAI, and any OpenAI-compatible provider.
    For Anthropic, set provider='anthropic' to use the anthropic SDK.
    """

    def __init__(
        self,
        vector_store,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
        provider: str = "deepseek",
        top_k: int = 5,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.vector_store = vector_store
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.provider = provider
        self.top_k = top_k
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._prompt = PromptTemplate()

    def _get_openai_client(self):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai required: pip install openai")
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _get_async_openai_client(self):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai required: pip install openai")
        return AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def _get_anthropic_client(self):
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic required: pip install anthropic")
        return anthropic.Anthropic(api_key=self.api_key)

    def embed_batch(self, texts: List[str], embed_fn: Callable) -> List[List[float]]:
        """Generate embeddings for a batch of texts."""
        if not texts:
            return []
        try:
            result = embed_fn(texts)
            if isinstance(result, list) and result and isinstance(result[0], list):
                logger.info("Batch embedded %d texts", len(texts))
                return result
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

        last_error = None
        for attempt in range(self.max_retries):
            try:
                if self.provider == "anthropic":
                    answer = self._call_anthropic(system_prompt, user_prompt)
                else:
                    answer = self._call_openai_compatible(system_prompt, user_prompt)
                sources = [d.metadata.get("source", d.id) for d in docs]
                logger.info("Query answered (attempt %d)", attempt + 1)
                return RagResponse(answer=answer, sources=sources)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait = self.retry_delay * (attempt + 1)
                    logger.warning("LLM API error (attempt %d/%d): %s — retrying in %.1fs",
                                   attempt + 1, self.max_retries, e, wait)
                    time.sleep(wait)
                else:
                    logger.error("LLM API failed after %d attempts: %s", self.max_retries, e)

        raise RuntimeError(f"AI 服务暂时不可用，请稍后重试。({last_error})")

    def _call_openai_compatible(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_openai_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=2048,
        )
        return response.choices[0].message.content

    def _call_anthropic(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_anthropic_client()
        message = client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text

    async def stream(
        self, question: str, namespace: str, embed_fn: Optional[Callable] = None
    ) -> AsyncIterator[str]:
        """Stream answer tokens."""
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

        try:
            if self.provider == "anthropic":
                async for token in self._stream_anthropic(system_prompt, user_prompt):
                    yield token
            else:
                async for token in self._stream_openai_compatible(system_prompt, user_prompt):
                    yield token
        except Exception as e:
            logger.error("Streaming failed: %s", e)
            raise RuntimeError(f"AI 服务暂时不可用，请稍后重试。({e})")

    async def _stream_openai_compatible(self, system_prompt: str, user_prompt: str) -> AsyncIterator[str]:
        client = self._get_async_openai_client()
        stream = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=2048,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _stream_anthropic(self, system_prompt: str, user_prompt: str) -> AsyncIterator[str]:
        client = self._get_anthropic_client()
        with client.messages.stream(
            model=self.model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text
