"""EN/FR parity of the webhooks capability's catalogue (decisions/i18n.md parity gate).

Reads the YAML files the plugin registers; the assertions pin identical keys and that the
fallback header the core asks for exists in both.
"""

from pathlib import Path

import pytest
import yaml

import capabilities.webhooks as webhooks_pkg
from capabilities.webhooks.service import FALLBACK_HEADER_KEY

pytestmark = pytest.mark.unit

LOCALES = Path(webhooks_pkg.__file__).parent / "locales"


def _keys(language: str) -> set[str]:
    data = yaml.safe_load((LOCALES / f"webhooks.{language}.yml").read_text(encoding="utf-8"))
    return {f"webhooks.{key}" for key in data["webhooks"]}


def test_en_and_fr_catalogues_have_identical_keys() -> None:
    assert _keys("en-US") == _keys("fr-FR")


def test_the_fallback_header_is_in_the_catalogue() -> None:
    assert FALLBACK_HEADER_KEY in _keys("en-US")
