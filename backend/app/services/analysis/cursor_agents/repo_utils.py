"""GitHub + Cursor repo helpers for cloud agent runs."""

from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from cursor_sdk import AsyncClient

from app.config import settings

_GITHUB_REPO_RE = re.compile(
    r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.\s]+?)(?:\.git)?/?$"
)


def parse_github_repo_url(repo_url: str) -> tuple[str, str]:
    url = normalize_repo_url(repo_url)
    match = _GITHUB_REPO_RE.search(url)
    if not match:
        raise ValueError(f"Not a GitHub repository URL: {repo_url}")
    return match.group("owner"), match.group("repo")


def normalize_repo_url(repo_url: str) -> str:
    parsed = urlparse(repo_url.strip())
    if parsed.scheme:
        path = parsed.path.rstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        return f"https://github.com{path}"
    return repo_url.rstrip("/").removesuffix(".git")


async def resolve_default_branch(repo_url: str, github_token: str | None = None) -> str:
    owner, repo = parse_github_repo_url(repo_url)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers=headers,
        )
        response.raise_for_status()
        branch = response.json().get("default_branch")
        if not branch:
            raise ValueError(f"Could not resolve default branch for {owner}/{repo}")
        return branch


async def list_connected_repo_urls() -> list[str]:
    """Repos connected to the Cursor account (required for cloud agents)."""
    if not settings.cursor_configured:
        return []

    async with await AsyncClient.launch_bridge(workspace=".") as client:
        repos = await client.repositories.list(api_key=settings.cursor_api_key)
        return [normalize_repo_url(repo.url) for repo in repos]


async def pick_connected_repo(
    prefer_full_name: str | None = None,
) -> str:
    connected = await list_connected_repo_urls()
    if not connected:
        raise ValueError(
            "No GitHub repositories are connected to your Cursor account.\n"
            "Connect GitHub in the Cursor Dashboard (Integrations) and grant access "
            "to the repos you want to analyze."
        )

    if prefer_full_name:
        needle = prefer_full_name.lower()
        for url in connected:
            if needle in url.lower():
                return url

    return connected[0]


async def assert_repo_connected(repo_url: str) -> None:
    connected = {normalize_repo_url(url) for url in await list_connected_repo_urls()}
    normalized = normalize_repo_url(repo_url)
    if normalized not in connected:
        preview = ", ".join(sorted(connected)[:8])
        extra = f" …and {len(connected) - 8} more" if len(connected) > 8 else ""
        raise ValueError(
            f"Repository {normalized} is not connected to your Cursor account.\n"
            "Cloud agents can only run against repos linked in Cursor Dashboard → Integrations.\n"
            f"Connected repos: {preview}{extra}"
        )
