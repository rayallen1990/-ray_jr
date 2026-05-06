"""Word document parser using python-docx"""


class WordParser:
    def parse(self, file_path: str) -> str:
        """Extract text from a Word (.docx) file."""
        try:
            from docx import Document
        except ImportError:
            raise ImportError("python-docx is required: pip install python-docx")

        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
