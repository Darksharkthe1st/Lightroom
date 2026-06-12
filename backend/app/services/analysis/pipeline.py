"""Run scout + rabbit-hole pipeline for a repository."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.services.analysis.artifact_loader import (
    load_repo_analysis,
    scout_artifacts_ready,
)
from app.services.analysis.cursor_agents.rabbit_hole import run_rabbit_holes
from app.services.analysis.cursor_agents.repo_utils import assert_repo_connected, normalize_repo_url
from app.services.analysis.cursor_agents.scout import run_scout
from app.services.github import GitHubService

_repo_jobs: dict[str, dict[str, Any]] = {}


def job_key(owner: str, repo: str) -> str:
    return f"{owner}/{repo}"


def get_repo_job(owner: str, repo: str) -> dict[str, Any] | None:
    return _repo_jobs.get(job_key(owner, repo))


def _set_job(owner: str, repo: str, **fields: Any) -> None:
    key = job_key(owner, repo)
    current = dict(_repo_jobs.get(key, {}))
    current.update(fields)
    _repo_jobs[key] = current


async def run_repo_pipeline(
    github: GitHubService,
    owner: str,
    repo: str,
    username: str,
) -> None:
    """Scout then rabbit holes; updates in-memory job status for polling."""
    key = job_key(owner, repo)
    data_dir = settings.data_path
    repo_url = normalize_repo_url(f"https://github.com/{owner}/{repo}")

    try:
        if not settings.cursor_configured:
            raise ValueError(
                "CURSOR_API_KEY is not set on the server. Add it to backend/.env."
            )

        await assert_repo_connected(repo_url)

        if not scout_artifacts_ready(owner, repo, data_dir):
            _set_job(
                owner,
                repo,
                status="running",
                phase="scout",
                message="Scout agent exploring the repository (about 2–3 minutes)…",
            )
            await run_scout(github, owner, repo, username, data_dir)

        analysis = load_repo_analysis(data_dir, owner, repo)

        holes_to_run = analysis.rabbit_holes_planned - analysis.rabbit_holes_complete
        if holes_to_run > 0 or (scout_artifacts_ready(owner, repo, data_dir) and analysis.rabbit_holes_complete == 0):
            _set_job(
                owner,
                repo,
                status="running",
                phase="rabbit_holes",
                message=f"Running deep-dive agents ({settings.cursor_rabbit_hole_max} max in parallel)…",
            )
            await run_rabbit_holes(github, owner, repo, username, data_dir)

        final = load_repo_analysis(data_dir, owner, repo)
        _set_job(
            owner,
            repo,
            status="completed",
            phase="done",
            message=(
                f"Analysis complete — {len(final.bullets)} resume bullet(s), "
                f"{final.rabbit_holes_complete} deep dive(s)."
            ),
        )
    except Exception as exc:
        _set_job(
            owner,
            repo,
            status="failed",
            phase="failed",
            message=str(exc),
            error=str(exc),
        )
        raise


def is_job_running(owner: str, repo: str) -> bool:
    job = get_repo_job(owner, repo)
    return bool(job and job.get("status") == "running")
