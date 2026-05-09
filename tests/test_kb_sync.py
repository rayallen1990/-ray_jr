"""Tests for app.kb_sync — KnowledgeBaseSync and SyncResult."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.kb_sync import KnowledgeBaseSync, SyncResult, SUPPORTED_EXTENSIONS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Create a minimal fake git repo directory."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    return tmp_path


@pytest.fixture()
def syncer(tmp_path: Path) -> KnowledgeBaseSync:
    """Return a KnowledgeBaseSync pointed at *tmp_path* (not yet cloned)."""
    return KnowledgeBaseSync(
        repo_url="https://example.com/repo.git",
        local_path=str(tmp_path / "kb"),
        branch="main",
    )


# ---------------------------------------------------------------------------
# SyncResult dataclass
# ---------------------------------------------------------------------------

class TestSyncResult:
    def test_defaults(self) -> None:
        r = SyncResult(success=True)
        assert r.success is True
        assert r.is_fresh_clone is False
        assert r.new_files == []
        assert r.modified_files == []
        assert r.error is None

    def test_with_files(self) -> None:
        r = SyncResult(success=True, new_files=["a.pdf", "b.docx"])
        assert len(r.new_files) == 2


# ---------------------------------------------------------------------------
# is_cloned
# ---------------------------------------------------------------------------

class TestIsCloned:
    def test_not_cloned(self, syncer: KnowledgeBaseSync) -> None:
        assert syncer.is_cloned() is False

    def test_cloned(self, tmp_path: Path) -> None:
        repo_dir = tmp_path / "kb"
        (repo_dir / ".git").mkdir(parents=True)
        s = KnowledgeBaseSync(
            repo_url="https://example.com/repo.git",
            local_path=str(repo_dir),
            branch="main",
        )
        assert s.is_cloned() is True


# ---------------------------------------------------------------------------
# scan_documents
# ---------------------------------------------------------------------------

class TestScanDocuments:
    def test_empty_dir(self, syncer: KnowledgeBaseSync) -> None:
        assert syncer.scan_documents() == []

    def test_finds_supported_files(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "readme.pdf").write_bytes(b"%PDF")
        (kb_dir / "notes.txt").write_text("hello")
        (kb_dir / "image.png").write_bytes(b"\x89PNG")  # unsupported

        s = KnowledgeBaseSync(
            repo_url="x", local_path=str(kb_dir), branch="main",
        )
        docs = s.scan_documents()
        assert "readme.pdf" in docs
        assert "notes.txt" in docs
        assert "image.png" not in docs

    def test_ignores_git_dir(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        (kb_dir / ".git" / "objects").mkdir(parents=True)
        (kb_dir / ".git" / "info.txt").write_text("internal")
        (kb_dir / "doc.md").write_text("# Hi")

        s = KnowledgeBaseSync(
            repo_url="x", local_path=str(kb_dir), branch="main",
        )
        docs = s.scan_documents()
        assert "doc.md" in docs
        assert not any(".git" in d for d in docs)


# ---------------------------------------------------------------------------
# clone
# ---------------------------------------------------------------------------

class TestClone:
    @patch("app.kb_sync.subprocess.run")
    def test_clone_success(
        self, mock_run: MagicMock, syncer: KnowledgeBaseSync, tmp_path: Path,
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        # Simulate the .git dir being created during clone
        git_dir = syncer.local_path / ".git"
        git_dir.mkdir(parents=True)

        result = syncer.clone()
        assert result.success is True
        assert result.is_fresh_clone is True
        mock_run.assert_called_once()

    @patch("app.kb_sync.subprocess.run")
    def test_clone_failure(self, mock_run: MagicMock, syncer: KnowledgeBaseSync) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "git clone", stderr="fatal: repo not found",
        )
        result = syncer.clone()
        assert result.success is False
        assert result.error is not None

    def test_clone_already_cloned(self, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        (kb_dir / ".git").mkdir(parents=True)
        s = KnowledgeBaseSync(repo_url="x", local_path=str(kb_dir), branch="main")
        result = s.clone()
        assert result.success is True
        assert result.is_fresh_clone is False


# ---------------------------------------------------------------------------
# pull
# ---------------------------------------------------------------------------

class TestPull:
    @patch("app.kb_sync.subprocess.run")
    def test_pull_no_changes(self, mock_run: MagicMock, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        (kb_dir / ".git").mkdir(parents=True)
        s = KnowledgeBaseSync(repo_url="x", local_path=str(kb_dir), branch="main")

        # Both HEAD calls return the same commit → no changes
        mock_run.return_value = MagicMock(
            returncode=0, stdout="abc123\n",
        )
        result = s.pull()
        assert result.success is True
        assert result.new_files == []

    @patch("app.kb_sync.subprocess.run")
    def test_pull_with_new_files(self, mock_run: MagicMock, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        (kb_dir / ".git").mkdir(parents=True)
        s = KnowledgeBaseSync(repo_url="x", local_path=str(kb_dir), branch="main")

        # Simulate: before=aaa, pull ok, after=bbb, diff lists two files
        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            cmd = args[0] if args else kwargs.get("args", [])
            m = MagicMock(returncode=0)
            if "rev-parse" in cmd:
                # First call → before, second → after
                if call_count["n"] <= 1:
                    m.stdout = "aaa111\n"
                else:
                    m.stdout = "bbb222\n"
            elif "pull" in cmd:
                m.stdout = ""
            elif "diff" in cmd:
                m.stdout = "docs/guide.pdf\nREADME.md\nimage.png\n"
            return m

        mock_run.side_effect = side_effect
        result = s.pull()
        assert result.success is True
        # image.png not in SUPPORTED_EXTENSIONS so should be filtered out
        assert "docs/guide.pdf" in result.new_files
        assert "README.md" in result.new_files
        assert "image.png" not in result.new_files

    @patch("app.kb_sync.subprocess.run")
    def test_pull_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        (kb_dir / ".git").mkdir(parents=True)
        s = KnowledgeBaseSync(repo_url="x", local_path=str(kb_dir), branch="main")

        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            cmd = args[0] if args else kwargs.get("args", [])
            if "rev-parse" in cmd:
                return MagicMock(returncode=0, stdout="aaa\n")
            if "pull" in cmd:
                raise subprocess.CalledProcessError(1, "git pull", stderr="merge conflict")
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = side_effect
        result = s.pull()
        assert result.success is False


# ---------------------------------------------------------------------------
# sync delegates correctly
# ---------------------------------------------------------------------------

class TestSync:
    @patch.object(KnowledgeBaseSync, "pull")
    def test_sync_pulls_when_cloned(self, mock_pull: MagicMock, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        (kb_dir / ".git").mkdir(parents=True)
        s = KnowledgeBaseSync(repo_url="x", local_path=str(kb_dir), branch="main")
        mock_pull.return_value = SyncResult(success=True)
        result = s.sync()
        mock_pull.assert_called_once()
        assert result.success is True

    @patch.object(KnowledgeBaseSync, "clone")
    def test_sync_clones_when_not_cloned(
        self, mock_clone: MagicMock, syncer: KnowledgeBaseSync,
    ) -> None:
        mock_clone.return_value = SyncResult(success=True, is_fresh_clone=True)
        result = syncer.sync()
        mock_clone.assert_called_once()
        assert result.is_fresh_clone is True


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_not_cloned(self, syncer: KnowledgeBaseSync) -> None:
        status = syncer.get_status()
        assert status == {"cloned": False}

    @patch("app.kb_sync.subprocess.run")
    def test_cloned(self, mock_run: MagicMock, tmp_path: Path) -> None:
        kb_dir = tmp_path / "kb"
        (kb_dir / ".git").mkdir(parents=True)
        s = KnowledgeBaseSync(repo_url="x", local_path=str(kb_dir), branch="main")

        mock_run.return_value = MagicMock(
            returncode=0, stdout="abcdef1234567890\n",
        )
        status = s.get_status()
        assert status["cloned"] is True
        assert "commit" in status
