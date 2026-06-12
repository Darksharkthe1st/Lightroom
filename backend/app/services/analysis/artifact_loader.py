"""Load scout + rabbit-hole artifacts from disk for API and demo."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.config import settings
from app.models.schemas import AnalysisStatus, ResumeBullet, ResumeResponse, SignalNote, RepoAnalysis

_BULLET_SECTION = "## Resume bullet candidates"
_OVERVIEW_SECTION = "## Overview"


def _analysis_roots() -> list[Path]:
    """Live analysis dir first, then committed seed data for demos."""
    roots = [settings.data_path / "analysis"]
    seed = settings.seed_data_path / "analysis"
    if seed != roots[0] and seed.exists():
        roots.append(seed)
    return roots


def analysis_dir(data_dir: Path, owner: str, repo: str) -> Path:
    """Resolve repo analysis dir — prefers live data, falls back to seed_data."""
    for root in _analysis_roots():
        candidate = root / owner / repo
        if (candidate / "findings.md").exists():
            return candidate
    return data_dir / "analysis" / owner / repo


def has_analysis(data_dir: Path, owner: str, repo: str) -> bool:
    base = analysis_dir(data_dir, owner, repo)
    return (base / "findings.md").exists()


def load_bullets(data_dir: Path, owner: str, repo: str) -> list[ResumeBullet]:
    base = analysis_dir(data_dir, owner, repo)
    full_name = f"{owner}/{repo}"
    bullets: list[ResumeBullet] = []

    bullets_path = base / "bullets.json"
    if bullets_path.exists():
        try:
            raw = json.loads(bullets_path.read_text(encoding="utf-8"))
            items = raw if isinstance(raw, list) else raw.get("bullets", [])
            for item in items:
                if isinstance(item, dict) and item.get("text"):
                    bullets.append(
                        ResumeBullet(
                            text=item["text"],
                            source_repo=item.get("source_repo", full_name),
                            evidence=item.get("evidence", []),
                            signal_id=item.get("signal_id"),
                        )
                    )
            if bullets:
                return bullets
        except (json.JSONDecodeError, TypeError):
            pass

    signals_dir = base / "signals"
    if not signals_dir.exists():
        return bullets

    for path in sorted(signals_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        signal_id = path.stem
        display = _signal_title(content) or signal_id.replace("_", " ").title()
        for text in _extract_bullet_texts(content):
            bullets.append(
                ResumeBullet(
                    text=text,
                    source_repo=full_name,
                    evidence=[f"Deep dive: {display}"],
                    signal_id=signal_id,
                )
            )
    return bullets


def load_repo_analysis(data_dir: Path, owner: str, repo: str) -> RepoAnalysis:
    base = analysis_dir(data_dir, owner, repo)
    full_name = f"{owner}/{repo}"

    triage_done = (base / "triage.json").exists()
    scout_done = (base / "findings.md").exists()
    rabbit_plan = 0
    if (base / "rabbit_holes.json").exists():
        try:
            plan = json.loads((base / "rabbit_holes.json").read_text(encoding="utf-8"))
            rabbit_plan = len(plan) if isinstance(plan, list) else 0
        except json.JSONDecodeError:
            rabbit_plan = 0

    signals_dir = base / "signals"
    signal_files = sorted(signals_dir.glob("*.md")) if signals_dir.exists() else []
    signals: list[SignalNote] = []
    for path in signal_files:
        content = path.read_text(encoding="utf-8")
        signals.append(
            SignalNote(
                signal_id=path.stem,
                display_name=_signal_title(content) or path.stem,
                summary=section_excerpt(content, "## Summary", 280),
            )
        )

    findings_excerpt = ""
    if scout_done:
        findings = (base / "findings.md").read_text(encoding="utf-8")
        findings_excerpt = section_excerpt(findings, _OVERVIEW_SECTION, 600)

    if signal_files:
        status = "analyzed"
    elif scout_done:
        status = "scouted"
    elif triage_done:
        status = "triaged"
    else:
        status = "pending"

    bullets = load_bullets(data_dir, owner, repo)

    return RepoAnalysis(
        full_name=full_name,
        status=status,
        triage_complete=triage_done,
        scout_complete=scout_done,
        rabbit_holes_planned=rabbit_plan,
        rabbit_holes_complete=len(signal_files),
        findings_excerpt=findings_excerpt,
        signals=signals,
        bullets=bullets,
    )


def resume_response_from_artifacts(
    data_dir: Path,
    owner: str,
    repo: str,
    username: str,
) -> ResumeResponse | None:
    analysis = load_repo_analysis(data_dir, owner, repo)
    if analysis.status == "pending":
        return None

    bullets = analysis.bullets
    if not bullets and analysis.scout_complete:
        bullets = [
            ResumeBullet(
                text=(
                    f"Contributed to {analysis.full_name} — "
                    f"scout analysis complete ({analysis.rabbit_holes_planned} areas identified)."
                ),
                source_repo=analysis.full_name,
                evidence=["findings.md"],
            )
        ]

    message = (
        f"Loaded analysis for {owner}/{repo}: "
        f"scout ✓, {analysis.rabbit_holes_complete}/{analysis.rabbit_holes_planned} deep dives."
    )
    return ResumeResponse(
        username=username,
        bullets=bullets,
        status=AnalysisStatus.COMPLETED,
        message=message,
    )


def _signal_title(content: str) -> str | None:
    match = re.search(r"^#\s*Signal:\s*(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else None


def section_excerpt(content: str, header: str, max_chars: int) -> str:
    if header not in content:
        return content[:max_chars].strip()
    start = content.index(header) + len(header)
    rest = content[start:].lstrip("\n")
    end = rest.find("\n## ")
    body = rest[:end] if end != -1 else rest
    body = " ".join(line.strip() for line in body.splitlines() if line.strip())
    return body[:max_chars] + ("…" if len(body) > max_chars else "")


def _extract_bullet_texts(content: str) -> list[str]:
    if _BULLET_SECTION not in content:
        return []
    section = content.split(_BULLET_SECTION, 1)[1]
    section = section.split("\n## ", 1)[0]
    texts: list[str] = []
    for line in section.splitlines():
        line = line.strip()
        match = re.match(r"^\d+\.\s+(.+)$", line)
        if match:
            texts.append(match.group(1).strip())
    return texts
