"""RAG dialogue engine with vector retrieval and LLM generation"""

from .engine import RagEngine
from .prompt import PromptTemplate

__all__ = ["RagEngine", "PromptTemplate"]
