"""Knowledge base repository sync utility"""

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}


@dataclass
class SyncResult:
    """Result of a sync operation"""

    success: bool
    is_fresh_clone: bool = False
    new_files: List[str] = field(default_factory=list)
    modified_files: List[str] = field(default_factory=list)
    error: Optional[str] = None


class KnowledgeBaseSync:
    """Sync knowledge base from external Git repository"""

    def __init__(
        self,
        repo_url: Optional[str] = None,
        local_path: Optional[str] = None,
        branch: Optional[str] = None,
    ):
        self.repo_url = repo_url or settings.knowledge_base_repo
        self.local_path = Path(local_path or settings.knowledge_base_path)
        self.branch = branch or settings.knowledge_base_branch

    def is_cloned(self) -> bool:
        """Check if repository is already cloned"""
        return (self.local_path / ".git").exists()

    def _get_head_commit(self) -> Optional[str]:
        """Return the current HEAD commit hash, or None if unavailable."""
        try:
            return subprocess.run(
                ["git", "-C", str(self.local_path), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def _changed_files_between(self, old_commit: str, new_commit: str) -> List[str]:
        """Return list of added/modified files between two commits."""
        try:
            result = subprocess.run(
                [
                    "git", "-C", str(self.local_path),
                    "diff", "--name-only", "--diff-filter=AM",
                    old_commit, new_commit,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return [f for f in result.stdout.strip().splitlines() if f]
        except subprocess.CalledProcessError:
            return []

    def clone(self) -> SyncResult:
        """Clone knowledge base repository"""
        if self.is_cloned():
            logger.info("Repository already cloned at %s", self.local_path)
            return SyncResult(success=True)

        logger.info("Cloning %s to %s ...", self.repo_url, self.local_path)
        try:
            subprocess.run(
                ["git", "clone", "-b", self.branch, self.repo_url, str(self.local_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("Clone successful")
            # On fresh clone every supported file is "new"
            new_files = self.scan_documents()
            return SyncResult(success=True, is_fresh_clone=True, new_files=new_files)
        except subprocess.CalledProcessError as e:
            logger.error("Clone failed: %s", e.stderr)
            return SyncResult(success=False, error=e.stderr)

    def pull(self) -> SyncResult:
        """Pull latest changes from remote"""
        if not self.is_cloned():
            logger.info("Repository not cloned yet, cloning first...")
            return self.clone()

        before = self._get_head_commit()
        logger.info("Pulling latest changes from %s ...", self.branch)
        try:
            subprocess.run(
                ["git", "-C", str(self.local_path), "pull", "origin", self.branch],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error("Pull failed: %s", e.stderr)
            return SyncResult(success=False, error=e.stderr)

        after = self._get_head_commit()
        if before and after and before != after:
            changed = self._changed_files_between(before, after)
            new_files = [
                f for f in changed
                if Path(f).suffix.lower() in SUPPORTED_EXTENSIONS
            ]
            return SyncResult(success=True, new_files=new_files)

        return SyncResult(success=True)

    def sync(self) -> SyncResult:
        """Sync knowledge base (clone if not exists, pull if exists)"""
        if self.is_cloned():
            return self.pull()
        return self.clone()

    def scan_documents(self) -> List[str]:
        """Scan local path for all supported document files (relative paths)."""
        if not self.local_path.exists():
            return []
        results: List[str] = []
        for ext in SUPPORTED_EXTENSIONS:
            for p in self.local_path.rglob(f"*{ext}"):
                if p.is_file() and ".git" not in p.parts:
                    results.append(str(p.relative_to(self.local_path)))
        return sorted(results)

    def get_status(self) -> dict:
        """Get repository status"""
        if not self.is_cloned():
            return {"cloned": False}

        try:
            commit = self._get_head_commit() or "unknown"
            message = subprocess.run(
                ["git", "-C", str(self.local_path), "log", "-1", "--pretty=%B"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            return {
                "cloned": True,
                "path": str(self.local_path),
                "branch": self.branch,
                "commit": commit[:8],
                "message": message,
            }
        except subprocess.CalledProcessError:
            return {"cloned": True, "error": "Failed to get status"}


def sync_knowledge_base() -> SyncResult:
    """Convenience function to sync knowledge base"""
    syncer = KnowledgeBaseSync()
    return syncer.sync()
