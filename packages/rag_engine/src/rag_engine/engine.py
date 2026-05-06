"""RAG engine core - retrieval + generation with retry"""

import time
from typing import List, AsyncIterator
from dataclasses import dataclass

from .prompt import PromptTemplate


@dataclass
class RagResponse:
    answer: str
    sources: List[str]


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

    def _embed(self, text: str) -> List[float]:
        """Placeholder embedding - replace with real embedding model"""
        raise NotImplementedError("Provide an embedding function via embed_fn parameter")

    def query(
        self, question: str, namespace: str, embed_fn=None
    ) -> RagResponse:
        """Retrieve relevant docs and generate answer with retry on API errors."""
        if embed_fn is None:
            raise ValueError("embed_fn is required to embed the query")

        query_vector = embed_fn(question)
        docs = self.vector_store.search(query_vector, namespace=namespace, top_k=self.top_k)

        system_prompt, user_prompt = self._prompt.build(question, docs)
        client = self._get_client()

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
                return RagResponse(answer=answer, sources=sources)
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise

    async def stream(
        self, question: str, namespace: str, embed_fn=None
    ) -> AsyncIterator[str]:
        """Stream answer tokens via Claude streaming API."""
        if embed_fn is None:
            raise ValueError("embed_fn is required")

        query_vector = embed_fn(question)
        docs = self.vector_store.search(query_vector, namespace=namespace, top_k=self.top_k)
        system_prompt, user_prompt = self._prompt.build(question, docs)
        client = self._get_client()

        with client.messages.stream(
            model=self.model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text
