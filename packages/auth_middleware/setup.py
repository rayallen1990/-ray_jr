from setuptools import setup, find_packages

setup(
    name="auth_middleware",
    version="0.1.0",
    description="Authentication middleware for Ray_jr knowledge base",
    author="Ray_jr Team",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.11",
    install_requires=[
        "fastapi>=0.104.0",
        "python-jose[cryptography]>=3.3.0",
        "bcrypt>=4.0.0",
        "pydantic>=2.0.0",
        "python-multipart>=0.0.6",
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
