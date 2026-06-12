from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/api/auth/github/callback"
    frontend_url: str = "http://localhost:5173"
    session_secret: str = "dev-secret-change-in-production"
    data_dir: str = "data"
    cursor_api_key: str = ""
    cursor_model: str = "composer-2.5"
    cursor_rabbit_hole_max: int = 3
    cursor_rabbit_hole_min_confidence: float = 0.7
    cursor_run_timeout_sec: int = 600

    @property
    def github_configured(self) -> bool:
        return bool(self.github_client_id and self.github_client_secret)

    @property
    def cursor_configured(self) -> bool:
        return bool(self.cursor_api_key)

    @property
    def data_path(self) -> Path:
        """Absolute path to backend/data — independent of process cwd."""
        path = Path(self.data_dir)
        return path if path.is_absolute() else BACKEND_ROOT / path

    @property
    def seed_data_path(self) -> Path:
        """Committed demo artifacts shipped with the repo."""
        return BACKEND_ROOT / "seed_data"


settings = Settings()
