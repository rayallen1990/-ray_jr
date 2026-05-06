"""Prompt template for RAG engine"""

SYSTEM_PROMPT = """You are an expert assistant for industrial HMI systems, specializing in Weinview (繁易) HMI products.
Answer questions based ONLY on the provided context. If the context doesn't contain enough information, say so clearly.
Always cite the source documents in your answer."""

RAG_TEMPLATE = """Context documents:
{context}

Question: {question}

Answer based on the context above, citing relevant sources:"""


class PromptTemplate:
    def build(self, question: str, documents: list) -> tuple[str, str]:
        """Build system and user prompts from question and retrieved documents.

        Returns:
            (system_prompt, user_prompt)
        """
        context_parts = []
        for i, doc in enumerate(documents, 1):
            source = doc.metadata.get("source", f"Document {i}")
            context_parts.append(f"[{i}] {source}:\n{doc.text}")

        context = "\n\n".join(context_parts)
        user_prompt = RAG_TEMPLATE.format(context=context, question=question)
        return SYSTEM_PROMPT, user_prompt
