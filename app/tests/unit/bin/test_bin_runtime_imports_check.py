"""Behavior of the guardrail that keeps dev-only imports out of shipped code.

The import-classifying half is exercised against parsed source snippets rather
than files on disk, so the cases stay readable and independent of the tree's
real contents. The remaining tests pin the guard against the actual repository:
it must report the tree clean, and it must be wired into the Makefile and CI,
since a guard nothing runs protects nothing.
"""

import ast
import tomllib
from pathlib import Path

from bin import check_runtime_imports as checker

APP_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = APP_ROOT.parent


def _modules(source: str) -> list[str]:
    """Return the module names the guard treats as imported at runtime."""
    return [module for _, module in checker.iter_unguarded_imports(ast.parse(source))]


def test_plain_module_import_is_seen_as_a_runtime_import() -> None:
    """A top-level import is what production evaluates on boot, so it is reported."""
    assert _modules("from types_boto3_dynamodb.literals import SelectType") == ["types_boto3_dynamodb"]


def test_type_checking_guarded_import_is_not_a_runtime_import() -> None:
    """The guarded block never executes at runtime, which is the whole fix being enforced."""
    source = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types_boto3_dynamodb.literals import SelectType
"""

    assert _modules(source) == ["typing"]


def test_qualified_type_checking_guard_is_recognised() -> None:
    """`typing.TYPE_CHECKING` guards the same way the bare name does."""
    source = """
import typing

if typing.TYPE_CHECKING:
    import moto
"""

    assert _modules(source) == ["typing"]


def test_else_branch_of_a_type_checking_guard_is_a_runtime_import() -> None:
    """Only the guarded body is skipped; the else branch does run in production."""
    source = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import moto
else:
    import boto3
"""

    assert _modules(source) == ["typing", "boto3"]


def test_import_nested_in_a_function_is_a_runtime_import() -> None:
    """A deferred import still executes in production, so it is not exempt."""
    source = """
def build():
    import moto
    return moto
"""

    assert _modules(source) == ["moto"]


def test_relative_imports_are_not_reported() -> None:
    """A relative import is first-party by construction and ships with the wheel."""
    assert _modules("from . import sibling\nfrom ..pkg import other") == []


def test_dotted_import_is_reduced_to_its_top_level_distribution_module() -> None:
    """Only the top-level name maps to a distribution, so that is what is checked."""
    assert _modules("import boto3.dynamodb.types") == ["boto3"]


def test_runtime_distribution_closure_separates_runtime_from_dev_only() -> None:
    """The allowed set is the transitive closure of [project] dependencies.

    boto3 is a declared runtime dependency; types-boto3-dynamodb reaches the venv
    only through the dev group's ``types-boto3`` extras, and moto only through the
    dev group directly. Neither may be imported by shipped code.
    """
    distributions = checker.runtime_distributions(checker.load_pyproject())

    assert "boto3" in distributions
    assert "types-boto3-dynamodb" not in distributions
    assert "moto" not in distributions


def test_shipped_tree_has_no_unresolvable_imports() -> None:
    """The regression test proper: every shipped import resolves in the prod image.

    This is the check that fails if a dev-only import is reintroduced, which is
    how ``types_boto3_dynamodb`` reached production from db_operations.py.
    """
    assert checker.find_violations(checker.load_pyproject()) == []


def test_guard_is_wired_into_the_makefile_and_ci() -> None:
    """An unrun guard protects nothing, so both entry points are pinned."""
    makefile = (APP_ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci_code.yml").read_text(encoding="utf-8")

    assert "check-runtime-imports:" in makefile
    assert "make check-runtime-imports" in workflow


def test_type_stub_distributions_stay_out_of_runtime_dependencies() -> None:
    """The root cause was a dev-only distribution being imported, not declared wrongly.

    Keeping the stubs in the dev group is what makes the guard meaningful; were
    they promoted to runtime dependencies the import would resolve and the bug
    class would silently reopen.
    """
    pyproject = tomllib.loads((APP_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert all(not dep.startswith("types-boto3") for dep in pyproject["project"]["dependencies"])
    assert any(dep.startswith("types-boto3[") for dep in pyproject["dependency-groups"]["dev"])
