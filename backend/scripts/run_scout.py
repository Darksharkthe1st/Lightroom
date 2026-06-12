#!/usr/bin/env python3
"""Run the scout agent against a repository.

Usage:
    cd backend
    source .venv/bin/activate
    python scripts/run_scout.py --owner Darksharkthe1st --repo CodeRunner --username Darksharkthe1st
    python scripts/run_scout.py --smoke   # SDK connectivity test only
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Allow imports from backend/app
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

from app.config import settings
from app.services.analysis.cursor_agents.client import smoke_test_connected_repo
from app.services.analysis.cursor_agents.repo_utils import list_connected_repo_urls
from app.services.analysis.cursor_agents.scout import run_scout
from app.services.github import GitHubService


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run Lightroom scout agent")
    parser.add_argument("--owner", default="Darksharkthe1st")
    parser.add_argument("--repo", default="CodeRunner")
    parser.add_argument("--username", default=None, help="GitHub login to analyze commits for")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"), help="GitHub PAT for API access")
    parser.add_argument("--smoke", action="store_true", help="Run SDK smoke test only")
    args = parser.parse_args()

    username = args.username or args.owner

    if not settings.cursor_configured:
        print("ERROR: CURSOR_API_KEY is not set in backend/.env", file=sys.stderr)
        return 1

    if args.smoke:
        connected = await list_connected_repo_urls()
        if not connected:
            print(
                "ERROR: No GitHub repos connected to Cursor.\n"
                "Connect GitHub in Cursor Dashboard → Integrations, then retry.",
                file=sys.stderr,
            )
            return 1
        print(f"Connected repos ({len(connected)}): {', '.join(connected[:5])}")
        print("Running SDK smoke test against a connected repo...")
        result = await smoke_test_connected_repo(github_token=args.token)
        print(
            f"OK — repo={result.repo_url} branch={result.branch} "
            f"agent_id={result.agent_id} run_id={result.run_id} status={result.status}"
        )
        if result.result_text:
            print(result.result_text[:500])
        return 0

    if not args.token:
        print(
            "ERROR: GITHUB_TOKEN is required for triage/commit fetch.\n"
            "Export a PAT with repo scope, or pass --token.",
            file=sys.stderr,
        )
        return 1

    github = GitHubService(args.token)
    data_dir = BACKEND_ROOT / settings.data_dir

    print(f"Scout starting: {args.owner}/{args.repo} (user=@{username})")
    print(f"Model: {settings.cursor_model}")
    print("This may take several minutes (cloud agent)...")

    result = await run_scout(github, args.owner, args.repo, username, data_dir)

    print(f"\nDone — status={result.status}")
    print(f"  agent_id:  {result.agent_id}")
    print(f"  run_id:    {result.run_id}")
    print(f"  findings:  {result.findings_path}")
    print(f"  rabbit holes: {result.rabbit_holes_path} ({len(result.rabbit_holes)} planned)")
    print(f"  triage:    {result.triage_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
