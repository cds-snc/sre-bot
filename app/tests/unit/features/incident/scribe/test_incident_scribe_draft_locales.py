"""EN/FR parity of the incident scribe draft locale catalogue."""

from pathlib import Path

import pytest
import yaml

import features.incident.scribe as scribe_pkg

pytestmark = pytest.mark.unit

_LOCALES_DIR = Path(scribe_pkg.__file__).parent / "locales"


def _keys(filename: str) -> set[str]:
    data = yaml.safe_load((_LOCALES_DIR / filename).read_text(encoding="utf-8"))
    return set(data["incident_draft"].keys())


def test_en_fr_locales_have_identical_keys():
    en_keys = _keys("incident_draft.en-US.yml")
    fr_keys = _keys("incident_draft.fr-FR.yml")

    assert en_keys == fr_keys, f"Locale key mismatch: {en_keys ^ fr_keys}"


def test_locales_are_non_empty():
    assert _keys("incident_draft.en-US.yml")
