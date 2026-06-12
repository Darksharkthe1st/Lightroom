"""Phase 2 rabbit-hole agents — parallel deep dives per scout signal."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.analysis.cursor_agents.artifacts import parse_rabbit_hole_output
from app.services.analysis.cursor_agents.client import run_cloud_prompt
from app.services.analysis.cursor_agents.errors import AgentRunError
from app.services.analysis.cursor_agents.prompts import build_rabbit_hole_prompt
from app.services.github import GitHubService


@dataclass
class RabbitHoleResult:
    signal_id: str
    display_name: str
    status: str
    signal_path: Path | None
    run_meta_path: Path | None
    agent_id: str | None
    run_id: str | None
    error: str | None


@dataclass
class RabbitHolesRunResult:
    owner: str
    repo: str
    results: list[RabbitHoleResult]
    signals_dir: Path


def select_holes(
    rabbit_holes: list[dict[str, Any]],
    triage: dict[str, Any],
    *,
    max_holes: int | None = None,
    min_confidence: float | None = None,
    signal_id: str | None = None,
) -> list[dict[str, Any]]:
    """Pick rabbit holes to run, respecting gating rules and caps."""
    if not triage.get("worth_deep_analysis", True):
        return []

    max_holes = max_holes if max_holes is not None else settings.cursor_rabbit_hole_max
    min_confidence = (
        min_confidence
        if min_confidence is not None
        else settings.cursor_rabbit_hole_min_confidence
    )

    holes = [h for h in rabbit_holes if isinstance(h, dict) and h.get("signal_id")]
    if signal_id:
        holes = [h for h in holes if h.get("signal_id") == signal_id]

    holes = [
        h
        for h in holes
        if float(h.get("confidence") or 0) >= min_confidence
    ]
    holes.sort(
        key=lambda h: (
            int(h.get("priority") or 99),
            -float(h.get("confidence") or 0),
        ),
    )
    return holes[:max_holes]


def _findings_excerpt(findings: str, *, max_chars: int = 4000) -> str:
    if len(findings) <= max_chars:
        return findings

    sections: list[str] = []
    for heading in ("## Overview", "## Stack", "## User contributions", "## Architecture"):
        if heading in findings:
            start = findings.index(heading)
            end = len(findings)
            for other in ("## Overview", "## Stack", "## Architecture", "## User contributions", "## Recruiter signals", "## Notes"):
                if other != heading and other in findings[start + 1 :]:
                    end = min(end, findings.index(other, start + 1))
            sections.append(findings[start:end].strip())

    excerpt = "\n\n".join(sections).strip()
    if not excerpt:
        excerpt = findings[:max_chars]
    if len(excerpt) > max_chars:
        excerpt = excerpt[: max_chars - 3] + "..."
    return excerpt


def _commits_for_hole(
    commits: list[dict[str, Any]],
    search_paths: list[str],
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    if not search_paths:
        return commits[:limit]

    keywords: list[str] = []
    for path in search_paths:
        parts = path.replace("\\", "/").rstrip("/").split("/")
        keywords.append(parts[-1].lower())
        if len(parts) > 1:
            keywords.append(parts[-2].lower())

    matched: list[dict[str, Any]] = []
    for item in commits:
        msg = item.get("commit", {}).get("message", "").lower()
        if any(kw in msg for kw in keywords if kw and len(kw) > 2):
            matched.append(item)

    return (matched or commits)[:limit]


def _write_run_meta(
    path: Path,
    *,
    signal_id: str,
    status: str,
    agent_id: str | None = None,
    run_id: str | None = None,
    duration_ms: int | None = None,
    repo_url: str | None = None,
    branch: str | None = None,
    error: str | None = None,
    artifact_paths: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "signal_id": signal_id,
        "status": status,
        "agent_id": agent_id,
        "run_id": run_id,
        "duration_ms": duration_ms,
        "repo_url": repo_url,
        "branch": branch,
        "artifact_paths": artifact_paths or [],
    }
    if error:
        payload["error"] = error
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


async def run_single_hole(
    *,
    github: GitHubService,
    owner: str,
    repo: str,
    username: str,
    branch: str,
    hole: dict[str, Any],
    findings: str,
    commits: list[dict[str, Any]],
    runs_dir: Path,
    signals_dir: Path,
    force: bool = False,
) -> RabbitHoleResult:
    signal_id = str(hole.get("signal_id", "unknown"))
    display_name = str(hole.get("display_name", signal_id))
    signal_path = signals_dir / f"{signal_id}.md"
    run_meta_path = runs_dir / f"{signal_id}.json"

    if signal_path.exists() and not force:
        return RabbitHoleResult(
            signal_id=signal_id,
            display_name=display_name,
            status="skipped",
            signal_path=signal_path,
            run_meta_path=run_meta_path if run_meta_path.exists() else None,
            agent_id=None,
            run_id=None,
            error=None,
        )

    repo_url = f"https://github.com/{owner}/{repo}"
    search_paths = hole.get("search_paths") or []
    relevant_commits = _commits_for_hole(commits, search_paths)
    prompt = build_rabbit_hole_prompt(
        owner=owner,
        repo=repo,
        username=username,
        branch=branch,
        hole=hole,
        findings_excerpt=_findings_excerpt(findings),
        commits=relevant_commits,
    )

    try:
        cloud_result = await run_cloud_prompt(
            prompt=prompt,
            repo_url=repo_url,
            branch=branch,
            github_token=github.access_token,
            run_meta_path=run_meta_path,
        )
    except AgentRunError as exc:
        _write_run_meta(
            run_meta_path,
            signal_id=signal_id,
            status="error",
            agent_id=exc.agent_id,
            run_id=exc.run_id,
            repo_url=repo_url,
            branch=branch,
            error=str(exc),
        )
        return RabbitHoleResult(
            signal_id=signal_id,
            display_name=display_name,
            status="error",
            signal_path=None,
            run_meta_path=run_meta_path,
            agent_id=exc.agent_id,
            run_id=exc.run_id,
            error=str(exc),
        )
    except Exception as exc:
        _write_run_meta(
            run_meta_path,
            signal_id=signal_id,
            status="error",
            repo_url=repo_url,
            branch=branch,
            error=str(exc),
        )
        return RabbitHoleResult(
            signal_id=signal_id,
            display_name=display_name,
            status="error",
            signal_path=None,
            run_meta_path=run_meta_path,
            agent_id=None,
            run_id=None,
            error=str(exc),
        )

    response_path = runs_dir / f"{signal_id}_response.txt"
    if cloud_result.result_text:
        response_path.write_text(cloud_result.result_text, encoding="utf-8")

    signal_text = parse_rabbit_hole_output(
        cloud_result.result_text or "",
        cloud_result.artifacts,
        signal_id=signal_id,
    )
    signal_path.write_text(signal_text, encoding="utf-8")

    return RabbitHoleResult(
        signal_id=signal_id,
        display_name=display_name,
        status=cloud_result.status,
        signal_path=signal_path,
        run_meta_path=run_meta_path,
        agent_id=cloud_result.agent_id,
        run_id=cloud_result.run_id,
        error=None,
    )


async def run_rabbit_holes(
    github: GitHubService,
    owner: str,
    repo: str,
    username: str,
    data_dir: Path,
    *,
    max_holes: int | None = None,
    min_confidence: float | None = None,
    signal_id: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> RabbitHolesRunResult:
    analysis_dir = data_dir / "analysis" / owner / repo
    runs_dir = analysis_dir / "runs"
    signals_dir = analysis_dir / "signals"
    rabbit_holes_path = analysis_dir / "rabbit_holes.json"
    findings_path = analysis_dir / "findings.md"
    triage_path = analysis_dir / "triage.json"
    commits_path = analysis_dir / "commits.json"

    if not rabbit_holes_path.exists():
        raise FileNotFoundError(
            f"Missing {rabbit_holes_path}. Run scout first: "
            f"python scripts/run_scout.py --owner {owner} --repo {repo}"
        )
    if not findings_path.exists():
        raise FileNotFoundError(f"Missing {findings_path}. Run scout first.")

    rabbit_holes = json.loads(rabbit_holes_path.read_text(encoding="utf-8"))
    if not isinstance(rabbit_holes, list):
        raise ValueError(f"Invalid rabbit_holes.json: expected a JSON array")

    findings = findings_path.read_text(encoding="utf-8")
    triage: dict[str, Any] = {}
    if triage_path.exists():
        triage = json.loads(triage_path.read_text(encoding="utf-8"))

    selected = select_holes(
        rabbit_holes,
        triage,
        max_holes=max_holes,
        min_confidence=min_confidence,
        signal_id=signal_id,
    )

    signals_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        return RabbitHolesRunResult(
            owner=owner,
            repo=repo,
            results=[
                RabbitHoleResult(
                    signal_id=str(h.get("signal_id")),
                    display_name=str(h.get("display_name", h.get("signal_id"))),
                    status="dry_run",
                    signal_path=signals_dir / f"{h.get('signal_id')}.md",
                    run_meta_path=None,
                    agent_id=None,
                    run_id=None,
                    error=None,
                )
                for h in selected
            ],
            signals_dir=signals_dir,
        )

    if commits_path.exists():
        commits_raw = json.loads(commits_path.read_text(encoding="utf-8"))
    else:
        commits_raw = await github.list_commits_all(owner, repo, author=username)
        commits_path.write_text(json.dumps(commits_raw, indent=2), encoding="utf-8")

    branch = triage.get("branch")
    if not branch:
        meta = await github.get_repository(owner, repo)
        branch = meta.get("default_branch") or "main"

    sem = asyncio.Semaphore(settings.cursor_rabbit_hole_max)

    async def _run_one(hole: dict[str, Any]) -> RabbitHoleResult:
        async with sem:
            return await run_single_hole(
                github=github,
                owner=owner,
                repo=repo,
                username=username,
                branch=branch,
                hole=hole,
                findings=findings,
                commits=commits_raw,
                runs_dir=runs_dir,
                signals_dir=signals_dir,
                force=force,
            )

    results = list(await asyncio.gather(*[_run_one(h) for h in selected]))

    return RabbitHolesRunResult(
        owner=owner,
        repo=repo,
        results=results,
        signals_dir=signals_dir,
    )
