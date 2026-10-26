"""Fail-closed configuration and client-address handling."""

import pytest
from pydantic import ValidationError

from app.core.config import REPO_ROOT, Settings
from app.core.net import client_ip

GOOD = {"app_env": "production", "secret_key": "x" * 40,
        "database_url": "postgresql+psycopg://app:s3cret@localhost/db"}


class FakeRequest:
    def __init__(self, peer, forwarded=None):
        self.client = type("C", (), {"host": peer})() if peer else None
        self.headers = {"x-forwarded-for": forwarded} if forwarded else {}


class TestConfiguration:
    def test_the_default_environment_is_production(self, monkeypatch):
        monkeypatch.delenv("APP_ENV", raising=False)
        assert Settings(_env_file=None, secret_key=GOOD["secret_key"], database_url=GOOD["database_url"]).app_env == "production"

    @pytest.mark.parametrize("overrides", [
        {"secret_key": "CHANGE_ME_LONG_RANDOM_VALUE"}, {"secret_key": "short"},
        {"database_url": "postgresql+psycopg://resume_app:CHANGE_ME@localhost/db"},
    ])
    @pytest.mark.security
    def test_production_refuses_placeholder_or_weak_secrets(self, overrides):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **{**GOOD, **overrides})

    def test_development_accepts_defaults(self):
        assert Settings(_env_file=None, app_env="development").app_env == "development"

    def test_relative_paths_resolve_against_the_repository_not_the_working_directory(self):
        settings = Settings(_env_file=None, storage_dir="data/files", model_dir="weights", **GOOD)
        assert settings.storage_dir == REPO_ROOT / "data/files" and settings.model_dir == REPO_ROOT / "weights"

    def test_malformed_proxy_setting_fails_at_startup(self):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, trusted_proxies="not-a-network", **GOOD)


@pytest.mark.security
class TestClientAddress:
    SETTINGS = Settings(_env_file=None, trusted_proxies="10.0.0.0/8", **GOOD)

    def test_direct_clients_cannot_spoof_forwarding_headers(self):
        assert client_ip(FakeRequest("203.0.113.9", "1.2.3.4"), self.SETTINGS) == "203.0.113.9"

    def test_behind_a_trusted_proxy_the_last_untrusted_hop_is_used(self):
        request = FakeRequest("10.0.0.5", "6.6.6.6, 198.51.100.7, 10.0.0.9")
        assert client_ip(request, self.SETTINGS) == "198.51.100.7"

    def test_a_forged_leading_entry_does_not_win(self):
        assert client_ip(FakeRequest("10.0.0.5", "6.6.6.6, 198.51.100.7"), self.SETTINGS) == "198.51.100.7"

    def test_a_trusted_proxy_without_a_header_falls_back_to_the_peer(self):
        assert client_ip(FakeRequest("10.0.0.5"), self.SETTINGS) == "10.0.0.5"

    def test_missing_peer_is_unknown(self):
        assert client_ip(FakeRequest(None), self.SETTINGS) == "unknown"
