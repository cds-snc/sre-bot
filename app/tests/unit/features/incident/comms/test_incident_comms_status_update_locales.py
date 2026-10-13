"""EN/FR parity of the incident comms status-update locale catalogue, and no second copy of it in code."""

import ast
from pathlib import Path

import pytest
import yaml

import features.incident.comms as comms_pkg

pytestmark = pytest.mark.unit

_LOCALES_DIR = Path(comms_pkg.__file__).parent / "locales"
_ENTRYPOINTS_DIR = Path(comms_pkg.__file__).parent / "entrypoints"
_LANGUAGE_KEYS = {"en", "fr", "en-US", "fr-FR"}


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


def _language_keyed_tables(source: Path) -> list[str]:
    """Return the module-level names suffixed ``_EN``/``_FR`` and the dict literals keyed by a language, by line."""
    tree = ast.parse(source.read_text(encoding="utf-8"))
    offenders = []
    for node in tree.body:
        if isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id.upper().endswith(("_EN", "_FR")):
                    offenders.append(f"{source.name}:{node.lineno} {target.id}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = {key.value for key in node.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)}
            if keys & _LANGUAGE_KEYS:
                offenders.append(f"{source.name}:{node.lineno} dict keyed by {sorted(keys & _LANGUAGE_KEYS)}")
    return offenders


def test_entrypoint_modules_hold_no_language_keyed_tables():
    """No module under ``entrypoints/`` keeps its own EN or FR wording: the catalogue is the only copy.

    An AST scan finds module-level names ending in ``_EN`` or ``_FR`` and dict
    literals keyed by a language or locale, which is how a fallback table would
    reappear; the views pass the key as the neutral fallback instead.
    """
    sources = sorted(_ENTRYPOINTS_DIR.glob("*.py"))

    assert sources
    assert [offender for source in sources for offender in _language_keyed_tables(source)] == []
