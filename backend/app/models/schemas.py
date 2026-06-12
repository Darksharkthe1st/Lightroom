from enum import Enum

from pydantic import BaseModel, Field


class GitHubUser(BaseModel):
    id: int
    login: str
    name: str | None = None
    avatar_url: str | None = None


class Repository(BaseModel):
    id: int
    name: str
    full_name: str
    description: str | None = None
    html_url: str
    private: bool = False
    language: str | None = None
    updated_at: str | None = None
    default_branch: str = "main"


class AuthStatus(BaseModel):
    authenticated: bool
    user: GitHubUser | None = None


class RepositorySummary(BaseModel):
    """Template response for repository overview — expand with real analysis later."""

    full_name: str
    title: str
    summary: str
    highlights: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    status: str = "template"


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResumeBullet(BaseModel):
    text: str
    source_repo: str
    evidence: list[str] = Field(default_factory=list)


class ResumeResponse(BaseModel):
    username: str
    bullets: list[ResumeBullet]
    status: AnalysisStatus
    message: str | None = None
