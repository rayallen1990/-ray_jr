"""PDF document parser using PyMuPDF"""

from typing import List


class PdfParser:
    def parse(self, file_path: str) -> str:
        """Extract text from a PDF file. Returns full text content."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("PyMuPDF is required: pip install pymupdf")

        text_parts: List[str] = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text_parts.append(page.get_text())
        return "\n".join(text_parts)
