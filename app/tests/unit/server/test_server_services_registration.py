"""Unit tests for the host registration of core services in the svcs registry.

The AWS client factory used by server.services is replaced with a MagicMock, so
the real DynamoDB-backed stores are constructed without any client or network.
The tests assert resolution by Protocol key, the per-registry singleton
lifetime, that a fake registered later replaces the host factory, and an AST
scan proving the concrete store classes are named only in server/services.py
outside the infrastructure that defines them.
"""

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import svcs

from contracts.coordination import ConditionalWriteStore
from contracts.records import RecordStore
from contracts.workplace import ConfiguredSystems
from infrastructure.coordination import DynamoDBConditionalWriteStore
from infrastructure.records.service import DynamoDBRecordStore
from server.services import CORE_SERVICES, register_core_services

pytestmark = pytest.mark.unit

APP_ROOT = Path(__file__).resolve().parents[3]
CONCRETE_NAMES = {"DynamoDBRecordStore", "DynamoDBConditionalWriteStore"}


@pytest.fixture(autouse=True)
def _stub_aws_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    get_aws_client = MagicMock(return_value=MagicMock(spec=["put_item", "get_item", "delete_item"]))
    monkeypatch.setattr("server.services.get_aws_client", get_aws_client)
    return get_aws_client


def _registry() -> svcs.Registry:
    registry = svcs.Registry()
    register_core_services(registry)
    return registry


def test_core_services_cover_records_coordination_and_configured_systems() -> None:
    assert {entry.contract for entry in CORE_SERVICES} == {RecordStore, ConditionalWriteStore, ConfiguredSystems}


def test_registered_contracts_resolve_to_the_dynamodb_stores() -> None:
    with svcs.Container(_registry()) as container:
        assert isinstance(container.get(RecordStore), DynamoDBRecordStore)
        assert isinstance(container.get(ConditionalWriteStore), DynamoDBConditionalWriteStore)


def test_a_registry_builds_each_service_once_across_containers(_stub_aws_client: MagicMock) -> None:
    registry = _registry()

    with svcs.Container(registry) as first, svcs.Container(registry) as second:
        assert first.get(RecordStore) is second.get(RecordStore)
        assert first.get(ConditionalWriteStore) is second.get(ConditionalWriteStore)

    assert _stub_aws_client.call_count == 2


def test_a_new_registry_builds_new_instances() -> None:
    with svcs.Container(_registry()) as first, svcs.Container(_registry()) as second:
        assert first.get(RecordStore) is not second.get(RecordStore)


def test_a_fake_registered_after_the_host_replaces_its_factory() -> None:
    registry = _registry()
    fake = MagicMock(spec=RecordStore)

    registry.register_value(RecordStore, fake)

    with svcs.Container(registry) as container:
        assert container.get(RecordStore) is fake


def test_concrete_store_classes_are_named_only_in_the_host_registration() -> None:
    """Outside infrastructure/ (which defines them) only server/services.py may name the classes."""
    offenders: list[str] = []
    for source in sorted(APP_ROOT.rglob("*.py")):
        relative = source.relative_to(APP_ROOT)
        if relative.parts[0] in {"infrastructure", "tests", ".venv"} or relative == Path("server/services.py"):
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"))
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        names |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names}
        offenders.extend(f"{relative}: {name}" for name in sorted(names & CONCRETE_NAMES))

    assert offenders == []
