import secrets
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from app.config import settings
from app.models.schemas import AuthStatus, GitHubUser
from app.services.github import GitHubService
from app.services.session_store import session_store

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_COOKIE = "lightroom_session"


def _get_session_id(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE)


def _require_session(request: Request):
    session_id = _get_session_id(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired")
    return session_id, session


@router.get("/status", response_model=AuthStatus)
async def auth_status(request: Request) -> AuthStatus:
    session_id = _get_session_id(request)
    if not session_id:
        return AuthStatus(authenticated=False)
    session = session_store.get(session_id)
    if not session:
        return AuthStatus(authenticated=False)
    user = session.user
    return AuthStatus(
        authenticated=True,
        user=GitHubUser(
            id=user["id"],
            login=user["login"],
            name=user.get("name"),
            avatar_url=user.get("avatar_url"),
        ),
    )


@router.get("/github/login")
async def github_login(response: Response) -> RedirectResponse:
    if not settings.github_configured:
        raise HTTPException(
            status_code=503,
            detail="GitHub OAuth not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET.",
        )

    session_id = str(uuid.uuid4())
    state = secrets.token_urlsafe(32)
    session_store.create(session_id, token="", user={})
    session_store.set_oauth_state(session_id, state)

    redirect = RedirectResponse(GitHubService.authorization_url(state))
    redirect.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return redirect


@router.get("/github/callback")
async def github_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error:
        return RedirectResponse(f"{settings.frontend_url}?auth_error={error}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    result = session_store.pop_session_for_state(state)
    if not result:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    session_id, session = result

    try:
        token = await GitHubService.exchange_code(code)
        github = GitHubService(token)
        user = await github.get_user()
        session_store.create(
            session_id,
            token=token,
            user=user.model_dump(),
        )
    except Exception as exc:
        return RedirectResponse(f"{settings.frontend_url}?auth_error={exc}")

    redirect = RedirectResponse(f"{settings.frontend_url}?auth=success")
    redirect.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return redirect


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict[str, str]:
    session_id = _get_session_id(request)
    if session_id:
        session_store.delete(session_id)
    response.delete_cookie(SESSION_COOKIE)
    return {"status": "logged_out"}


def get_github_client(request: Request) -> GitHubService:
    _, session = _require_session(request)
    return GitHubService(session.token)
