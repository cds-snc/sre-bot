"""Isolation and builders for the webhooks capability's unit tests.

``_isolation`` (autouse) removes every WEBHOOKS_* variable, disables the .env file, installs
a base file with an empty [webhooks] table (so every limit is its default) and clears the
cached slice, so a test observes only the values it writes. ``kind_document`` returns a valid
sender-kind file as a mapping, which a test changes before ``build_kind`` validates and
compiles it.
"""

import copy
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from capabilities.webhooks.domain.interpret import Delivery
from capabilities.webhooks.domain.kinds import SenderKind
from capabilities.webhooks.domain.limits import WebhookLimits
from capabilities.webhooks.schemas import SenderKindFile, build_sender_kind
from capabilities.webhooks.settings import WebhooksSettings, get_webhooks_settings
from contracts.configuration import install_configuration_files
from server.configuration.loader import TomlConfigurationFiles

RECEIVED_AT = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
LANGUAGES = ("en-US", "fr-FR")

KIND_DOCUMENT: dict[str, Any] = {
    "kind": "webhooks/sender-kinds",
    "version": 1,
    "id": "budget-alert",
    "event": "alert",
    "match": {"all": [{"path": "$.source", "op": "equals", "value": "aws.budgets"}]},
    "fields": {
        "budget": {"path": "$.detail.name", "required": True},
        "spent": {"path": "$.detail.spent", "type": "number"},
        "console": {"path": "$.detail.url", "type": "url"},
        "message": {"path": "$.detail.message"},
    },
    "templates": {
        "title": {"en-US": "Budget {{ fields.budget }} exceeded", "fr-FR": "Budget {{ fields.budget }} dépassé"},
        "summary": {"en-US": "Spent {{ fields.spent }}", "fr-FR": "Dépensé {{ fields.spent }}"},
        "details": "{{ fields.message }}",
    },
    "links": [{"field": "console", "label": {"en-US": "Open the console", "fr-FR": "Ouvrir la console"}}],
    "alert": {"severity": "warning", "dedup_key": "budget:{{ fields.budget }}"},
}

PAYLOAD: dict[str, Any] = {
    "source": "aws.budgets",
    "detail": {
        "name": "sandbox",
        "spent": 120.5,
        "url": "https://console.aws.amazon.com/billing/home",
        "message": "Actual spend is over the budget.",
    },
}


@pytest.fixture(autouse=True)
def _isolation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.setitem(WebhooksSettings.model_config, "env_file", None)
    for key in tuple(os.environ):
        if key.startswith("WEBHOOKS_"):
            monkeypatch.delenv(key, raising=False)
    install_webhooks_files(tmp_path)
    get_webhooks_settings.cache_clear()
    yield
    get_webhooks_settings.cache_clear()


def install_webhooks_files(tmp_path: Path, base: str = "[webhooks]\n", environment: str = "") -> None:
    (tmp_path / "base.toml").write_text(base, encoding="utf-8")
    (tmp_path / "local.toml").write_text(environment, encoding="utf-8")
    install_configuration_files(
        TomlConfigurationFiles(environment="local", paths=(tmp_path / "base.toml", tmp_path / "local.toml"))
    )
    get_webhooks_settings.cache_clear()


def kind_document(**changes: Any) -> dict[str, Any]:
    """Return a copy of the valid budget-alert kind with top-level keys replaced (None removes one)."""
    document = copy.deepcopy(KIND_DOCUMENT)
    for key, value in changes.items():
        if value is None:
            document.pop(key, None)
        else:
            document[key] = value
    return document


def build_kind(document: dict[str, Any]) -> SenderKind:
    return build_sender_kind(SenderKindFile.model_validate(document))


def payload() -> dict[str, Any]:
    return copy.deepcopy(PAYLOAD)


def limits() -> WebhookLimits:
    return get_webhooks_settings().limits()


def delivery() -> Delivery:
    return Delivery(event_id="msg-1", instance_ref="inst-1", instance_name="Billing", received_at=RECEIVED_AT)
