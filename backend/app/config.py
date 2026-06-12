from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @property
    def github_configured(self) -> bool:
        return bool(self.github_client_id and self.github_client_secret)

    @property
    def cursor_configured(self) -> bool:
        return bool(self.cursor_api_key)


settings = Settings()
