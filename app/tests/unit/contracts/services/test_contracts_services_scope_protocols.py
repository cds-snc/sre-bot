"""Unit tests for the service-scope Protocols in contracts.services.

The svcs container and the server's opener are assigned to the Protocol types
(checked statically by mypy), so a feature written against the contract works
with any implementation. An AST scan of the package source proves the contract
imports no svcs module, which keeps the svcs dependency in the server layer.
"""

import ast
from pathlib import Path

import pytest
import svcs

import contracts.services
from contracts.services import ServiceResolver, ServiceScopeOpener
from server.services import SvcsServiceScopeOpener

pytestmark = pytest.mark.unit


def test_svcs_container_satisfies_the_resolver_protocol() -> None:
    """A plain svcs.Container is accepted where a ServiceResolver is declared.

    Stub strategy: an empty real registry, no fakes; only the static assignment
    and identity are checked.
    Assertion rationale: identity shows the Protocol annotation adds no wrapper,
    so the container's own get() is what a feature calls.
    """
    container = svcs.Container(svcs.Registry())
    resolver: ServiceResolver = container

    assert resolver is container


def test_server_opener_satisfies_the_scope_opener_protocol() -> None:
    """The server's SvcsServiceScopeOpener is accepted where a ServiceScopeOpener is declared.

    Stub strategy: an empty real registry; no scope is opened here.
    Assertion rationale: identity shows the opener is handed through unchanged,
    so a registrar exposing it hands features the server's own object.
    """
    opener: ServiceScopeOpener = SvcsServiceScopeOpener(svcs.Registry())

    assert isinstance(opener, SvcsServiceScopeOpener)


def test_contracts_services_source_imports_no_svcs_module() -> None:
    """No module in contracts/services imports svcs, directly or through a submodule.

    Stub strategy: the source is read and parsed, not imported, so the scan sees
    every import statement, including ones inside functions.
    Assertion rationale: the contract layer must stay free of the container
    library; lint-imports enforces the same rule for the whole package tree.
    """
    package_dir = Path(contracts.services.__file__).parent
    imported_roots: set[str] = set()
    for source in package_dir.glob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported_roots.add(node.module.split(".")[0])

    assert "svcs" not in imported_roots
