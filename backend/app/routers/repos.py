from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.schemas import Repository, RepositorySummary
from app.routers.auth import get_github_client
from app.services.github import GitHubService
from app.services.repository_summary import build_template_summary

router = APIRouter(prefix="/repos", tags=["repos"])


@router.get("", response_model=list[Repository])
async def list_repositories(
    github: GitHubService = Depends(get_github_client),
) -> list[Repository]:
    return await github.list_repositories()


@router.get("/{owner}/{repo}", response_model=RepositorySummary)
async def get_repository_summary(
    owner: str,
    repo: str,
    github: GitHubService = Depends(get_github_client),
) -> RepositorySummary:
    repos = await github.list_repositories()
    match = next((r for r in repos if r.full_name == f"{owner}/{repo}"), None)
    if not match:
        raise HTTPException(status_code=404, detail="Repository not found or not accessible")
    return build_template_summary(match)
