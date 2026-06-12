from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import settings
from app.models.schemas import RepoAnalysis, ResumeResponse
from app.routers.auth import _require_session, get_github_client
from app.services.analysis.artifact_loader import load_repo_analysis
from app.services.analysis.orchestrator import AnalysisOrchestrator
from app.services.github import GitHubService

router = APIRouter(prefix="/analysis", tags=["analysis"])

_orchestrator = AnalysisOrchestrator(settings.data_path)


@router.get("/repo/{owner}/{repo}", response_model=RepoAnalysis)
async def get_repo_analysis(owner: str, repo: str, request: Request) -> RepoAnalysis:
    _require_session(request)
    return load_repo_analysis(settings.data_path, owner, repo)


@router.get("/resume", response_model=ResumeResponse)
async def get_resume_status(request: Request) -> ResumeResponse:
    _, session = _require_session(request)
    username = session.user["login"]
    return _orchestrator.get_status(username)


@router.post("/resume", response_model=ResumeResponse)
async def run_resume_analysis(
    request: Request,
    github: GitHubService = Depends(get_github_client),
) -> ResumeResponse:
    _, session = _require_session(request)
    username = session.user["login"]
    repos = await github.list_repositories()
    if not repos:
        raise HTTPException(status_code=400, detail="No repositories to analyze")
    full_names = [r.full_name for r in repos]
    return await _orchestrator.analyze_repositories(github, username, full_names)


@router.post("/resume/{owner}/{repo}", response_model=ResumeResponse)
async def run_single_repo_analysis(
    owner: str,
    repo: str,
    request: Request,
    github: GitHubService = Depends(get_github_client),
) -> ResumeResponse:
    _, session = _require_session(request)
    username = session.user["login"]
    return await _orchestrator.analyze_single_repository(github, username, owner, repo)
