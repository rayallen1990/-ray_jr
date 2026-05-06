from setuptools import setup, find_packages

setup(
    name="document_parser",
    version="0.1.0",
    description="Document parsing module for Ray_jr knowledge base",
    author="Ray_jr Team",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.11",
    install_requires=[
        "PyMuPDF>=1.23.0",
        "python-docx>=1.0.0",
        "openpyxl>=3.1.0",
        "pydantic>=2.0.0",
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
