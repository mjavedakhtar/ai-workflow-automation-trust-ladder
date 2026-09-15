from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    google_api_key: str = ""
    llm_mode: Literal["auto", "gemini", "mock"] = "auto"
    gemini_model: str = "gemini-2.0-flash"
    api_key: str = "dev-change-me"
    ledger_signing_key: str = "dev-ledger-change-me"
    database_url: str = f"sqlite:///{ROOT / 'backend' / 'data' / 'runtime' / 'trustladder.db'}"
    checkpoint_path: str = str(ROOT / "backend" / "data" / "runtime" / "checkpoints.sqlite")
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def use_gemini(self) -> bool:
        if self.llm_mode == "mock":
            return False
        if self.llm_mode == "gemini":
            return bool(self.google_api_key)
        return bool(self.google_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
