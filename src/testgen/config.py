"""Settings loaded from environment variables (TESTGEN_ prefix)."""
from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TESTGEN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    backend: str = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    openai_api_key: str = ""
    base_url: str = ""

    max_iterations: int = 3
    target_coverage: float = 0.80
    prompt_version: str = "v3"
    runner_timeout: int = 30

    db_path: str = ".testgen/results.db"
    cache_dir: str = ".testgen/cache"
    results_dir: str = "results"

    max_mutants: int = 30

    def ensure_dirs(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        Path(self.results_dir).mkdir(parents=True, exist_ok=True)


cfg = Settings()