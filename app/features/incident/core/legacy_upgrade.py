"""The incident legacy upgrade: brings every item below ``RECORD_VERSION`` to it, with its binding.

The runner of decisions/incident-management.md (Migration, legacy data upgrade):
one whole-table read capped by ``[incident_core] full_read_max_items``, the
shared per-item plan (``adapters/item_upgrade.py``, which uses the legacy item
bridge as the only mapping), and one structured report event per run. Per item
it puts the item's binding into the bindings table first (``put_if_not_exists``,
never overwriting), then makes one guarded records update with the version
marker last, so a crash between the two converges on the rerun. It reads and
writes through the records contract and asks the host ``TenantVerifier`` for the
Slack tenant it stamps on conversation references.

Nothing is guessed and nothing is half written. Any blocker (the cap, a failed
read, an item the plan or the write guard cannot read, an open item without a
conversation, a failed tenant check) fails the run before its first write, and a dry run lists every blocker. The
bridge reports only the first unreadable field of an item, so fixing one may
reveal another on the next run. Legacy-only attributes stay on the item; the
attributes the legacy and the end-state shapes share by name (status, severity,
security_incident and the two legacy roles) take their end-state value, which is
safe once no legacy reader of them remains (the first run follows TASK-145.8).

Registered by the response subdomain, which runs it from a scheduled job.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

import structlog

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import READ_LIMIT_EXCEEDED, RecordStore, RecordTable
from contracts.workplace import TenantVerifier, WorkplaceSystem
from features.incident.core.adapters.binding_items import binding_item
from features.incident.core.adapters.item_upgrade import ItemUpgrade, UnboundOpenItem, plan_item_upgrade
from features.incident.core.adapters.legacy_items import UnreadableLegacyItem

logger = structlog.get_logger()

type Failure = Literal[
    "read_failed",
    "read_limit_exceeded",
    "unreadable_items",
    "tenant_check_failed",
    "write_failed",
    "open_items_without_conversation",
]


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

    ``to_upgrade`` counts the items planned (legacy items and end-state items
    awaiting their binding); ``upgraded`` the legacy items written (bridge,
    binding and marker) and ``marker_raised`` the end-state items raised to the
    current version. ``pending`` counts the planned items not written: every one
    in a dry run, and in apply those whose guard was lost (changed or deleted
    since the read, retried next run). ``bindings_put`` and ``bindings_existing``
    count the binding puts that created the binding and that found it present
    (apply only); ``binding_skipped`` counts planned items with no binding to
    put (a Closed item without a conversation). ``unbound`` holds the ids of open
    items without a conversation, which block the run.
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
    bindings_put: int = 0
    bindings_existing: int = 0
    marker_raised: int = 0
    binding_skipped: int = 0
    unbound: tuple[object, ...] = ()
    unmatched_status: tuple[tuple[object, object], ...] = ()
    unreadable: tuple[tuple[object, str], ...] = ()
    dropped: tuple[tuple[object, str], ...] = ()
    tenant_check: TenantCheck | None = None

    @property
    def outcome(self) -> Literal["succeeded", "failed"]:
        """``failed`` when any blocker or write failure occurred."""
        return "failed" if self.failures else "succeeded"


class LegacyUpgrade:
    """Upgrades the incidents table's items below the current record version; ``run`` never raises for a store or vendor failure.

    ``tenants`` is the configured tenant per workplace system, as the read path's
    bridge gets it; the Slack one must be the tenant the verifier confirms.
    ``bindings`` is the bindings table the item bindings are put into.
    """

    def __init__(
        self,
        records: RecordStore,
        table: RecordTable,
        tenants: Mapping[WorkplaceSystem, str],
        verifier: TenantVerifier,
        max_items: int,
        *,
        bindings: RecordTable,
    ) -> None:
        self._records = records
        self._table = table
        self._bindings = bindings
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
        plans: list[ItemUpgrade] = []
        unmatched_status: list[tuple[object, object]] = []
        unreadable: list[tuple[object, str]] = []
        unbound: list[object] = []
        for item in items:
            planned = plan_item_upgrade(item, self._tenants)
            if planned is None:
                already_upgraded += 1
            elif isinstance(planned, UnreadableLegacyItem):
                if planned.field == "status":
                    unmatched_status.append((planned.incident_id, planned.value))
                else:
                    unreadable.append((planned.incident_id, planned.field))
            elif isinstance(planned, UnboundOpenItem):
                unbound.append(planned.incident_id)
            else:
                plans.append(planned)
        dropped = [(plan.incident_id, field) for plan in plans for field in plan.dropped]

        failures: list[Failure] = []
        if unmatched_status or unreadable:
            failures.append("unreadable_items")
        if unbound:
            failures.append("open_items_without_conversation")
        tenant_check = self._check_tenant()
        if tenant_check.outcome != "verified":
            failures.append("tenant_check_failed")

        upgraded = marker_raised = guard_lost = bindings_put = bindings_existing = 0
        if apply and not failures:
            for plan in plans:
                if plan.binding is not None:
                    put = self._records.put_if_not_exists(self._bindings, binding_item(plan.binding))
                    if not put.is_success:
                        failures.append("write_failed")
                        break
                    if put.data is True:
                        bindings_put += 1
                    else:
                        bindings_existing += 1
                result = self._records.update(self._table, {"id": plan.incident_id}, plan.changes, expected=plan.expected)
                if result.is_success and result.data is not None:
                    if plan.from_version is None:
                        upgraded += 1
                    else:
                        marker_raised += 1
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
            to_upgrade=len(plans),
            upgraded=upgraded,
            guard_lost=guard_lost,
            pending=len(plans) - upgraded - marker_raised,
            bindings_put=bindings_put,
            bindings_existing=bindings_existing,
            marker_raised=marker_raised,
            binding_skipped=sum(1 for plan in plans if plan.binding is None),
            unbound=tuple(unbound),
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
        "bindings_put": report.bindings_put,
        "bindings_existing": report.bindings_existing,
        "marker_raised": report.marker_raised,
        "binding_skipped": report.binding_skipped,
        "unbound": list(report.unbound),
        "unmatched_status": [{"incident_id": incident_id, "value": value} for incident_id, value in report.unmatched_status],
        "unreadable": [{"incident_id": incident_id, "field": field} for incident_id, field in report.unreadable],
        "dropped": [{"incident_id": incident_id, "field": field} for incident_id, field in report.dropped],
        "tenant_check": None if report.tenant_check is None else vars(report.tenant_check).copy(),
    }
    if report.failures:
        logger.error("incident_legacy_upgrade_report", **fields)
    else:
        logger.info("incident_legacy_upgrade_report", **fields)
