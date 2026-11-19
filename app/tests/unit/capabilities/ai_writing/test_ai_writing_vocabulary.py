"""Tests that the AI writing capability stays in feature-free vocabulary.

Reads the capability's Python sources and its README (outside the required "Feature consumers"
list, which names the consuming packages) and asserts no feature term appears
(decisions/plugin-architecture.md, test 3).
"""

import re
from pathlib import Path

import pytest

import capabilities.ai_writing

pytestmark = pytest.mark.unit

_ROOT = Path(capabilities.ai_writing.__file__).parent
_FEATURE_TERMS = re.compile(r"\b(incident|timeline|transcript|slack)", re.IGNORECASE)


def _texts() -> dict[str, str]:
    texts = {str(path.relative_to(_ROOT)): path.read_text(encoding="utf-8") for path in _ROOT.rglob("*.py")}
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    texts["README.md"] = readme.split("## Feature consumers")[0]
    return texts


def test_no_feature_vocabulary_in_the_capability() -> None:
    hits = {name: _FEATURE_TERMS.findall(text) for name, text in _texts().items()}

    assert {name: found for name, found in hits.items() if found} == {}
