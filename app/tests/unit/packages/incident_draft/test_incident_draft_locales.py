"""EN/FR locale catalogue parity for the incident_draft package."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import packages.incident_draft as incident_draft_pkg

pytestmark = pytest.mark.unit

_LOCALES_DIR = Path(incident_draft_pkg.__file__).parent / "locales"


def _keys(filename: str) -> set[str]:
    data = yaml.safe_load((_LOCALES_DIR / filename).read_text(encoding="utf-8"))
    return set(data["incident_draft"].keys())


def test_en_fr_locales_have_identical_keys():
    en_keys = _keys("incident_draft.en-US.yml")
    fr_keys = _keys("incident_draft.fr-FR.yml")

    assert en_keys == fr_keys, f"Locale key mismatch: {en_keys ^ fr_keys}"


def test_locales_are_non_empty():
    assert _keys("incident_draft.en-US.yml")
