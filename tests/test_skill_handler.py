"""Tests for app.api.v1.skill_handler — /kb sync, /kb status, /kb documents."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.kb_sync import SyncResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Return a TestClient wired to the FastAPI app."""
    from app.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /api/v1/kb/sync
# ---------------------------------------------------------------------------

class TestKbSync:
    @patch("app.api.v1.skill_handler.KnowledgeBaseSync")
    def test_sync_no_new_files(self, MockSync: MagicMock, client: TestClient) -> None:
        instance = MockSync.return_value
        instance.sync.return_value = SyncResult(success=True, new_files=[])
        instance.local_path = Path("/tmp/kb")

        resp = client.post("/api/v1/kb/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "up to date" in data["message"].lower()

    @patch("app.api.v1.skill_handler._index_chunks")
    @patch("app.api.v1.skill_handler._parse_and_chunk")
    @patch("app.api.v1.skill_handler.KnowledgeBaseSync")
    def test_sync_with_new_files(
        self,
        MockSync: MagicMock,
        mock_parse: MagicMock,
        mock_index: MagicMock,
        client: TestClient,
    ) -> None:
        instance = MockSync.return_value
        instance.sync.return_value = SyncResult(
            success=True,
            new_files=["guide.pdf", "readme.md"],
        )
        instance.local_path = Path("/tmp/kb")

        mock_parse.return_value = ["chunk1", "chunk2", "chunk3"]

        resp = client.post("/api/v1/kb/sync?tenant_id=tenant-a")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["new_files_count"] == 2
        assert data["total_chunks"] == 6  # 3 chunks × 2 files
        assert len(data["processed"]) == 2
        for p in data["processed"]:
            assert p["status"] == "ok"

    @patch("app.api.v1.skill_handler.KnowledgeBaseSync")
    def test_sync_git_failure(self, MockSync: MagicMock, client: TestClient) -> None:
        instance = MockSync.return_value
        instance.sync.return_value = SyncResult(
            success=False, error="fatal: not a git repo",
        )

        resp = client.post("/api/v1/kb/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["error"] is not None

    @patch("app.api.v1.skill_handler.KnowledgeBaseSync")
    def test_sync_skip_indexing(self, MockSync: MagicMock, client: TestClient) -> None:
        instance = MockSync.return_value
        instance.sync.return_value = SyncResult(
            success=True,
            new_files=["doc.pdf"],
        )
        instance.local_path = Path("/tmp/kb")

        resp = client.post("/api/v1/kb/sync?index=false")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "skipped" in data["message"].lower()
        assert data["new_files_count"] == 1
        assert data["total_chunks"] == 0

    @patch("app.api.v1.skill_handler._parse_and_chunk")
    @patch("app.api.v1.skill_handler.KnowledgeBaseSync")
    def test_sync_parse_error_handled(
        self,
        MockSync: MagicMock,
        mock_parse: MagicMock,
        client: TestClient,
    ) -> None:
        instance = MockSync.return_value
        instance.sync.return_value = SyncResult(
            success=True, new_files=["bad.pdf"],
        )
        instance.local_path = Path("/tmp/kb")
        mock_parse.side_effect = RuntimeError("corrupt PDF")

        resp = client.post("/api/v1/kb/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["processed"][0]["status"] == "error"
        assert "corrupt PDF" in data["processed"][0]["error"]


# ---------------------------------------------------------------------------
# GET /api/v1/kb/status
# ---------------------------------------------------------------------------

class TestKbStatus:
    @patch("app.api.v1.skill_handler.KnowledgeBaseSync")
    def test_status_not_cloned(self, MockSync: MagicMock, client: TestClient) -> None:
        instance = MockSync.return_value
        instance.get_status.return_value = {"cloned": False}

        resp = client.get("/api/v1/kb/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cloned"] is False

    @patch("app.api.v1.skill_handler.KnowledgeBaseSync")
    def test_status_cloned(self, MockSync: MagicMock, client: TestClient) -> None:
        instance = MockSync.return_value
        instance.get_status.return_value = {
            "cloned": True,
            "path": "/tmp/kb",
            "branch": "main",
            "commit": "abc12345",
            "message": "initial commit",
        }
        instance.scan_documents.return_value = ["a.pdf", "b.txt"]

        resp = client.get("/api/v1/kb/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cloned"] is True
        assert data["document_count"] == 2
        assert data["commit"] == "abc12345"


# ---------------------------------------------------------------------------
# GET /api/v1/kb/documents
# ---------------------------------------------------------------------------

class TestKbDocuments:
    @patch("app.api.v1.skill_handler.KnowledgeBaseSync")
    def test_documents_not_cloned(self, MockSync: MagicMock, client: TestClient) -> None:
        instance = MockSync.return_value
        instance.is_cloned.return_value = False

        resp = client.get("/api/v1/kb/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cloned"] is False

    @patch("app.api.v1.skill_handler.KnowledgeBaseSync")
    def test_documents_lists_files(self, MockSync: MagicMock, client: TestClient) -> None:
        instance = MockSync.return_value
        instance.is_cloned.return_value = True
        instance.scan_documents.return_value = ["guide.pdf", "faq.txt"]

        resp = client.get("/api/v1/kb/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cloned"] is True
        assert data["document_count"] == 2
        assert "guide.pdf" in data["documents"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class TestPlainTextParser:
    def test_parse_txt(self, tmp_path: Path) -> None:
        from app.api.v1.skill_handler import _PlainTextParser
        f = tmp_path / "test.txt"
        f.write_text("Hello world", encoding="utf-8")
        parser = _PlainTextParser()
        assert parser.parse(str(f)) == "Hello world"


class TestGetParserForFile:
    def test_pdf(self) -> None:
        from app.api.v1.skill_handler import _get_parser_for_file
        parser = _get_parser_for_file(Path("doc.pdf"))
        assert parser is not None

    def test_docx(self) -> None:
        from app.api.v1.skill_handler import _get_parser_for_file
        parser = _get_parser_for_file(Path("doc.docx"))
        assert parser is not None

    def test_txt(self) -> None:
        from app.api.v1.skill_handler import _get_parser_for_file
        parser = _get_parser_for_file(Path("notes.txt"))
        assert parser is not None

    def test_unsupported(self) -> None:
        from app.api.v1.skill_handler import _get_parser_for_file
        parser = _get_parser_for_file(Path("image.png"))
        assert parser is None
