"""Per-repository agent: browse code, write findings, mine commits, draft bullets."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.models.schemas import ResumeBullet
from app.services.github import GitHubService

KEY_FILES = (
    "README.md",
    "readme.md",
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "requirements.txt",
    "docker-compose.yml",
    "Dockerfile",
)

LANGUAGE_EXTENSIONS = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".rb": "Ruby",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".swift": "Swift",
    ".kt": "Kotlin",
}


class RepoAgent:
    def __init__(
        self,
        github: GitHubService,
        owner: str,
        repo: str,
        username: str,
        data_dir: Path,
    ) -> None:
        self.github = github
        self.owner = owner
        self.repo = repo
        self.full_name = f"{owner}/{repo}"
        self.username = username
        self.data_dir = data_dir
        self.analysis_dir = data_dir / "analysis" / owner / repo
        self.findings_path = self.analysis_dir / "findings.md"

    async def run(self) -> tuple[Path, list[ResumeBullet]]:
        self.analysis_dir.mkdir(parents=True, exist_ok=True)

        meta = await self.github.get_repository(self.owner, self.repo)
        branch = meta.get("default_branch") or "main"
        tree = await self.github.get_repo_tree(self.owner, self.repo, branch)

        findings = await self._browse_and_note(meta, tree, branch)
        self.findings_path.write_text(findings, encoding="utf-8")

        commits = await self.github.list_commits(
            self.owner, self.repo, author=self.username, per_page=50
        )
        bullets = self._build_resume_bullets(findings, commits, meta)
        return self.findings_path, bullets

    async def _browse_and_note(
        self,
        meta: dict[str, Any],
        tree: list[dict[str, Any]],
        branch: str,
    ) -> str:
        blobs = [item for item in tree if item.get("type") == "blob"]
        paths = [item["path"] for item in blobs]

        languages = self._detect_languages(paths)
        if meta.get("language"):
            languages.add(meta["language"])

        key_file_notes: list[str] = []
        for name in KEY_FILES:
            match = next((p for p in paths if p == name or p.endswith(f"/{name}")), None)
            if not match:
                continue
            try:
                content = await self.github.get_file_content(
                    self.owner, self.repo, match, branch
                )
                snippet = self._summarize_file(match, content)
                key_file_notes.append(f"- **{match}**: {snippet}")
            except Exception as exc:
                key_file_notes.append(f"- **{match}**: (could not read: {exc})")

        top_dirs = self._top_level_dirs(paths)
        description = meta.get("description") or "No description provided."

        lines = [
            f"# Findings: {self.full_name}",
            "",
            "## Overview",
            f"- **Description**: {description}",
            f"- **Default branch**: `{branch}`",
            f"- **Languages detected**: {', '.join(sorted(languages)) or 'unknown'}",
            f"- **File count (blobs)**: {len(blobs)}",
            "",
            "## Repository structure",
            f"- Top-level directories: {', '.join(top_dirs) if top_dirs else '(flat root)'}",
            "",
            "## Key files",
        ]
        lines.extend(key_file_notes or ["- No standard key files found."])
        lines.extend(["", "## Notes", self._purpose_note(meta, languages, paths)])
        return "\n".join(lines)

    def _detect_languages(self, paths: list[str]) -> set[str]:
        langs: set[str] = set()
        for path in paths:
            for ext, lang in LANGUAGE_EXTENSIONS.items():
                if path.endswith(ext):
                    langs.add(lang)
        return langs

    @staticmethod
    def _top_level_dirs(paths: list[str]) -> list[str]:
        dirs: set[str] = set()
        for path in paths:
            parts = path.split("/")
            if len(parts) > 1:
                dirs.add(parts[0])
        return sorted(dirs)[:12]

    @staticmethod
    def _summarize_file(path: str, content: str) -> str:
        if path.lower().endswith("readme.md"):
            first_para = ""
            for line in content.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    first_para = stripped[:200]
                    break
            return first_para or "README present."

        if path.endswith("package.json"):
            if '"name"' in content:
                m = re.search(r'"name"\s*:\s*"([^"]+)"', content)
                if m:
                    return f"npm package `{m.group(1)}`."
            return "Node.js project metadata."

        if path.endswith("pyproject.toml"):
            return "Python project (pyproject.toml)."

        if path.endswith("requirements.txt"):
            count = sum(1 for line in content.splitlines() if line.strip() and not line.startswith("#"))
            return f"{count} Python dependencies listed."

        return f"{len(content.splitlines())} lines."

    def _purpose_note(
        self,
        meta: dict[str, Any],
        languages: set[str],
        paths: list[str],
    ) -> str:
        hints: list[str] = []
        if any("test" in p.lower() for p in paths):
            hints.append("includes tests")
        if any(p.endswith(".github/workflows") or ".github/workflows/" in p for p in paths):
            hints.append("has CI workflows")
        if any("docker" in p.lower() for p in paths):
            hints.append("uses Docker")
        if meta.get("topics"):
            hints.append(f"topics: {', '.join(meta['topics'][:5])}")

        lang_str = ", ".join(sorted(languages)) if languages else "mixed stack"
        hint_str = "; ".join(hints) if hints else "standard application layout"
        return (
            f"This repository appears to be a **{lang_str}** project. "
            f"Based on structure: {hint_str}. "
            f"Findings will be refined as deeper analysis is added."
        )

    def _build_resume_bullets(
        self,
        findings: str,
        commits: list[dict[str, Any]],
        meta: dict[str, Any],
    ) -> list[ResumeBullet]:
        if not commits:
            return []

        languages = meta.get("language") or "software"
        desc = meta.get("description") or self.full_name
        commit_msgs = [c["commit"]["message"].splitlines()[0] for c in commits[:8]]
        themes = self._themes_from_commits(commit_msgs)

        bullets: list[ResumeBullet] = []

        bullets.append(
            ResumeBullet(
                text=(
                    f"Contributed to **{self.full_name}** ({languages}): "
                    f"{desc[:120]}{'...' if len(desc) > 120 else ''}"
                ),
                source_repo=self.full_name,
                evidence=commit_msgs[:3],
            )
        )

        if themes:
            bullets.append(
                ResumeBullet(
                    text=(
                        f"Delivered {len(commits)}+ commits on {self.full_name}, "
                        f"including work on {', '.join(themes[:3])}."
                    ),
                    source_repo=self.full_name,
                    evidence=commit_msgs[3:6] if len(commit_msgs) > 3 else commit_msgs,
                )
            )

        # Reference findings file in evidence for traceability
        bullets.append(
            ResumeBullet(
                text=(
                    f"Built and maintained features in a {languages} codebase "
                    f"({self._file_count_from_findings(findings)} tracked files)."
                ),
                source_repo=self.full_name,
                evidence=[f"See findings: {self.findings_path.name}"],
            )
        )

        return bullets

    @staticmethod
    def _themes_from_commits(messages: list[str]) -> list[str]:
        keywords = {
            "fix": "bug fixes",
            "feat": "new features",
            "add": "new capabilities",
            "refactor": "refactoring",
            "test": "testing",
            "docs": "documentation",
            "perf": "performance",
            "ui": "UI improvements",
            "api": "API work",
        }
        found: list[str] = []
        joined = " ".join(messages).lower()
        for key, label in keywords.items():
            if key in joined and label not in found:
                found.append(label)
        return found

    @staticmethod
    def _file_count_from_findings(findings: str) -> str:
        for line in findings.splitlines():
            if "File count" in line:
                m = re.search(r"(\d+)", line)
                if m:
                    return m.group(1)
        return "many"
