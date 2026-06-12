from pathlib import Path

from app.models.schemas import Repository, RepositorySummary
from app.services.analysis.artifact_loader import analysis_dir, section_excerpt


def build_repository_summary(repo: Repository, data_dir: Path) -> RepositorySummary:
    owner, name = repo.full_name.split("/", 1)
    findings_path = analysis_dir(data_dir, owner, name) / "findings.md"

    if findings_path.exists():
        findings = findings_path.read_text(encoding="utf-8")
        overview = section_excerpt(findings, "## Overview", 500)
        stack_match = findings.find("## Stack")
        arch_match = findings.find("## Architecture")
        tech_stack: list[str] = []
        if stack_match != -1:
            stack_block = findings[stack_match : findings.find("\n## ", stack_match + 1)]
            tech_stack = [
                line.lstrip("- ").split("—")[0].strip().strip("*")
                for line in stack_block.splitlines()
                if line.strip().startswith("-")
            ][:8]

        signals_dir = analysis_dir(data_dir, owner, name) / "signals"
        signal_count = len(list(signals_dir.glob("*.md"))) if signals_dir.exists() else 0
        status = "analyzed" if signal_count else "scouted"

        return RepositorySummary(
            full_name=repo.full_name,
            title=f"{repo.name} — AI Analysis",
            summary=overview or repo.description or "Analysis available.",
            highlights=[
                f"Pipeline: scout complete, {signal_count} deep dive(s)",
                f"Visibility: {'private' if repo.private else 'public'}",
                f"Default branch: {repo.default_branch}",
            ],
            tech_stack=tech_stack or ([repo.language] if repo.language else []),
            status=status,
        )

    lang = repo.language or "Unknown"
    desc = repo.description or "No description available."
    return RepositorySummary(
        full_name=repo.full_name,
        title=f"{repo.name} — Repository Overview",
        summary=(
            f"{desc} Primary language: {lang}. "
            f"Run analysis to generate resume bullets from your commits."
        ),
        highlights=[
            f"Last updated: {repo.updated_at or 'unknown'}",
            f"Visibility: {'private' if repo.private else 'public'}",
            f"Default branch: {repo.default_branch}",
        ],
        tech_stack=[lang] if repo.language else [],
        status="template",
    )
