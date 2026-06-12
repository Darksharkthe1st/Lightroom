from typing import Any

import httpx

from app.config import settings
from app.models.schemas import GitHubUser, Repository

GITHUB_API = "https://api.github.com"
GITHUB_OAUTH_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_TOKEN = "https://github.com/login/oauth/access_token"


class GitHubService:
    def __init__(self, access_token: str) -> None:
        self.access_token = access_token
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @staticmethod
    def authorization_url(state: str) -> str:
        scopes = "repo read:user"
        return (
            f"{GITHUB_OAUTH_AUTHORIZE}"
            f"?client_id={settings.github_client_id}"
            f"&redirect_uri={settings.github_redirect_uri}"
            f"&scope={scopes.replace(' ', '%20')}"
            f"&state={state}"
        )

    @staticmethod
    async def exchange_code(code: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GITHUB_OAUTH_TOKEN,
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                    "redirect_uri": settings.github_redirect_uri,
                },
            )
            response.raise_for_status()
            data = response.json()
            token = data.get("access_token")
            if not token:
                raise ValueError(data.get("error_description", "No access token returned"))
            return token

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API}{path}",
                headers=self._headers,
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_user(self) -> GitHubUser:
        data = await self._get("/user")
        return GitHubUser(
            id=data["id"],
            login=data["login"],
            name=data.get("name"),
            avatar_url=data.get("avatar_url"),
        )

    async def list_repositories(self) -> list[Repository]:
        repos: list[Repository] = []
        page = 1
        while True:
            batch = await self._get(
                "/user/repos",
                params={
                    "per_page": 100,
                    "page": page,
                    "sort": "updated",
                    "affiliation": "owner,collaborator,organization_member",
                },
            )
            if not batch:
                break
            for item in batch:
                repos.append(
                    Repository(
                        id=item["id"],
                        name=item["name"],
                        full_name=item["full_name"],
                        description=item.get("description"),
                        html_url=item["html_url"],
                        private=item.get("private", False),
                        language=item.get("language"),
                        updated_at=item.get("updated_at"),
                        default_branch=item.get("default_branch") or "main",
                    )
                )
            if len(batch) < 100:
                break
            page += 1
        return repos

    async def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        return await self._get(f"/repos/{owner}/{repo}")

    async def get_repo_tree(self, owner: str, repo: str, branch: str) -> list[dict[str, Any]]:
        ref = await self._get(f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
        tree_sha = ref["object"]["sha"]
        tree = await self._get(
            f"/repos/{owner}/{repo}/git/trees/{tree_sha}",
            params={"recursive": "1"},
        )
        return tree.get("tree", [])

    async def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> str:
        import base64

        data = await self._get(f"/repos/{owner}/{repo}/contents/{path}", params={"ref": ref})
        if isinstance(data, list):
            return ""
        content = data.get("content", "")
        encoding = data.get("encoding", "base64")
        if encoding == "base64" and content:
            return base64.b64decode(content).decode("utf-8", errors="replace")
        return content or ""

    async def list_commits(
        self,
        owner: str,
        repo: str,
        author: str | None = None,
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"per_page": per_page}
        if author:
            params["author"] = author
        return await self._get(f"/repos/{owner}/{repo}/commits", params=params)
