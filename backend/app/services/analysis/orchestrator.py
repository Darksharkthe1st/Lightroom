"""Coordinates per-repo agents and aggregates resume bullets."""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.models.schemas import AnalysisStatus, ResumeBullet, ResumeResponse
from app.services.analysis.repo_agent import RepoAgent
from app.services.github import GitHubService

# In-memory job tracking for MVP
_jobs: dict[str, dict] = {}


class AnalysisOrchestrator:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _job_key(self, username: str) -> str:
        return f"user:{username}"

    def get_status(self, username: str) -> ResumeResponse:
        job = _jobs.get(self._job_key(username))
        if not job:
            return ResumeResponse(
                username=username,
                bullets=[],
                status=AnalysisStatus.PENDING,
                message="No analysis started yet.",
            )
        return ResumeResponse(
            username=username,
            bullets=job.get("bullets", []),
            status=job["status"],
            message=job.get("message"),
        )

    async def analyze_repositories(
        self,
        github: GitHubService,
        username: str,
        repo_full_names: list[str],
    ) -> ResumeResponse:
        key = self._job_key(username)
        _jobs[key] = {
            "status": AnalysisStatus.RUNNING,
            "bullets": [],
            "message": f"Analyzing {len(repo_full_names)} repositories...",
        }

        all_bullets: list[ResumeBullet] = []

        async def analyze_one(full_name: str) -> list[ResumeBullet]:
            owner, repo = full_name.split("/", 1)
            agent = RepoAgent(github, owner, repo, username, self.data_dir)
            try:
                _, bullets = await agent.run()
                return bullets
            except Exception as exc:
                return [
                    ResumeBullet(
                        text=f"Could not fully analyze {full_name}: {exc}",
                        source_repo=full_name,
                        evidence=[],
                    )
                ]

        results = await asyncio.gather(*(analyze_one(name) for name in repo_full_names))
        for bullets in results:
            all_bullets.extend(bullets)

        _jobs[key] = {
            "status": AnalysisStatus.COMPLETED,
            "bullets": all_bullets,
            "message": f"Analyzed {len(repo_full_names)} repositories.",
        }

        return ResumeResponse(
            username=username,
            bullets=all_bullets,
            status=AnalysisStatus.COMPLETED,
            message=_jobs[key]["message"],
        )

    async def analyze_single_repository(
        self,
        github: GitHubService,
        username: str,
        owner: str,
        repo: str,
    ) -> ResumeResponse:
        return await self.analyze_repositories(github, username, [f"{owner}/{repo}"])
