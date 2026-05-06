"""Knowledge base repository sync utility"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from app.config import settings


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

    def clone(self) -> bool:
        """Clone knowledge base repository"""
        if self.is_cloned():
            print(f"Repository already cloned at {self.local_path}")
            return True

        print(f"Cloning {self.repo_url} to {self.local_path}...")
        try:
            subprocess.run(
                ["git", "clone", "-b", self.branch, self.repo_url, str(self.local_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            print("✓ Clone successful")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Clone failed: {e.stderr}")
            return False

    def pull(self) -> bool:
        """Pull latest changes from remote"""
        if not self.is_cloned():
            print("Repository not cloned yet, cloning first...")
            return self.clone()

        print(f"Pulling latest changes from {self.branch}...")
        try:
            subprocess.run(
                ["git", "-C", str(self.local_path), "pull", "origin", self.branch],
                check=True,
                capture_output=True,
                text=True,
            )
            print("✓ Pull successful")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Pull failed: {e.stderr}")
            return False

    def sync(self) -> bool:
        """Sync knowledge base (clone if not exists, pull if exists)"""
        if self.is_cloned():
            return self.pull()
        else:
            return self.clone()

    def get_status(self) -> dict:
        """Get repository status"""
        if not self.is_cloned():
            return {"cloned": False}

        try:
            # Get current commit hash
            commit = subprocess.run(
                ["git", "-C", str(self.local_path), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            # Get last commit message
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


def sync_knowledge_base() -> bool:
    """Convenience function to sync knowledge base"""
    syncer = KnowledgeBaseSync()
    return syncer.sync()
