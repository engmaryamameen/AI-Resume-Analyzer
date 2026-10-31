from functools import lru_cache
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PIPELINE_VERSION = "pipeline-2"
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    # Fails closed: anything other than an explicit development/test setting gets production rules.
    app_env: Literal["development", "production", "test"] = "production"
    cors_allowed_origins: str = "http://localhost:3000"
    trusted_proxies: str = ""

    database_url: str = "postgresql+psycopg://resume_app:CHANGE_ME@localhost:5432/resume_intel"
    secret_key: str = "CHANGE_ME_LONG_RANDOM_VALUE"  # noqa: S105 - rejected in production
    storage_dir: Path = REPO_ROOT / "backend" / "storage"
    model_dir: Path = REPO_ROOT / "models"

    max_upload_bytes: int = 5 * 1024 * 1024
    max_pdf_pages: int = 8
    max_jd_chars: int = 20_000
    parser_timeout_seconds: int = 20
    parser_memory_mb: int = 512
    session_ttl_hours: int = 72
    retention_days: int = 90

    job_max_attempts: int = Field(default=3, ge=1)
    job_lock_seconds: int = 120

    ml_enabled: bool = True
    ml_device: Literal["cpu", "cuda"] = "cpu"
    ml_threads: int = Field(default=4, ge=1)
    ml_batch_size: int = Field(default=16, ge=1)
    ml_max_seconds: int = Field(default=120, ge=5)

    metrics_token: str = ""

    rate_limit_per_minute: int = 120
    rate_limit_auth_per_minute: int = 10
    rate_limit_upload_per_minute: int = 10
    rate_limit_demo_per_minute: int = 20

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def trusted_proxy_networks(self) -> list[IPv4Network | IPv6Network]:
        return [
            ip_network(p.strip(), strict=False)
            for p in self.trusted_proxies.split(",")
            if p.strip()
        ]

    def is_trusted_proxy(self, address: str) -> bool:
        try:
            ip = ip_address(address)
        except ValueError:
            return False
        return any(ip in net for net in self.trusted_proxy_networks)

    @model_validator(mode="after")
    def _resolve_paths_and_refuse_unsafe_production(self) -> "Settings":
        self.storage_dir = (
            self.storage_dir if self.storage_dir.is_absolute() else REPO_ROOT / self.storage_dir
        )
        self.model_dir = (
            self.model_dir if self.model_dir.is_absolute() else REPO_ROOT / self.model_dir
        )
        if self.is_production:
            if self.secret_key.startswith("CHANGE_ME") or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must be a random value of at least 32 characters")
            if "CHANGE_ME" in self.database_url:
                raise ValueError("DATABASE_URL still contains a placeholder credential")
        list(
            self.trusted_proxy_networks
        )  # a malformed entry fails at startup, not on the first request
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
