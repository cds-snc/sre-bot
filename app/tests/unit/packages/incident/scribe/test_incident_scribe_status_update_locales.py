"""EN/FR parity of the incident scribe status-update locale catalogue."""

from pathlib import Path

import pytest
import yaml

import packages.incident.scribe as scribe_pkg

pytestmark = pytest.mark.unit

_LOCALES_DIR = Path(scribe_pkg.__file__).parent / "locales"


def _keys(filename: str) -> set[str]:
    data = yaml.safe_load((_LOCALES_DIR / filename).read_text(encoding="utf-8"))
    return set(data["incident_status_update"].keys())


def test_en_fr_locales_have_identical_keys():
    """EN and FR locale files for incident status updates have matching keys."""
    en_keys = _keys("incident_status_update.en-US.yml")
    fr_keys = _keys("incident_status_update.fr-FR.yml")

    assert en_keys == fr_keys, f"Locale key mismatch: {en_keys ^ fr_keys}"


def test_locales_are_non_empty():
    """Both EN and FR locale files contain keys."""
    assert _keys("incident_status_update.en-US.yml")
    assert _keys("incident_status_update.fr-FR.yml")
