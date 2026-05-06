from setuptools import setup, find_packages

setup(
    name="rag_engine",
    version="0.1.0",
    description="RAG dialogue engine for Ray_jr knowledge base",
    author="Ray_jr Team",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.11",
    install_requires=[
        "langchain>=0.1.0",
        "anthropic>=0.18.0",
        "openai>=1.12.0",
        "pydantic>=2.0.0",
        "tiktoken>=0.5.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
        ],
    },
)
