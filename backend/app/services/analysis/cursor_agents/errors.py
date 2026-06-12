from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AgentRunError(Exception):
    """Raised when a Cursor agent run fails."""

    message: str
    agent_id: str | None = None
    run_id: str | None = None
    status: str | None = None
    retryable: bool = False
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        parts = [self.message]
        if self.agent_id:
            parts.append(f"agent_id={self.agent_id}")
        if self.run_id:
            parts.append(f"run_id={self.run_id}")
        return " | ".join(parts)


def raise_if_startup_failed(exc: Exception) -> None:
    from cursor_sdk import CursorAgentError

    if isinstance(exc, CursorAgentError):
        raise AgentRunError(
            message=str(exc),
            retryable=getattr(exc, "is_retryable", False),
        ) from exc
    raise exc


def raise_if_run_failed(
    status: str,
    *,
    agent_id: str | None,
    run_id: str | None,
    result_text: str | None = None,
) -> None:
    if status == "finished":
        return
    raise AgentRunError(
        message=result_text or f"Agent run ended with status: {status}",
        agent_id=agent_id,
        run_id=run_id,
        status=status,
    )
