"""Behavior tests for the in-memory fake coverage freeze-baseline checker.

Each test builds a throwaway app tree (contracts/, capabilities/, infrastructure/,
features/, packages/) under ``tmp_path`` and points the checker's APP_ROOT and
BASELINE_PATH at it, so no test depends on the real packages. The final tests
inspect the committed baseline and run the checker against the real tree.
"""

from pathlib import Path

import pytest

from bin import check_fake_coverage as checker

PROTOCOL_SOURCE = "from typing import Protocol\n\n\nclass {name}(Protocol):\n    def get(self) -> str: ...\n"
CONTRACT = {"contracts/records/protocol.py": PROTOCOL_SOURCE.format(name="RecordStore")}
REAL_IMPLEMENTATION = {
    "infrastructure/records/service.py": (
        "from contracts.records.protocol import RecordStore\n\n\nclass DynamoDBRecordStore(RecordStore):\n    pass\n"
    ),
}
FAKE = {
    "infrastructure/records/in_memory.py": (
        "from contracts.records.protocol import RecordStore\n\n\nclass InMemoryRecordStore(RecordStore):\n    pass\n"
    ),
}
CAPABILITY_API = {"capabilities/directory/api.py": PROTOCOL_SOURCE.format(name="DirectoryProvider")}
CAPABILITY_ADAPTER = {
    "capabilities/directory/adapters/google.py": (
        "from capabilities.directory.api import DirectoryProvider\n\n\n"
        "class GoogleDirectoryProvider(DirectoryProvider):\n    pass\n"
    ),
}


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _use_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    files: dict[str, str],
    baseline: str = "# empty baseline\n",
) -> None:
    """Write ``files`` under a fake app root and aim the checker at it."""
    app_root = tmp_path / "app"
    app_root.mkdir()
    for relative_path, content in files.items():
        _write(app_root / relative_path, content)
    baseline_path = tmp_path / "baseline.txt"
    _write(baseline_path, baseline)
    monkeypatch.setattr(checker, "APP_ROOT", app_root)
    monkeypatch.setattr(checker, "BASELINE_PATH", baseline_path)


def test_main_passes_for_hosting_contract_with_subclassing_fake(tmp_path, monkeypatch):
    _use_tree(tmp_path, monkeypatch, {**CONTRACT, **REAL_IMPLEMENTATION, **FAKE})

    assert checker.find_current_violations() == set()
    assert checker.main() == 0


def test_main_fails_for_hosting_contract_without_fake(tmp_path, monkeypatch, capsys):
    """A contracts Protocol an infrastructure class subclasses is a hosting contract and needs a fake."""
    _use_tree(tmp_path, monkeypatch, {**CONTRACT, **REAL_IMPLEMENTATION})

    exit_code = checker.main()

    assert exit_code == 1
    assert "contracts/records/protocol.py:RecordStore" in capsys.readouterr().out


@pytest.mark.parametrize(
    "fake_files",
    [
        pytest.param(
            {
                "infrastructure/records/fakes.py": (
                    "from contracts.records.protocol import RecordStore\n\n\nclass InMemoryRecordStore(RecordStore):\n    pass\n"
                ),
            },
            id="fake-outside-in-memory-module",
        ),
        pytest.param(
            {"infrastructure/records/in_memory.py": "class InMemoryRecordStore:\n    def get(self) -> str:\n        return ''\n"},
            id="structural-only-fake",
        ),
        pytest.param(
            {
                "features/incident/core/adapters/in_memory.py": (
                    "from contracts.records.protocol import RecordStore\n\n\nclass InMemoryRecordStore(RecordStore):\n    pass\n"
                ),
            },
            id="fake-in-feature-tree",
        ),
    ],
)
def test_find_current_violations_rejects_fake_not_declared_in_package_in_memory_module(tmp_path, monkeypatch, fake_files):
    """Only an explicit subclass in an infrastructure/ or capabilities/ in_memory.py module lets mypy prove conformance."""
    _use_tree(tmp_path, monkeypatch, {**CONTRACT, **REAL_IMPLEMENTATION, **fake_files})

    assert checker.find_current_violations() == {"contracts/records/protocol.py:RecordStore"}


def test_contracts_protocol_without_infrastructure_implementation_is_not_covered_and_is_printed(tmp_path, monkeypatch, capsys):
    """Registrars and extension points are implemented by the host, so they fall out by rule and are listed."""
    _use_tree(
        tmp_path,
        monkeypatch,
        {
            **CONTRACT,
            **REAL_IMPLEMENTATION,
            **FAKE,
            "contracts/plugins/hookspecs.py": PROTOCOL_SOURCE.format(name="EventHandlerRegistrar"),
            "server/plugins.py": (
                "from contracts.plugins.hookspecs import EventHandlerRegistrar\n\n\n"
                "class HostRegistrar(EventHandlerRegistrar):\n    pass\n"
            ),
        },
    )

    exit_code = checker.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert checker.find_current_violations() == set()
    assert checker.find_uncovered_contracts() == ["contracts/plugins/hookspecs.py:EventHandlerRegistrar"]
    assert "contracts/plugins/hookspecs.py:EventHandlerRegistrar" in output


def test_infrastructure_fake_alone_does_not_make_contracts_protocol_a_hosting_contract(tmp_path, monkeypatch):
    """Coverage keys on a real infrastructure implementation; a fake on its own satisfies nothing and requires nothing."""
    _use_tree(tmp_path, monkeypatch, {**CONTRACT, **FAKE})

    assert checker.find_current_violations() == set()
    assert checker.find_uncovered_contracts() == ["contracts/records/protocol.py:RecordStore"]


def test_capability_api_protocol_with_adapter_needs_fake(tmp_path, monkeypatch):
    _use_tree(tmp_path, monkeypatch, {**CAPABILITY_API, **CAPABILITY_ADAPTER})

    assert checker.find_current_violations() == {"capabilities/directory/api.py:DirectoryProvider"}


def test_capability_api_protocol_with_adapter_and_fake_passes(tmp_path, monkeypatch):
    _use_tree(
        tmp_path,
        monkeypatch,
        {
            **CAPABILITY_API,
            **CAPABILITY_ADAPTER,
            "capabilities/directory/in_memory.py": (
                "from capabilities.directory.api import DirectoryProvider\n\n\n"
                "class InMemoryDirectoryProvider(DirectoryProvider):\n    pass\n"
            ),
        },
    )

    assert checker.find_current_violations() == set()


def test_capability_api_protocol_without_adapter_is_not_covered(tmp_path, monkeypatch):
    """An api.py Protocol no adapter implements faces no external system (for example an engine extension point)."""
    _use_tree(tmp_path, monkeypatch, CAPABILITY_API)

    assert checker.find_current_violations() == set()


def test_capability_protocol_implemented_by_another_capability_adapter_is_not_covered(tmp_path, monkeypatch):
    """Only the capability's own adapters/ make its api.py Protocol externally facing."""
    _use_tree(
        tmp_path,
        monkeypatch,
        {
            **CAPABILITY_API,
            "capabilities/people/adapters/google.py": (
                "from capabilities.directory.api import DirectoryProvider\n\n\nclass Other(DirectoryProvider):\n    pass\n"
            ),
        },
    )

    assert checker.find_current_violations() == set()


def test_protocol_defined_in_infrastructure_is_covered_by_location(tmp_path, monkeypatch):
    """A hosting contract not yet moved to contracts/ needs a fake even when its implementation is structural."""
    _use_tree(
        tmp_path,
        monkeypatch,
        {
            "infrastructure/audit/protocol.py": PROTOCOL_SOURCE.format(name="AuditTrailService"),
            "infrastructure/audit/service.py": "class DynamoDBAuditTrailService:\n    pass\n",
        },
    )

    assert checker.find_current_violations() == {"infrastructure/audit/protocol.py:AuditTrailService"}


def test_protocol_defined_in_infrastructure_passes_with_fake(tmp_path, monkeypatch):
    _use_tree(
        tmp_path,
        monkeypatch,
        {
            "infrastructure/audit/protocol.py": PROTOCOL_SOURCE.format(name="AuditTrailService"),
            "infrastructure/audit/in_memory.py": (
                "from infrastructure.audit.protocol import AuditTrailService\n\n\n"
                "class InMemoryAuditTrailService(AuditTrailService):\n    pass\n"
            ),
        },
    )

    assert checker.find_current_violations() == set()


def test_contracts_protocol_with_subclassing_implementation_and_fake_passes(tmp_path, monkeypatch):
    """A contracts/ Protocol hosted by an infrastructure class needs the in_memory.py fake that subclasses it."""
    _use_tree(
        tmp_path,
        monkeypatch,
        {
            "contracts/coordination/store.py": PROTOCOL_SOURCE.format(name="ConditionalWriteStore"),
            "infrastructure/coordination/dynamodb.py": (
                "from contracts.coordination.store import ConditionalWriteStore\n\n\n"
                "class DynamoDBConditionalWriteStore(ConditionalWriteStore):\n    pass\n"
            ),
            "infrastructure/coordination/in_memory.py": (
                "from contracts.coordination.store import ConditionalWriteStore\n\n\n"
                "class InMemoryConditionalWriteStore(ConditionalWriteStore):\n    pass\n"
            ),
        },
    )

    assert checker.find_current_violations() == set()


def test_contracts_protocol_without_subclassing_fake_is_a_violation(tmp_path, monkeypatch):
    _use_tree(
        tmp_path,
        monkeypatch,
        {
            "contracts/coordination/store.py": PROTOCOL_SOURCE.format(name="ConditionalWriteStore"),
            "infrastructure/coordination/dynamodb.py": (
                "from contracts.coordination.store import ConditionalWriteStore\n\n\n"
                "class DynamoDBConditionalWriteStore(ConditionalWriteStore):\n    pass\n"
            ),
        },
    )

    assert checker.find_current_violations() == {"contracts/coordination/store.py:ConditionalWriteStore"}


def test_feature_package_and_capability_adapter_protocols_are_never_scanned(tmp_path, monkeypatch):
    """Feature Path B adapters are out by rule: none of these trees is read for Protocol definitions."""
    _use_tree(
        tmp_path,
        monkeypatch,
        {
            "features/incident/comms/ports.py": PROTOCOL_SOURCE.format(name="StatusPagePublisher"),
            "features/incident/core/api.py": PROTOCOL_SOURCE.format(name="IncidentLookup"),
            "packages/oncall_sync/ports.py": PROTOCOL_SOURCE.format(name="OnCallScheduleProvider"),
            "capabilities/directory/adapters/ports.py": PROTOCOL_SOURCE.format(name="AdapterOnlyPort"),
            "capabilities/directory/service.py": PROTOCOL_SOURCE.format(name="NonApiPort"),
            "integrations/openai/summarizer.py": PROTOCOL_SOURCE.format(name="Summarizer"),
        },
    )

    assert checker.find_current_violations() == set()


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("import typing\n\n\nclass AuditTrailService(typing.Protocol):\n    pass\n", id="attribute-base"),
        pytest.param("from typing import Protocol\n\n\nclass AuditTrailService[T](Protocol):\n    pass\n", id="pep-695"),
        pytest.param(
            "from typing import Protocol, TypeVar\n\nT = TypeVar('T')\n\n\nclass AuditTrailService(Protocol[T]):\n    pass\n",
            id="subscripted-protocol",
        ),
    ],
)
def test_protocol_definition_forms_are_detected(tmp_path, monkeypatch, source):
    _use_tree(tmp_path, monkeypatch, {"infrastructure/audit/protocol.py": source})

    assert checker.find_current_violations() == {"infrastructure/audit/protocol.py:AuditTrailService"}


@pytest.mark.parametrize(
    "fake_source",
    [
        pytest.param(
            "import contracts.records.protocol as p\n\n\nclass InMemoryRecordStore(p.RecordStore):\n    pass\n",
            id="attribute-base",
        ),
        pytest.param(
            "from contracts.records.protocol import RecordStore\n\n\nclass InMemoryRecordStore(RecordStore[str]):\n    pass\n",
            id="subscripted-base",
        ),
    ],
)
def test_fake_base_forms_are_recognised(tmp_path, monkeypatch, fake_source):
    _use_tree(
        tmp_path,
        monkeypatch,
        {**CONTRACT, **REAL_IMPLEMENTATION, "infrastructure/records/in_memory.py": fake_source},
    )

    assert checker.find_current_violations() == set()


def test_main_passes_when_gap_is_baselined(tmp_path, monkeypatch):
    _use_tree(
        tmp_path,
        monkeypatch,
        {**CONTRACT, **REAL_IMPLEMENTATION},
        baseline="contracts/records/protocol.py:RecordStore  # TASK-1\n",
    )

    assert checker.main() == 0


def test_main_reports_stale_baseline_entry_without_failing(tmp_path, monkeypatch, capsys):
    _use_tree(
        tmp_path,
        monkeypatch,
        {**CONTRACT, **REAL_IMPLEMENTATION, **FAKE},
        baseline="infrastructure/audit/protocol.py:AuditTrailService  # TASK-122\n",
    )

    exit_code = checker.main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "INFO" in output
    assert "infrastructure/audit/protocol.py:AuditTrailService" in output


def test_cache_directories_are_not_scanned(tmp_path, monkeypatch):
    _use_tree(
        tmp_path,
        monkeypatch,
        {"infrastructure/audit/__pycache__/protocol.py": PROTOCOL_SOURCE.format(name="AuditTrailService")},
    )

    assert checker.find_current_violations() == set()


def test_real_baseline_entries_each_name_the_task_that_retires_them():
    """A gap without an owner never ratchets down, so every committed entry carries its retiring task."""
    lines = [
        line.strip()
        for line in checker.BASELINE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    assert lines
    assert [line for line in lines if "# TASK-" not in line] == []


def test_real_tree_has_no_net_new_gaps():
    """The committed tree passes: RecordStore and ConditionalWriteStore have fakes, every other gap is baselined."""
    current = checker.find_current_violations()

    assert current - checker.load_baseline_entries() == set()
    assert "contracts/records/store.py:RecordStore" not in current
    assert "contracts/coordination/store.py:ConditionalWriteStore" not in current
