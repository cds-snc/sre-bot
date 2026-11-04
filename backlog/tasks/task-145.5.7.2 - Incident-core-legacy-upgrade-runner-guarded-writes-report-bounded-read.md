---
id: TASK-145.5.7.2
title: 'Incident core legacy upgrade runner: guarded writes, report, bounded read'
status: To Do
assignee: []
created_date: '2026-11-04T14:04:00Z'
updated_date: '2026-11-04T17:26:00Z'
labels:
  - incident
  - features
  - records
  - reliability
dependencies:
  - TASK-145.5.7.1
references:
  - decisions/incident-management.md
  - decisions/reliability.md
  - decisions/cloud-portability.md
parent_task_id: TASK-145.5.7
priority: medium
ordinal: 474000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of 3 of TASK-145.5.7 (Stack K layer on top of 145.5.7.1; branch stack-k/task-145.5.7.2-upgrade-runner). The runner in features/incident/core, fully tested against InMemoryRecordStore with a fake TenantVerifier. Nothing registers it; revert is behavior-neutral.

Scope: [incident_core] full_read_max_items in common/settings.py (D5; TASK-145.12 reads it too); the runner (core/legacy_upgrade.py) with report; D6 guard; D7 unreadable handling incl. UpgradedItem.dropped in core/adapters/legacy_items.py; consumes TenantVerifier through the service scope (not a core port, not Slack); AC8 find_by_conversation warning. D8: no binding backfill here (TASK-145.7 adds it to this job later).

D6: one guarded RecordStore.update per item on record_version absent plus every scalar attribute the bridge read at its read value (None = absent): status, name, user_id, created_at, security_incident, channel_id, report_url, meet_url, severity, detection_time, start_impact_time, end_impact_time, incident_commander, operations_lead, plus each end-state attribute the job sets, guarded as read. teams (a list) is not guarded. Failed guard = guard_lost.
D7: unreadable items are reported as unmatched_status (id + stored value) and unreadable (id + field, no value); any of them stops the run before any apply write; dry run lists them all (the bridge reports only the first failing field per item). Drops (optional values the bridge discards) are carried on UpgradedItem.dropped and reported as a count with id and field; drops never block apply.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 [incident_core] full_read_max_items (default 10000, ge=1) is declared in features/incident/common/settings.py and app/config/base.toml; the whole-table read is RecordStore.read_all with it; past the cap the run fails before any apply write and the report names the cap
- [ ] #2 dry_run reports counts and writes nothing; apply upgrades every item without record_version through upgrade_legacy_item to the end-state attributes and reference maps and stamps record_version 1 (tested over each legacy item shape against InMemoryRecordStore)
- [ ] #3 Incidents not Closed get open_bucket OPEN and opened_at; Closed incidents get neither; a missing legacy security flag is written as security_incident false; legacy attributes stay on the item
- [ ] #4 Every write is one guarded update (record_version absent plus every scalar attribute the bridge read, at its read value; teams not guarded); reruns change nothing; an item changed or deleted since the read is counted guard_lost and left untouched
- [ ] #5 An item with an unmatched status or another unreadable field is reported (id + stored value for status; id + field otherwise) and stops the run before any apply write; dry_run lists all of them; UpgradedItem carries dropped field names and the report counts drops with id and field without blocking apply
- [ ] #6 Before apply writes anything the runner asks TenantVerifier (resolved from the service scope) for the Slack tenant; a mismatch or failed call fails the run reporting the expected and received ids; dry_run reports the same check
- [ ] #7 One structured report event per run carries scanned, already_upgraded, to_upgrade, upgraded, guard_lost, unmatched_status, unreadable, dropped, pending, cap and the tenant check; a failed run logs at error level
- [ ] #8 IncidentStore.find_by_conversation logs a warning naming the stored and requested tenants for each by_channel candidate it drops for its tenant
- [ ] #9 Verified by targeted tests, ruff, then once mypy and once full pytest, from app/; make check-import-contracts and make check-settings-key-ownership are green
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN OUTLINE (2026-11-04; full step-level plan to be refreshed at pickup against the then-current stack). STATUS: awaiting human review.
SIZE: ~245 production LOC, 7 files, one subsystem (incident core + its config key). Passes the gate. Revert = no behavior change (nothing registers the runner).
DEPENDS ON 145.5.7.1 (TenantVerifier, FakeTenantVerifier in tests/factories/tenant_verifier.py).

FILES
1. app/features/incident/common/settings.py (+3): full_read_max_items: int = Field(default=10000, ge=1, description=...) on IncidentCoreSettings; docstring Keys list. app/config/base.toml [incident_core] full_read_max_items = 10000 with a comment (+2). Stays in common/ (TASK-145.12 reads it too).
2. app/features/incident/core/adapters/legacy_items.py (+~15): UpgradedItem gains dropped: tuple[str, ...] = (); _dropped() (:~115) is the single place a drop happens, so collect the field names beside the log call (collector passed through the helpers or returned alongside the optional values); UnreadableLegacyItem unchanged. Existing log events stay.
3. app/features/incident/core/legacy_upgrade.py (new, ~190): LegacyUpgrade(records, table, tenants, max_items, verifier: TenantVerifier); run(*, apply) -> UpgradeReport (frozen dataclass: mode, outcome, failure, cap, counts scanned/already_upgraded/to_upgrade/upgraded/guard_lost/pending, unmatched_status tuple[(id, stored value)], unreadable tuple[(id, field)], dropped tuple[(id, field)], tenant_check). Flow: read_all(table, max_items=cap) (READ_LIMIT_EXCEEDED or store error: failed, report names cap, no write); classify each item (record_version present: already_upgraded; else upgrade_legacy_item); D7 unreadable lists (status -> unmatched_status with value; any other field -> unreadable without value; the bridge reports only the first failing field per item, noted in the report docstring); verifier.verified_tenant(WorkplaceSystem.SLACK) in dry_run and apply; any blocker (cap, unmatched/unreadable, tenant error) = failed run with no apply write, dry_run reports all blockers in one event; apply per item: changes = SetAttribute for every upgraded attribute except key id, + record_version=RECORD_VERSION, + (not Closed) open_bucket=OPEN_BUCKET and opened_at=declared_at; D6 expected = {"record_version": None} + {attr: read value or None} for the scalar attributes listed in D6 + {end-state attr: as read (None when absent)} for every attribute set; teams not guarded; applied -> upgraded; success with data None -> guard_lost; NOT_FOUND -> guard_lost; other error -> stop, failed, pending counts the rest. pending = to_upgrade - upgraded. One INFO event incident_legacy_upgrade_report (ERROR when failed); ids and fields only, never values except the unmatched status value. Per-item work is one function so TASK-145.7 can add its binding step (D8).
4. app/features/incident/core/store.py (+~8): AC8 warning incident_conversation_candidate_dropped in find_by_conversation (:139-146) with incident_id, stored/requested system and tenant; never the vendor id.
5. app/features/incident/core/api.py (+~25): build_legacy_upgrade(records, systems, settings, verifier) -> LegacyUpgrade; export LegacyUpgrade, UpgradeReport; update api-surface test. Do not touch the README core table row (conflicts with #1735).
6. (conditional, see CONFLICT 2) app/contracts/records/store.py:155 widen ExpectedValue, +1 line, plus infrastructure conversion if needed.

CONFLICT 2 TO RESOLVE BEFORE PICKUP (human): D6 guards severity, detection_time/start_impact_time/end_impact_time and created_at at their read value, but ExpectedValue = KeyValue | bool | None with KeyValue = str | int (contracts/records/store.py:21,155) and the Dynamo store returns numbers as Decimal (infrastructure/records/service.py:88). A Decimal read value cannot be passed as a guard under the current type. Proposed default: the runner converts an integral Decimal to int (exact) for the guard; a non-integral Decimal or other unguardable type (list, dict, float) makes the item unreadable with field = that attribute (reported, stops apply). Alternative: widen ExpectedValue to include Decimal (one-line contract change, dynamodb serialiser already accepts Decimal; needs in-memory equality check, Decimal(5) == 5 holds). Choose before .2 starts.

AC -> TEST (named at pickup, per testing-standards under app/tests/unit/features/incident/core/)
AC1: test_incident_common_settings_load.py (default, base.toml key, 0 rejected); test_incident_core_legacy_upgrade_preconditions.py (cap+1 fails, exactly cap passes, CountingRecordStore shows no write, report names cap).
AC2: test_incident_core_legacy_upgrade_apply.py (each legacy shape; fields equal upgrade_legacy_item output; record_version 1), test_incident_core_legacy_upgrade_dry_run.py (counts, zero writes).
AC3: test_incident_core_legacy_upgrade_apply.py (open vs Closed vs lowercase closed/reviewed; opened_at fixed width; missing security flag false; legacy attributes present).
AC4: test_incident_core_legacy_upgrade_guard.py (guard_lost for a concurrent end-state writer, for a legacy status edit, for an edit of each other guarded scalar, deletion; teams edit does not lose the guard), test_incident_core_legacy_upgrade_rerun.py (second apply: zero updates).
AC5: test_incident_core_legacy_upgrade_unreadable.py (unmatched status and other field; dry_run lists all; apply writes nothing), test_incident_core_legacy_item_dropped.py (dropped tuple per optional value; drops do not block apply, counted with id and field).
AC6: test_incident_core_legacy_upgrade_tenant.py (FakeTenantVerifier: mismatch and failure block apply, dry_run reports expected and received ids; success proceeds).
AC7: test_incident_core_legacy_upgrade_report.py (exactly one event per run with every key; failed run at error level; no values logged).
AC8: test_incident_core_incident_store_find_by_conversation_dropped.py.
AC9: gates.

ASSUMPTIONS: InMemoryRecordStore honors expected {attr: None} as absent (infrastructure/records/in_memory.py:50-53, verified); Dynamo parity is covered by the records conformance tests; the bridge reads exactly the attributes in D6 (legacy_items.py read via item.get: id, name, user_id, created_at, status, security_incident, channel_id, report_url, meet_url, severity, detection_time, start_impact_time, end_impact_time, incident_commander, operations_lead, teams): re-verify at pickup.
BLAST/ROLLBACK: unregistered code plus a settings key with a default; git revert restores everything.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-04 (human approved): OQ12: the records contract's ExpectedValue is not widened (no vendor type in the contract, cloud-portability.md contract 4). The runner guards an integral Decimal read value as int; a non-integral number in a guarded field makes the item unreadable (blocks apply, listed with id and field).

2026-11-04 (human approved, coordinated-incidents reconciliation): R1: the bridge (features/incident/core/adapters/legacy_items.py _product, shared by the read path and the job, Migration rule 2) no longer maps legacy teams to product: the legacy teams value is the name of the Drive folder chosen for the report's placement, not a product, and a product is not a team. product stays unset on every upgraded item; teams stays on the item as a legacy attribute (rule 5); it is not counted in dropped (deliberately unmapped; the bridge docstring and the run procedure say why); no engagement is inferred from it (D33). Nothing reads Incident.product today (rg), so the read path shows no change. Tests: a legacy item with one team and one with several both upgrade with product unset and teams kept; update the existing legacy-item tests that expect product = teams[0].
<!-- SECTION:NOTES:END -->
