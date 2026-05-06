from setuptools import setup, find_packages

setup(
    name="vector_store",
    version="0.1.0",
    description="Vector database wrapper for Ray_jr knowledge base",
    author="Ray_jr Team",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.11",
    install_requires=[
        "qdrant-client>=1.7.0",
        "sentence-transformers>=2.2.0",
        "pydantic>=2.0.0",
        "numpy>=1.24.0",
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
