"""EN/FR parity of the postmortem catalogue, titles within Slack's cap, and no copy of its wording in the entry points."""

import ast

import pytest
import yaml

from features.incident.postmortem.entrypoints.texts import LOCALES_DIR

pytestmark = pytest.mark.unit

_ENTRYPOINTS_DIR = LOCALES_DIR.parent / "entrypoints"
_FILES = ("incident_postmortem.en-US.yml", "incident_postmortem.fr-FR.yml")
# Slack caps a modal's title, submit and close texts at 24 characters (Block Kit view objects).
_SLACK_TITLE_LIMIT = 24


def _catalogue(filename: str) -> dict[str, str]:
    data = yaml.safe_load((LOCALES_DIR / filename).read_text(encoding="utf-8"))
    return data["incident_postmortem"]


def test_en_and_fr_have_the_same_keys() -> None:
    en, fr = (set(_catalogue(name)) for name in _FILES)

    assert en
    assert en == fr, en ^ fr


@pytest.mark.parametrize("filename", _FILES)
@pytest.mark.parametrize("key", ["schedule.title", "working.title", "schedule.submit", "schedule.close", "result.close"])
def test_capped_labels_fit_slacks_limit(filename: str, key: str) -> None:
    assert len(_catalogue(filename)[key]) <= _SLACK_TITLE_LIMIT


def test_entry_points_hold_no_sentence_literal() -> None:
    """Wording lives in the catalogue only: no string literal in an entry point reads as a sentence."""
    offenders = []
    for source in _ENTRYPOINTS_DIR.glob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Module | ast.FunctionDef | ast.ClassDef)
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        }
        offenders += [
            f"{source.name}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.count(" ") >= 3
            and node.value[:1].isupper()
            and id(node) not in docstrings
        ]

    assert offenders == []
