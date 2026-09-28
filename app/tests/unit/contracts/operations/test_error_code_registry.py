"""Behavior tests for the error-code registry.

The registry is enforced statically: production modules are parsed with ``ast``
(never imported) and every ``error_code=`` keyword whose value is a string
literal, a same-module string constant, or a literal operand of an ``or``
fallback must be a registry member. Values that are not statically resolvable
(``result.error_code``, calls, parameters) are pass-through sites and are
skipped by design.
"""

import ast
from pathlib import Path

from contracts.operations import ErrorCode

APP_ROOT = Path(__file__).resolve().parents[4]
EXCLUDED_DIRS = {"tests", ".venv", "__pycache__", ".mypy_cache"}


def _production_files() -> list[Path]:
    return sorted(path for path in APP_ROOT.rglob("*.py") if not EXCLUDED_DIRS.intersection(path.relative_to(APP_ROOT).parts))


def _module_string_constants(tree: ast.Module) -> dict[str, str]:
    constants: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            constants[node.targets[0].id] = node.value.value
    return constants


def _resolve_codes(value: ast.expr, constants: dict[str, str]) -> list[str]:
    match value:
        case ast.Constant(value=str() as code):
            return [code]
        case ast.Name(id=name) if name in constants:
            return [constants[name]]
        case ast.BoolOp(values=operands):
            return [code for operand in operands for code in _resolve_codes(operand, constants)]
        case _:
            return []


def _static_error_codes(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(), filename=str(path))
    constants = _module_string_constants(tree)
    return [
        (node.value.lineno, code)
        for node in ast.walk(tree)
        if isinstance(node, ast.keyword) and node.arg == "error_code"
        for code in _resolve_codes(node.value, constants)
    ]


def test_every_static_error_code_in_production_is_registered() -> None:
    """Every statically resolvable error_code in production code is an ErrorCode member.

    Parses each production module without importing it, so the scan is
    deterministic and side-effect free. The failure message lists each
    unregistered code as ``path:line:code`` so the fix is a one-line registry
    addition or a call-site correction.
    """
    registered = {member.value for member in ErrorCode}
    unregistered = [
        f"{path.relative_to(APP_ROOT)}:{line}:{code}"
        for path in _production_files()
        for line, code in _static_error_codes(path)
        if code not in registered
    ]

    assert unregistered == []


def test_scan_resolves_literals_constants_and_or_fallbacks() -> None:
    """The scan resolves the three static forms and skips pass-through values.

    Uses an inline source snippet rather than a production file so the
    enforcement test cannot pass vacuously if the resolver stops matching.
    """
    tree = ast.parse(
        "MISSING = 'RANGE_NOT_FOUND'\n"
        "f(error_code='TIMEOUT')\n"
        "f(error_code=MISSING)\n"
        "f(error_code=result.error_code or 'GROUP_DISCOVERY_FAILED')\n"
        "f(error_code=result.error_code)\n"
    )
    constants = _module_string_constants(tree)

    codes = [
        code
        for node in ast.walk(tree)
        if isinstance(node, ast.keyword) and node.arg == "error_code"
        for code in _resolve_codes(node.value, constants)
    ]

    assert sorted(codes) == ["GROUP_DISCOVERY_FAILED", "RANGE_NOT_FOUND", "TIMEOUT"]


def test_registry_distinguishes_unauthorized_with_unauthenticated_and_forbidden() -> None:
    """UNAUTHENTICATED and FORBIDDEN are both registered codes.

    UNAUTHENTICATED has no producer yet, so the production scan alone would
    never exercise it; this asserts the ADR's distinguishing pair directly.
    """
    assert ErrorCode.UNAUTHENTICATED == "UNAUTHENTICATED"
    assert ErrorCode.FORBIDDEN == "FORBIDDEN"
