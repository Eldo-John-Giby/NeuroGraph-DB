from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://neurograph:replace-me@localhost:5432/neurograph"
    jwt_secret_key: str = ""
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cookie_secure: bool = True
    artifact_root: Path = Path("../artifacts")
    verified_baseline_bundle_dir: Path | None = None
    verified_baseline_run_record: Path | None = None
    verified_multimodal_bundle_dir: Path | None = None
    verified_multimodal_run_record: Path | None = None
    neo4j_uri: str | None = None
    neo4j_username: str | None = None
    neo4j_password: str | None = None
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def configured_jwt_secret(self) -> bool:
        value = self.jwt_secret_key.strip()
        return len(value) >= 32 and not value.lower().startswith(("replace-", "change-me", "your-secret"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
