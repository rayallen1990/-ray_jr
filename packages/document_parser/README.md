# Document Parser

Document parsing module for Ray_jr knowledge base platform.

## Overview

Handles parsing of various document formats (PDF, Word, Excel) and extracts text content for knowledge base ingestion.

## Features

- PDF parsing using PyMuPDF
- Word document (.docx) parsing
- Excel spreadsheet (.xlsx) parsing
- Unified text extraction interface
- Metadata extraction (page numbers, sections, etc.)

## Dependencies

- PyMuPDF >= 1.23.0
- python-docx >= 1.0.0
- openpyxl >= 3.1.0
- pydantic >= 2.0.0

## Installation

```bash
pip install -e .
```

## Usage

```python
from document_parser import DocumentParser

parser = DocumentParser()
text = parser.parse_file("path/to/document.pdf")
```

## Development

Install with dev dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```
