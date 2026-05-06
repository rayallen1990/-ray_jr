#!/usr/bin/env python3
"""Command-line tool to sync knowledge base repository"""

import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.kb_sync import KnowledgeBaseSync


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Sync knowledge base repository")
    parser.add_argument(
        "--status", action="store_true", help="Show repository status"
    )
    parser.add_argument(
        "--clone", action="store_true", help="Clone repository (if not exists)"
    )
    parser.add_argument(
        "--pull", action="store_true", help="Pull latest changes"
    )
    parser.add_argument(
        "--repo", type=str, help="Override repository URL"
    )
    parser.add_argument(
        "--path", type=str, help="Override local path"
    )
    parser.add_argument(
        "--branch", type=str, help="Override branch name"
    )

    args = parser.parse_args()

    syncer = KnowledgeBaseSync(
        repo_url=args.repo,
        local_path=args.path,
        branch=args.branch,
    )

    if args.status:
        status = syncer.get_status()
        print("Knowledge Base Status:")
        for key, value in status.items():
            print(f"  {key}: {value}")
        return

    if args.clone:
        success = syncer.clone()
        sys.exit(0 if success else 1)

    if args.pull:
        success = syncer.pull()
        sys.exit(0 if success else 1)

    # Default: sync (clone or pull)
    success = syncer.sync()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
