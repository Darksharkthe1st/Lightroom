from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from cursor_sdk import AsyncAgent, AsyncClient, CloudAgentOptions, CloudRepository

from app.config import settings
from app.services.analysis.cursor_agents.errors import (
    raise_if_run_failed,
    raise_if_startup_failed,
)
from app.services.analysis.cursor_agents.repo_utils import (
    assert_repo_connected,
    normalize_repo_url,
    pick_connected_repo,
    resolve_default_branch,
)


@dataclass
class CloudRunMeta:
    agent_id: str
    run_id: str
    status: str
    duration_ms: int | None
    result_text: str | None
    repo_url: str
    branch: str
    artifacts: dict[str, str]
    artifact_paths: list[str]


async def run_cloud_prompt(
    *,
    prompt: str,
    repo_url: str,
    branch: str | None = None,
    github_token: str | None = None,
    run_meta_path: Path | None = None,
    skip_connection_check: bool = False,
) -> CloudRunMeta:
    """Run a one-shot cloud agent against a GitHub repo."""
    if not settings.cursor_configured:
        raise ValueError(
            "CURSOR_API_KEY is not set. Add it to backend/.env (see .env.example)."
        )

    repo_url = normalize_repo_url(repo_url)
    if not skip_connection_check:
        await assert_repo_connected(repo_url)

    if branch is None:
        branch = await resolve_default_branch(repo_url, github_token)

    cloud_opts = CloudAgentOptions(
        repos=[CloudRepository(url=repo_url, starting_ref=branch)],
        auto_create_pr=False,
    )

    agent_id: str | None = None
    run_id: str | None = None

    try:
        async with await AsyncClient.launch_bridge(workspace=str(Path.cwd())) as client:
            async with await client.agents.create(
                api_key=settings.cursor_api_key,
                model=settings.cursor_model,
                cloud=cloud_opts,
            ) as agent:
                agent_id = agent.agent_id
                run = await agent.send(prompt)
                run_id = run.id

                result = await run.wait()
                raise_if_run_failed(
                    result.status,
                    agent_id=agent_id,
                    run_id=run_id,
                    result_text=result.result,
                )

                artifacts, artifact_paths = await _download_artifacts(agent)

                meta = CloudRunMeta(
                    agent_id=agent_id,
                    run_id=run_id,
                    status=result.status,
                    duration_ms=result.duration_ms,
                    result_text=result.result,
                    repo_url=repo_url,
                    branch=branch,
                    artifacts=artifacts,
                    artifact_paths=artifact_paths,
                )

                if run_meta_path:
                    run_meta_path.parent.mkdir(parents=True, exist_ok=True)
                    run_meta_path.write_text(
                        json.dumps(
                            {
                                "agent_id": meta.agent_id,
                                "run_id": meta.run_id,
                                "status": meta.status,
                                "duration_ms": meta.duration_ms,
                                "repo_url": meta.repo_url,
                                "branch": meta.branch,
                                "artifact_paths": meta.artifact_paths,
                            },
                            indent=2,
                        ),
                        encoding="utf-8",
                    )

                return meta

    except Exception as exc:
        raise_if_startup_failed(exc)
        raise


async def _download_artifacts(agent: AsyncAgent) -> tuple[dict[str, str], list[str]]:
    """Download all cloud agent artifacts keyed by path."""
    downloaded: dict[str, str] = {}
    paths: list[str] = []
    try:
        listed = await agent.list_artifacts()
    except Exception:
        return downloaded, paths

    for artifact in listed:
        paths.append(artifact.path)
        try:
            raw = await agent.download_artifact(artifact.path)
            downloaded[artifact.path] = raw.decode("utf-8", errors="replace")
        except Exception:
            continue
    return downloaded, paths


async def smoke_test_connected_repo(
    *,
    prefer_full_name: str = "Darksharkthe1st/CodeRunner",
    github_token: str | None = None,
) -> CloudRunMeta:
    """SDK connectivity check using a repo connected to the Cursor account."""
    repo_url = await pick_connected_repo(prefer_full_name)
    branch = await resolve_default_branch(repo_url, github_token)
    return await run_cloud_prompt(
        prompt="In one sentence, what is this repository? Do not modify any files.",
        repo_url=repo_url,
        branch=branch,
        github_token=github_token,
        skip_connection_check=True,
    )
