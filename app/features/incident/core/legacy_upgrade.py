"""The incident legacy upgrade: writes the end-state shape onto every item without ``record_version``.

The runner of decisions/incident-management.md (Migration, legacy data upgrade):
one whole-table read capped by ``[incident_core] full_read_max_items``, the shared
legacy item bridge (``adapters/legacy_items.py``) as the only mapping, one
guarded records update per item, and one structured report event per run. It
reads and writes through the records contract and asks the host
``TenantVerifier`` for the Slack tenant it stamps on conversation references.

Nothing is guessed and nothing is half written. Any blocker (the cap, a failed
read, an item the bridge or the write guard cannot read, a failed tenant check)
fails the run before its first write, and a dry run lists every blocker. The
bridge reports only the first unreadable field of an item, so fixing one may
reveal another on the next run. Legacy-only attributes stay on the item; the
attributes the legacy and the end-state shapes share by name (status, severity,
security_incident and the two legacy roles) take their end-state value, which is
safe once no legacy reader of them remains (the first run follows TASK-145.8).

Registered by the response subdomain (TASK-145.5.7.3); the record's binding step
is added to ``_plan_item`` later (TASK-145.7) under a raised version marker.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

import structlog

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import READ_LIMIT_EXCEEDED, ExpectedValue, RecordChange, RecordStore, RecordTable, SetAttribute
from contracts.workplace import TenantVerifier, WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.legacy_items import UnreadableLegacyItem, UpgradedItem, upgrade_legacy_item
from features.incident.core.store import OPEN_BUCKET, RECORD_VERSION

logger = structlog.get_logger()

# Every scalar the bridge reads, guarded at its read value so a write never lands on a changed item.
_READ_ATTRIBUTES = (
    "status",
    "name",
    "user_id",
    "created_at",
    "security_incident",
    "channel_id",
    "report_url",
    "meet_url",
    "severity",
    "detection_time",
    "start_impact_time",
    "end_impact_time",
    "incident_commander",
    "operations_lead",
)

type Failure = Literal["read_failed", "read_limit_exceeded", "unreadable_items", "tenant_check_failed", "write_failed"]


@dataclass(frozen=True)
class TenantCheck:
    """The verifier's answer for the Slack tenant.

    Attributes:
        outcome: ``verified``, ``mismatch`` (the message names the expected and received ids) or ``failed``.
        tenant: The verified tenant id, when verified.
        status: The verifier's result status.
        error_code: The verifier's error code, when not verified.
        message: The verifier's message, when not verified.
    """

    outcome: Literal["verified", "mismatch", "failed"]
    tenant: str | None
    status: str
    error_code: str | None
    message: str | None


@dataclass(frozen=True)
class UpgradeReport:
    """What one run read, wrote and could not do.

    ``pending`` counts the items still without ``record_version`` after the run:
    every item to upgrade in a dry run, and in apply those not upgraded
    (``guard_lost`` items, changed or deleted since the read, are retried next run).
    ``unmatched_status`` holds (id, stored status); ``unreadable`` and ``dropped``
    hold (id, legacy attribute) and never a stored value.
    """

    mode: Literal["dry_run", "apply"]
    failures: tuple[Failure, ...]
    cap: int
    scanned: int = 0
    already_upgraded: int = 0
    to_upgrade: int = 0
    upgraded: int = 0
    guard_lost: int = 0
    pending: int = 0
    unmatched_status: tuple[tuple[object, object], ...] = ()
    unreadable: tuple[tuple[object, str], ...] = ()
    dropped: tuple[tuple[object, str], ...] = ()
    tenant_check: TenantCheck | None = None

    @property
    def outcome(self) -> Literal["succeeded", "failed"]:
        """``failed`` when any blocker or write failure occurred."""
        return "failed" if self.failures else "succeeded"


@dataclass(frozen=True)
class _ItemWrite:
    key: dict[str, Any]
    changes: tuple[RecordChange, ...]
    expected: dict[str, ExpectedValue]


class _UnguardableError(Exception):
    def __init__(self, field: str) -> None:
        super().__init__(field)
        self.field = field


class LegacyUpgrade:
    """Upgrades the incidents table's legacy items; ``run`` never raises for a store or vendor failure.

    ``tenants`` is the configured tenant per workplace system, as the read path's
    bridge gets it; the Slack one must be the tenant the verifier confirms.
    """

    def __init__(
        self,
        records: RecordStore,
        table: RecordTable,
        tenants: Mapping[WorkplaceSystem, str],
        verifier: TenantVerifier,
        max_items: int,
    ) -> None:
        self._records = records
        self._table = table
        self._tenants = dict(tenants)
        self._verifier = verifier
        self._max_items = max_items

    def run(self, *, apply: bool) -> UpgradeReport:
        """Read, classify and check the tenant; with ``apply`` and no blocker, write each item; log the report."""
        report = self._run(apply=apply)
        _log(report)
        return report

    def _run(self, *, apply: bool) -> UpgradeReport:
        mode: Literal["dry_run", "apply"] = "apply" if apply else "dry_run"
        read = self._records.read_all(self._table, max_items=self._max_items)
        if not read.is_success:
            failure: Failure = "read_limit_exceeded" if read.error_code == READ_LIMIT_EXCEEDED else "read_failed"
            return UpgradeReport(mode=mode, failures=(failure,), cap=self._max_items)

        items: list[Mapping[str, Any]] = read.data or []
        already_upgraded = 0
        writes: list[_ItemWrite] = []
        unmatched_status: list[tuple[object, object]] = []
        unreadable: list[tuple[object, str]] = []
        dropped: list[tuple[object, str]] = []
        for item in items:
            if item.get("record_version") is not None:
                already_upgraded += 1
                continue
            upgraded = upgrade_legacy_item(item, self._tenants)
            if isinstance(upgraded, UnreadableLegacyItem):
                if upgraded.field == "status":
                    unmatched_status.append((upgraded.incident_id, upgraded.value))
                else:
                    unreadable.append((upgraded.incident_id, upgraded.field))
                continue
            dropped.extend((upgraded.item["id"], field) for field in upgraded.dropped)
            try:
                writes.append(_plan_item(item, upgraded))
            except _UnguardableError as exc:
                unreadable.append((upgraded.item["id"], exc.field))

        failures: list[Failure] = []
        if unmatched_status or unreadable:
            failures.append("unreadable_items")
        tenant_check = self._check_tenant()
        if tenant_check.outcome != "verified":
            failures.append("tenant_check_failed")

        upgraded_count = guard_lost = 0
        if apply and not failures:
            for write in writes:
                result = self._records.update(self._table, write.key, write.changes, expected=write.expected)
                if result.is_success and result.data is not None:
                    upgraded_count += 1
                elif result.is_success or result.status is OperationStatus.NOT_FOUND:
                    guard_lost += 1
                else:
                    failures.append("write_failed")
                    break

        return UpgradeReport(
            mode=mode,
            failures=tuple(failures),
            cap=self._max_items,
            scanned=len(items),
            already_upgraded=already_upgraded,
            to_upgrade=len(writes),
            upgraded=upgraded_count,
            guard_lost=guard_lost,
            pending=len(writes) - upgraded_count,
            unmatched_status=tuple(unmatched_status),
            unreadable=tuple(unreadable),
            dropped=tuple(dropped),
            tenant_check=tenant_check,
        )

    def _check_tenant(self) -> TenantCheck:
        result: OperationResult[str] = self._verifier.verified_tenant(WorkplaceSystem.SLACK)
        configured = self._tenants.get(WorkplaceSystem.SLACK)
        if result.is_success and result.data is not None and result.data == configured:
            return TenantCheck("verified", result.data, result.status.value, None, None)
        if result.is_success:
            # The contract promises the configured tenant; anything else is treated as a mismatch.
            message = f"verified Slack tenant {result.data} is not the configured tenant {configured}"
            return TenantCheck("mismatch", None, result.status.value, ErrorCode.TENANT_MISMATCH, message)
        outcome: Literal["mismatch", "failed"] = "mismatch" if result.error_code == ErrorCode.TENANT_MISMATCH else "failed"
        return TenantCheck(outcome, None, result.status.value, result.error_code, result.message)


def _plan_item(item: Mapping[str, Any], upgraded: UpgradedItem) -> _ItemWrite:
    """Return the one guarded update that upgrades ``item``; raises ``_UnguardableError`` naming a read value no guard can hold."""
    values = {attribute: value for attribute, value in upgraded.item.items() if attribute != "id"}
    values["record_version"] = RECORD_VERSION
    if values["status"] != IncidentStatus.CLOSED.value:
        values["open_bucket"] = OPEN_BUCKET
        values["opened_at"] = values["declared_at"]
    expected = {attribute: _guard_value(attribute, item.get(attribute)) for attribute in (*_READ_ATTRIBUTES, *values)}
    changes = tuple(SetAttribute(attribute, value) for attribute, value in values.items())
    return _ItemWrite(key={"id": upgraded.item["id"]}, changes=changes, expected=expected)


def _guard_value(attribute: str, value: object) -> ExpectedValue:
    """Return ``value`` as an equality guard: text, bool, int and None as read, an integral Decimal as int."""
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, Decimal) and value.is_finite() and value == value.to_integral_value():
        return int(value)
    raise _UnguardableError(attribute)


def _log(report: UpgradeReport) -> None:
    fields: dict[str, object] = {
        "mode": report.mode,
        "outcome": report.outcome,
        "failures": list(report.failures),
        "cap": report.cap,
        "scanned": report.scanned,
        "already_upgraded": report.already_upgraded,
        "to_upgrade": report.to_upgrade,
        "upgraded": report.upgraded,
        "guard_lost": report.guard_lost,
        "pending": report.pending,
        "unmatched_status": [{"incident_id": incident_id, "value": value} for incident_id, value in report.unmatched_status],
        "unreadable": [{"incident_id": incident_id, "field": field} for incident_id, field in report.unreadable],
        "dropped": [{"incident_id": incident_id, "field": field} for incident_id, field in report.dropped],
        "tenant_check": None if report.tenant_check is None else vars(report.tenant_check).copy(),
    }
    if report.failures:
        logger.error("incident_legacy_upgrade_report", **fields)
    else:
        logger.info("incident_legacy_upgrade_report", **fields)
