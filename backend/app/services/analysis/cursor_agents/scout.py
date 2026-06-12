"""Phase 1 scout agent — cloud SDK run per repository."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.analysis.cursor_agents.artifacts import parse_scout_output
from app.services.analysis.cursor_agents.client import run_cloud_prompt
from app.services.analysis.cursor_agents.prompts import build_scout_prompt
from app.services.analysis.triage import build_triage
from app.services.github import GitHubService


@dataclass
class ScoutResult:
    owner: str
    repo: str
    findings_path: Path
    rabbit_holes_path: Path
    triage_path: Path
    run_meta_path: Path
    agent_id: str
    run_id: str
    status: str
    rabbit_holes: list[dict[str, Any]]


async def run_scout(
    github: GitHubService,
    owner: str,
    repo: str,
    username: str,
    data_dir: Path,
) -> ScoutResult:
    analysis_dir = data_dir / "analysis" / owner / repo
    runs_dir = analysis_dir / "runs"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    triage = await build_triage(github, owner, repo, username)
    triage_path = analysis_dir / "triage.json"
    triage_path.write_text(json.dumps(triage, indent=2), encoding="utf-8")

    meta = await github.get_repository(owner, repo)
    branch = meta.get("default_branch") or "main"
    commits_raw = await github.list_commits_all(owner, repo, author=username)

    commits_path = analysis_dir / "commits.json"
    commits_path.write_text(json.dumps(commits_raw, indent=2), encoding="utf-8")

    repo_url = f"https://github.com/{owner}/{repo}"
    prompt = build_scout_prompt(
        owner=owner,
        repo=repo,
        username=username,
        branch=branch,
        triage=triage,
        commits=commits_raw,
    )

    run_meta_path = runs_dir / "scout.json"
    cloud_result = await run_cloud_prompt(
        prompt=prompt,
        repo_url=repo_url,
        branch=branch,
        github_token=github.access_token,
        run_meta_path=run_meta_path,
    )

    if cloud_result.result_text:
        (runs_dir / "scout_response.txt").write_text(cloud_result.result_text, encoding="utf-8")
    if cloud_result.artifacts:
        (runs_dir / "scout_artifacts.json").write_text(
            json.dumps(
                {"paths": cloud_result.artifact_paths, "keys": list(cloud_result.artifacts)},
                indent=2,
            ),
            encoding="utf-8",
        )
        artifacts_dir = runs_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        for path, content in cloud_result.artifacts.items():
            safe_name = path.replace("/", "__")
            (artifacts_dir / safe_name).write_text(content, encoding="utf-8")

    findings_text, rabbit_holes = parse_scout_output(
        cloud_result.result_text or "",
        cloud_result.artifacts,
    )

    findings_path = analysis_dir / "findings.md"
    findings_path.write_text(findings_text, encoding="utf-8")

    rabbit_holes_path = analysis_dir / "rabbit_holes.json"
    rabbit_holes_path.write_text(json.dumps(rabbit_holes, indent=2), encoding="utf-8")

    return ScoutResult(
        owner=owner,
        repo=repo,
        findings_path=findings_path,
        rabbit_holes_path=rabbit_holes_path,
        triage_path=triage_path,
        run_meta_path=run_meta_path,
        agent_id=cloud_result.agent_id,
        run_id=cloud_result.run_id,
        status=cloud_result.status,
        rabbit_holes=rabbit_holes,
    )
