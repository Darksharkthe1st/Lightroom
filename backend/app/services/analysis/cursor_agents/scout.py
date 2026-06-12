"""Phase 1 scout agent — cloud SDK run per repository."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    commits_raw = await github.list_commits(owner, repo, author=username, per_page=30)

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

    findings_text, rabbit_holes = _parse_scout_output(cloud_result.result_text or "")

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


def _parse_scout_output(text: str) -> tuple[str, list[dict[str, Any]]]:
    findings = _extract_artifact(text, "findings.md")
    rabbit_raw = _extract_artifact(text, "rabbit_holes.json")

    if not findings:
        findings = _extract_markdown_block(text) or text

    rabbit_holes: list[dict[str, Any]] = []
    if rabbit_raw:
        try:
            parsed = json.loads(rabbit_raw)
            if isinstance(parsed, list):
                rabbit_holes = parsed
        except json.JSONDecodeError:
            rabbit_holes = _extract_json_array(text)

    return findings.strip(), rabbit_holes


def _extract_artifact(text: str, filename: str) -> str | None:
    pattern = rf"--- artifact:.*?{re.escape(filename)}.*?---\n(.*?)(?=\n--- artifact:|\Z)"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    if filename in text:
        header = f"# Findings:" if filename == "findings.md" else None
        if header and header in text:
            start = text.index(header)
            end = text.find("--- artifact:", start)
            return text[start:end].strip() if end != -1 else text[start:].strip()

    return None


def _extract_markdown_block(text: str) -> str | None:
    if "# Findings:" in text:
        start = text.index("# Findings:")
        return text[start:].split("--- artifact:")[0].strip()
    return None


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    match = re.search(r"\[\s*\{.*?\}\s*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []
