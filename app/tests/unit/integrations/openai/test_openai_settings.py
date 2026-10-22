"""Tests for OpenAI vendor settings resolution and defaults."""

from __future__ import annotations

import pytest

from integrations.openai.settings import OpenAISettings, get_openai_settings

pytestmark = pytest.mark.unit


class TestOpenAISettings:
    def test_reads_api_key_and_applies_defaults(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")

        settings = OpenAISettings()

        assert settings.api_key.get_secret_value() == "sk-secret"
        assert settings.model == "gpt-5.6-luna"
        assert settings.max_output_tokens == 3000
        assert settings.temperature == -1.0
        assert settings.timeout_seconds == 180.0
        assert settings.base_url == "https://ai.cdssandbox.xyz"

    def test_overrides_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-5.4-mini")
        monkeypatch.setenv("OPENAI_MAX_OUTPUT_TOKENS", "1200")

        settings = OpenAISettings()

        assert settings.model == "gpt-5.4-mini"
        assert settings.max_output_tokens == 1200

    def test_api_key_not_exposed_in_repr(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")

        settings = OpenAISettings()

        assert "sk-secret" not in repr(settings)

    def test_get_openai_settings_is_cached(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")

        assert get_openai_settings() is get_openai_settings()
