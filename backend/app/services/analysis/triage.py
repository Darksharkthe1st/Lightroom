"""Phase 0 triage — heuristic signal detection (no SDK). Full taxonomy in Milestone 2."""

from __future__ import annotations

import re
from typing import Any

from app.services.github import GitHubService

KEY_FILES = (
    "README.md",
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "requirements.txt",
    "docker-compose.yml",
    "Dockerfile",
    "pom.xml",
    "build.gradle",
)

SIGNAL_PATTERNS: dict[str, list[str]] = {
    "react": ["cr-frontend/", "react", "jsx", "tsx", "package.json"],
    "spring_boot": ["spring", "pom.xml", "build.gradle", "src/main/java"],
    "docker": ["docker", "Dockerfile", "docker-compose"],
    "ci_cd": [".github/workflows"],
    "testing": ["test", "spec", "junit", "pytest", "jest"],
    "kubernetes": ["k8s", "kubernetes", "helm", "deployment.yaml"],
    "postgres": ["postgres", "postgresql", "migration"],
    "redis": ["redis"],
    "typescript": [".ts", ".tsx", "tsconfig"],
    "python": [".py", "pyproject.toml", "requirements.txt"],
    "java": [".java", "pom.xml", "mvnw"],
    "ai_llm": ["langchain", "openai", "llm", "agent"],
    "api_design": ["controller", "router", "openapi", "swagger", "/api"],
    "observability": ["prometheus", "grafana", "metrics", "opentelemetry"],
}


async def build_triage(
    github: GitHubService,
    owner: str,
    repo: str,
    username: str,
) -> dict[str, Any]:
    meta = await github.get_repository(owner, repo)
    branch = meta.get("default_branch") or "main"
    tree = await github.get_repo_tree(owner, repo, branch)
    blobs = [item for item in tree if item.get("type") == "blob"]
    paths = [item["path"] for item in blobs]

    commits = await github.list_commits_all(owner, repo, author=username)
    signals = _detect_signals(paths, meta)

    commit_count = len(commits)
    strong_signals = [s for s in signals if s["confidence"] >= 0.5]
    worth_deep = commit_count > 0 or len(strong_signals) >= 2

    return {
        "repo": f"{owner}/{repo}",
        "username": username,
        "branch": branch,
        "description": meta.get("description"),
        "language": meta.get("language"),
        "commit_count": commit_count,
        "file_count": len(blobs),
        "top_level_dirs": _top_level_dirs(paths),
        "signals": signals,
        "worth_deep_analysis": worth_deep,
    }


def _detect_signals(paths: list[str], meta: dict[str, Any]) -> list[dict[str, Any]]:
    joined = "\n".join(paths).lower()
    detected: list[dict[str, Any]] = []

    for signal_id, patterns in SIGNAL_PATTERNS.items():
        triggers = [p for p in patterns if p.lower() in joined or any(path.endswith(p) for path in paths)]
        if not triggers and signal_id == "java" and meta.get("language") == "Java":
            triggers = ["github language: Java"]
        if triggers:
            confidence = min(0.95, 0.45 + 0.1 * len(triggers))
            detected.append(
                {
                    "id": signal_id,
                    "confidence": round(confidence, 2),
                    "triggers": triggers[:5],
                }
            )

    detected.sort(key=lambda s: s["confidence"], reverse=True)
    return detected


def _top_level_dirs(paths: list[str]) -> list[str]:
    dirs: set[str] = set()
    for path in paths:
        parts = path.split("/")
        if len(parts) > 1:
            dirs.add(parts[0])
    return sorted(dirs)[:12]
