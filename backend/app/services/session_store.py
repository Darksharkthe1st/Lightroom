"""Simple in-memory session store for MVP. Swap for Redis/DB later."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Session:
    token: str
    user: dict[str, Any]
    oauth_state: str | None = None


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._state_to_session: dict[str, str] = {}

    def create(self, session_id: str, token: str, user: dict[str, Any]) -> Session:
        session = Session(token=token, user=user)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session and session.oauth_state:
            self._state_to_session.pop(session.oauth_state, None)

    def set_oauth_state(self, session_id: str, state: str) -> None:
        self._state_to_session[state] = session_id
        session = self._sessions.get(session_id)
        if session:
            session.oauth_state = state

    def pop_session_for_state(self, state: str) -> tuple[str, Session] | None:
        session_id = self._state_to_session.pop(state, None)
        if not session_id:
            return None
        session = self._sessions.get(session_id)
        if not session:
            return None
        session.oauth_state = None
        return session_id, session


session_store = SessionStore()
