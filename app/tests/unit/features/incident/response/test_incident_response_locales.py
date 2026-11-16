"""EN/FR parity of the incident response catalogue, and no copy of its wording in the entry points."""

import ast
from pathlib import Path

import pytest
import yaml

from features.incident.response import plugin

pytestmark = pytest.mark.unit

_LOCALES_DIR = Path(plugin.__file__).parent / "locales"
_ENTRYPOINTS_DIR = Path(plugin.__file__).parent / "entrypoints"


def _keys(filename: str) -> set[str]:
    data = yaml.safe_load((_LOCALES_DIR / filename).read_text(encoding="utf-8"))
    return set(data["incident_response"].keys())


def test_en_and_fr_have_the_same_keys() -> None:
    en = _keys("incident_response.en-US.yml")
    fr = _keys("incident_response.fr-FR.yml")

    assert en
    assert en == fr, en ^ fr


def test_entry_points_hold_no_sentence_literal() -> None:
    """Reply wording lives in the catalogue only: an entry point passes keys, so no string literal there is a sentence.

    Registration descriptions are exempt: the registrar takes a plain description beside its key
    (decisions/transport-slack.md, parsing and help).
    """
    offenders = []
    for source in _ENTRYPOINTS_DIR.glob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        registration_literals = {
            id(node)
            for call in ast.walk(tree)
            if isinstance(call, ast.Call) and getattr(call.func, "attr", "") == "register_command"
            for node in ast.walk(call)
        }
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Module | ast.FunctionDef | ast.ClassDef)
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.count(" ") >= 3
                and node.value[:1].isupper()
                and id(node) not in registration_literals | docstrings
            ):
                offenders.append(f"{source.name}:{node.lineno} {node.value!r}")
    assert offenders == []
