"""Structural guards for how the Google Workspace vendor package calls the SDK.

The package holds typed service factories and error classification only. Every
module is parsed and walked for the two retired dispatch shapes: resolving an SDK
resource or method from a runtime string through getattr, and discovering call
parameters by reading an SDK method's __doc__. Matching on the AST ignores prose
in docstrings and comments, so only executable references count.
"""

import ast
from collections.abc import Callable
from pathlib import Path

import integrations.google_workspace as google_workspace_package

PACKAGE_ROOT = Path(google_workspace_package.__file__).resolve().parent
APP_ROOT = PACKAGE_ROOT.parents[1]


def _package_modules() -> list[Path]:
    return sorted(path for path in PACKAGE_ROOT.rglob("*.py") if "__pycache__" not in path.parts)


def _is_dynamic_getattr(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and not isinstance(node.args[1], ast.Constant)
    )


def _reads_docstring(node: ast.expr) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "__doc__") or (
        isinstance(node, ast.Constant) and node.value == "__doc__"
    )


def _matches(tree: ast.AST, predicate: Callable[[ast.expr], bool]) -> list[int]:
    return sorted(node.lineno for node in ast.walk(tree) if isinstance(node, ast.expr) and predicate(node))


def _package_findings(predicate: Callable[[ast.expr], bool]) -> list[str]:
    findings: list[str] = []
    for path in _package_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(APP_ROOT).as_posix()
        findings.extend(f"{relative}:{lineno}" for lineno in _matches(tree, predicate))
    return findings


def test_detectors_flag_retired_shapes_and_ignore_static_access_and_prose() -> None:
    """Proves the guards below cannot pass vacuously.

    Each detector must flag its retired shape in an inline snippet and must not
    flag getattr with a literal attribute name or __doc__ mentioned only in prose.
    The package scan must also see the vendor client module.
    """
    retired = ast.parse(
        "def call(resource, method):\n"
        "    api = getattr(resource, method)\n"
        "    if hasattr(api, '__doc__'):\n"
        "        return api.__doc__\n"
    )
    compliant = ast.parse(
        '"""Never read __doc__ or getattr(resource, method) here."""\n'
        "# getattr(resource, method) and __doc__ in a comment\n"
        "def call(service):\n"
        "    return getattr(service, 'users', None)\n"
    )

    assert _matches(retired, _is_dynamic_getattr) == [2]
    assert _matches(retired, _reads_docstring) == [3, 4]
    assert _matches(compliant, _is_dynamic_getattr) == []
    assert _matches(compliant, _reads_docstring) == []
    assert PACKAGE_ROOT / "client.py" in _package_modules()


def test_google_workspace_package_resolves_no_sdk_attribute_from_a_runtime_string() -> None:
    """Every SDK resource and method is reached through a typed attribute access.

    A getattr whose attribute name is not a literal is string dispatch; the
    assertion lists each offending module and line so a failure names the site.
    """
    assert _package_findings(_is_dynamic_getattr) == []


def test_google_workspace_package_reads_no_sdk_docstring() -> None:
    """No module discovers call parameters by reading an SDK method's __doc__.

    Both the attribute read and a hasattr probe on the literal name count; the
    assertion lists each offending module and line so a failure names the site.
    """
    assert _package_findings(_reads_docstring) == []
