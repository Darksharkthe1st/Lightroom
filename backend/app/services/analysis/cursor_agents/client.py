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

                meta = CloudRunMeta(
                    agent_id=agent_id,
                    run_id=run_id,
                    status=result.status,
                    duration_ms=result.duration_ms,
                    result_text=result.result,
                    repo_url=repo_url,
                    branch=branch,
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
                            },
                            indent=2,
                        ),
                        encoding="utf-8",
                    )

                meta.result_text = await _collect_lightroom_artifacts(agent, meta.result_text)
                return meta

    except Exception as exc:
        raise_if_startup_failed(exc)
        raise


async def _collect_lightroom_artifacts(agent: AsyncAgent, fallback_text: str | None) -> str | None:
    """Download .lightroom/* artifacts if the agent produced them."""
    try:
        artifacts = await agent.list_artifacts()
    except Exception:
        return fallback_text

    paths = {a.path for a in artifacts}
    lightroom = [p for p in paths if p.startswith(".lightroom/") or p.endswith("findings.md")]
    if not lightroom:
        return fallback_text

    parts = [fallback_text or ""]
    for path in sorted(lightroom):
        try:
            content = await agent.download_artifact(path)
            parts.append(f"\n--- artifact: {path} ---\n{content.decode('utf-8', errors='replace')}")
        except Exception:
            continue
    return "\n".join(parts)


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
