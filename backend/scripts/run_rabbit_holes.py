#!/usr/bin/env python3
"""Run rabbit-hole agents for scout-recommended signals.

Usage:
    cd backend
    source .venv/bin/activate
    python scripts/run_rabbit_holes.py --owner Darksharkthe1st --repo CodeRunner
    python scripts/run_rabbit_holes.py --signal-id docker_execution_queue
    python scripts/run_rabbit_holes.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

from app.config import settings
from app.services.analysis.cursor_agents.rabbit_hole import run_rabbit_holes
from app.services.github import GitHubService


def _status_icon(status: str) -> str:
    return {"finished": "✓", "skipped": "○", "error": "✗", "dry_run": "·"}.get(status, "?")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run Lightroom rabbit-hole agents")
    parser.add_argument("--owner", default="Darksharkthe1st")
    parser.add_argument("--repo", default="CodeRunner")
    parser.add_argument("--username", default=None, help="GitHub login to analyze commits for")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"), help="GitHub PAT for API access")
    parser.add_argument("--max-holes", type=int, default=None, help="Max holes to run (default: config)")
    parser.add_argument("--signal-id", default=None, help="Run a single signal only")
    parser.add_argument("--force", action="store_true", help="Re-run even if signals/*.md exists")
    parser.add_argument("--dry-run", action="store_true", help="Print selected holes without SDK calls")
    args = parser.parse_args()

    username = args.username or args.owner

    if not settings.cursor_configured:
        print("ERROR: CURSOR_API_KEY is not set in backend/.env", file=sys.stderr)
        return 1

    if not args.dry_run and not args.token:
        print(
            "ERROR: GITHUB_TOKEN is required.\n"
            "Export a PAT with repo scope, or pass --token.",
            file=sys.stderr,
        )
        return 1

    github = GitHubService(args.token or "")
    data_dir = BACKEND_ROOT / settings.data_dir

    print(f"Rabbit holes: {args.owner}/{args.repo} (user=@{username})")
    print(f"Model: {settings.cursor_model}")
    if args.dry_run:
        print("Dry run — no SDK calls.")
    else:
        print("This may take several minutes per signal (cloud agents)...")

    try:
        result = await run_rabbit_holes(
            github,
            args.owner,
            args.repo,
            username,
            data_dir,
            max_holes=args.max_holes,
            signal_id=args.signal_id,
            force=args.force,
            dry_run=args.dry_run,
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    finished = sum(1 for r in result.results if r.status == "finished")
    errors = sum(1 for r in result.results if r.status == "error")
    skipped = sum(1 for r in result.results if r.status == "skipped")

    print(f"\nDone — {len(result.results)} selected, {finished} finished, {skipped} skipped, {errors} error(s)")
    for item in result.results:
        path = item.signal_path or result.signals_dir / f"{item.signal_id}.md"
        line = f"  {_status_icon(item.status)} {item.signal_id}"
        if item.status in ("finished", "skipped"):
            line += f"  → {path}"
        elif item.error:
            line += f"  → {item.error}"
        print(line)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
