---
id: TASK-145.5.7
title: >-
  Incident legacy upgrade job: upgrade every item without record_version to the
  end-state shape, the open index included
status: To Do
assignee: []
created_date: 2026-10-14 23:10
updated_date: '2026-11-04T18:01:00Z'
labels:
  - incident
  - features
  - records
  - reliability
dependencies:
  - TASK-145.5.2
  - TASK-145.5.8
  - TASK-27.5
  - TASK-157
references:
  - decisions/reliability.md
  - decisions/lifecycle.md
  - https://12factor.net/admin-processes
  - >-
    https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-indexes-general-sparse-indexes.html
  - https://github.com/cds-snc/sre-bot/issues/1696
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 393000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 11 of Stack K (handoff doc-13). The single legacy data upgrade for the incidents table. Legacy items carry legacy attribute names, bare reference strings, free-text status, no security_incident, no open_bucket or opened_at and no record_version. This job upgrades them all to the end-state shape; it follows the shared legacy backfill rule set in decisions/incident-management.md (Migration).

WHAT IT DOES
- Reads the whole incidents table with TASK-27.5's bounded full-table read and selects the items without record_version.
- Runs each through the pure upgrade function features/incident/core/adapters/legacy_items.py (TASK-145.5.8; the same function the read bridge uses), then writes the end-state attributes and the nested reference maps (conversation, report, video_call, postmortem_meeting, external_case, source_alert, each {system, tenant, vendor_id, url}), sets open_bucket OPEN and opened_at (fixed-width ISO-8601 UTC of the legacy created_at) for incidents not Closed, and stamps record_version 1, in one guarded RecordStore.update per item (guarded on record_version absent), so reruns are no-ops and a concurrent writer wins.
- RECORD_VERSION and OPEN_BUCKET come from core/store.py (TASK-145.5.4). opened_at and every stored time use the stored-time formatter format_stored_time in core/adapters/incident_items.py, added by TASK-145.5.8.
- Legacy attributes are kept on the item; TASK-145.13 leaves them in place (no strip pass). channel_id stays as the by_channel key.
- Status matches the five IncidentStatus values ignoring case and surrounding whitespace (production: 30 `closed` and 1 `reviewed` lowercase of 323 items). Any other value fails the run before apply writes anything, with the list of incident ids and stored values, for a manual fix in the table.
- A missing legacy security flag becomes security_incident false.

RUNNER (the shared runner pattern, decisions/incident-management.md Migration)
- An in-app leased Tier-2 job registered by the incident.response plugin (lease_ttl from its own settings), reached through the ServiceScopeOpener (TASK-145.5.2); the Slack tenant is checked through the host's TenantVerifier (contracts/workplace).
- A mode setting: off (default, the job is not registered), dry_run, apply.
- One structured report event per run with counts (scanned, already_upgraded, to_upgrade, upgraded, guard_lost, unmatched_status, pending).
- No bin script or management command: none can run in production (no ECS Exec, no RunTask).

TIMING
- Run per environment, dry run then apply, after TASK-145.8 deploys (the modal writers are the last legacy writers apart from the sheet import) and before TASK-145.9 merges (the stale-channel nudge is the first reader of the open index).
- Run again, dry run then apply, after TASK-145.12 removes the Google Sheet import (create_missing_incidents), which creates legacy items until then.
- TASK-145.13 deletes the job and legacy_items.py once a production run reports nothing pending.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The job ships with upgrade_mode off ([incident_response] upgrade_mode = "off" in base.toml, the default; the job is not registered); dry_run reports the counts and writes nothing; apply upgrades every item without record_version through legacy_items.py to the end-state attributes and reference maps and stamps record_version 1 (tested against InMemoryRecordStore over each legacy item shape) [TASK-145.5.7.2, .3]
- [ ] #2 Incidents not Closed get open_bucket OPEN and opened_at; Closed incidents get neither; a missing legacy security flag is written as security_incident false [TASK-145.5.7.2]
- [ ] #3 Every write is a guarded RecordStore.update (record_version absent plus every scalar attribute the bridge read, at its read value), so reruns change nothing and a concurrent writer wins (guard_lost counted); legacy attributes stay on the item [TASK-145.5.7.2]
- [ ] #4 A status outside the five IncidentStatus values (ignoring case and surrounding whitespace) or another unreadable field fails the run before any apply write, reporting the incident ids with the stored value (status) or the field; dropped optional values are reported with id and field and do not block apply [TASK-145.5.7.2]
- [ ] #5 One structured report event per run carries the counts; the run procedure (per environment, dry run then apply, after TASK-145.8 deploys and again after TASK-145.12) and the removal owner (TASK-145.13) are recorded in features/incident/README.md; running it is a precondition of TASK-145.9, not of this task [TASK-145.5.7.2, .3]
- [ ] #6 The whole-table read is RecordStore.read_all with max_items from the documented incident core setting [incident_core] full_read_max_items (features/incident/common/settings.py, default 10000, declared in app/config/base.toml); past the cap the run fails before any apply write and the report names the cap (decisions/cloud-portability.md contract 4) [TASK-145.5.7.2]
- [ ] #7 Before apply writes anything, the job asks the host TenantVerifier (auth.test judged by the unchanged TASK-157 check_slack_tenant: a configured id must match; an Enterprise org the entry does not name is a mismatch); a mismatch or a failed call fails the run with the expected and received ids, and dry_run reports the same check (decisions/workplace-systems.md rule 3) [TASK-145.5.7.1, .2]
- [ ] #8 IncidentStore.find_by_conversation logs a warning naming the stored and requested tenants for each by_channel candidate it drops for its tenant, never dropping one silently (decisions/incident-management.md, Stored form) [TASK-145.5.7.2]
- [ ] #9 The job is registered by the incident.response plugin through BackgroundJobRegistry at lifespan startup (never at import), as an interval job under a lease whose TTL is upgrade_lease_ttl_seconds from the plugin's settings (lease_ttl on the registry), and opens one ServiceScopeOpener scope per run; with upgrade_mode off nothing is registered [TASK-145.5.7.1, .3]
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
COORDINATOR PLAN (2026-11-04). Supersedes the 2026-11-04 slice A/B plan. Decisions D1-D10 approved by the human 2026-11-04 (see comment). STATUS: awaiting human review of the breakdown (checkpoint #1) and of each subtask plan (checkpoint #2).

SLICES (each one Stack K layer, on top of #1735, one branch, one PR; order is dependency order)
1. TASK-145.5.7.1 Host tenant verifier and lease_ttl on BackgroundJobRegistry (D1, D2). ~170 prod LOC, 7 files, host only. Depends on TASK-157. Branch stack-k/task-145.5.7.1-host-tenant-verifier-and-lease. Full plan in the subtask.
2. TASK-145.5.7.2 Incident core legacy upgrade runner (full_read_max_items, D6, D7 incl. dropped, AC8). ~245 LOC, 7 files, incident core. Depends on .1. Branch stack-k/task-145.5.7.2-upgrade-runner. Plan outline in the subtask.
3. TASK-145.5.7.3 incident.response becomes a plugin and registers the job (D3, D4, D5, run procedure). ~140 LOC + ~25 README lines, 8 files. Depends on .2. Branch stack-k/task-145.5.7.3-response-registers-upgrade. Plan outline in the subtask.
This task is done when all three are Done (human) and a production dry run then apply has reported pending 0 (a precondition of TASK-145.9, not of the PRs).

DECISIONS (approved 2026-11-04)
D1 Tenant verification is host-owned: Protocol TenantVerifier in contracts/workplace/ (beside ConfiguredSystems); host implementation in server/ calls auth.test via the integrations/slack client factory + classify_slack_error and judges with the UNCHANGED check_slack_tenant/TenantMismatch (server/slack/tenant_guard.py:40,49, #1817 merged); registered in the svcs registry beside ConfiguredSystems (server/services.py:62-66 CORE_SERVICES). Only Slack now; Google returns unsupported. No integrations/slack/tenant.py; vendor package shape unchanged. [.1]
D2 lease_ttl: timedelta | None = None on register_interval/register_daily (contracts/scheduler/registry.py:22,31; jobs/scheduled_tasks.py). None = Tier-1; a value = Tier-2 via run_if_leased(get_lease_store(ttl), "scheduler:<job_name>"). TTL from the job's own settings (reliability.md). Tier-2 slice of TASK-64 AC#1/#2. [.1]
D3 Registered by incident.response, a plugin now: entry point, contract (m) entry, hookimpls (register_background_jobs, register_requirements Slack + Google), pytest-env pin. No upgrade/ subdomain. TASK-145.13 deletes only hookimpl lines and job keys. [.3; see CONFLICT 1]
D4 "incident.response" = true in base.toml [plugins.incident_response]; false in ci.toml; no key in production.toml. The mode is the only operational switch. [.3]
D5 [incident_response] keys: upgrade_mode (off|dry_run|apply, default off; off = not registered), upgrade_interval_minutes (30), upgrade_lease_ttl_seconds. [incident_core] full_read_max_items stays in common/settings.py. [.2 for full_read_max_items, .3 for the rest]
D6 One guarded update per item: record_version absent + every scalar attribute the bridge read at its read value (None = absent) + each end-state attribute set, as read; teams not guarded; failed guard = guard_lost. [.2; see CONFLICT 2]
D7 unmatched_status (id + stored value) and unreadable (id + field) stop the run before any apply write; dry run lists all (the bridge reports only the first failing field per item); UpgradedItem.dropped reported with id and field, drops never block apply. [.2]
D8 No binding backfill here; TASK-145.7 adds it to this job later (marker 2): the per-item function stays separate and the report keys extensible. [.2]
D9 (breakdown) Three subtasks, expand-only, each revertible alone.
D10 auth.test org-token shape is an assumption, confirmed by the first production dry-run report (production [slack.tenant] has team_id only; under the unchanged verdict an org token that returns an enterprise_id would be a mismatch, check_slack_tenant at tenant_guard.py:56-58). If it mismatches, the fix is configuration (add enterprise_id), not code. [.3 README run procedure]

AC -> SUBTASK (parent ACs verified by the subtask's tests)
#1 mode off default, dry_run writes nothing, apply upgrades: .3 (mode key, off registers nothing) + .2 (dry_run/apply behavior).
#2 open_bucket/opened_at/security_incident: .2.
#3 guarded updates, guard_lost, legacy attributes stay: .2.
#4 unmatched status / unreadable stops before any write: .2.
#5 one report event; run procedure and removal owner recorded: .2 (event) + .3 (README run procedure).
#6 read_all cap from [incident_core] full_read_max_items: .2.
#7 tenant verified before apply, dry_run reports it: .1 (TenantVerifier, host verdict) + .2 (consumed, blocks apply).
#8 find_by_conversation dropped-candidate warning: .2.
#9 registered by incident.response at lifespan startup, leased, one scope per run, nothing registered with mode off: .1 (lease_ttl) + .3 (plugin, registration, scope).

OPEN ITEMS FOR THE HUMAN (found in code while planning)
CONFLICT 1 (blocks .3): contract (m) protected-plugins (pyproject.toml:440-468; allowed_importers = [], ignore_imports shrink-only) cannot list features.incident.response while app/server/configuration/host_configuration.py:22, app/modules/incident/core.py:13 and app/modules/incident/incident.py:11 import features.incident.response.settings. Proposed: entry point and contract (m) entry point at features.incident.response.plugin (hookimpls there, not in __init__.py); settings stay importable. Needs a yes/no.
CONFLICT 2 (blocks .2): D6 guards severity, the legacy times and created_at at read values, but ExpectedValue = KeyValue | bool | None, KeyValue = str | int (contracts/records/store.py:21,155) while DynamoDB returns numbers as Decimal (infrastructure/records/service.py:88). Proposed: the runner converts an integral Decimal to int; a non-integral/unguardable value makes the item unreadable (reported, stops apply). Alternative: widen ExpectedValue to Decimal.
NOTE: #1817 (TASK-157) is already merged on main (dc79aa33); implementation still waits for it to be deployed with its Slack smoke recorded (slack_tenant_mismatch = 0).
NOTE: TASK-145.12 AC3/step 3 still cite INCIDENT_CORE__FULL_READ_MAX_ITEMS (other session's task; not touched here).

GATES (each slice): ruff, targeted tests during TDD; at the end once mypy then once full pytest, sequential, from app/; make check-import-contracts; make check-settings-key-ownership for .2/.3.

BLAST RADIUS AND ROLLBACK
.1 and .2 are unregistered additions; .3 ships mode off, so no slice changes runtime behavior at merge and each reverts alone (revert .3 before .2 before .1 if several). The only data-writing moment is a later configuration change to dry_run then apply, writing additive attributes only (legacy attributes stay), guarded per item, so a mistaken apply never destroys legacy data. Production cannot run scripts: the report event is the only evidence; run per environment, dry run then apply, after TASK-145.8 deploys and again after TASK-145.12; TASK-145.9 merges only after a production report shows pending 0; TASK-145.13 removes the hookimpl lines and job keys.

SCENARIO AND CARDINALITY EVIDENCE (domain-model-evolution, approved 2026-11-04). Entity: the incident record, legacy item -> end-state shape.
| Relationship | Domain permits | Legacy holds | Upgrade writes |
| --- | --- | --- | --- |
| products per incident | 0 or 1 (one product's response; several products coordinate through engagements) | teams: a Drive folder name list, not a product | product unset; teams kept as a legacy attribute; no engagement inferred (D33) |
| conversations per incident | 1 now; many working-surface bindings later | channel_id | one conversation reference with the verified Slack tenant; TASK-145.7 adds the binding step (marker 2) |
| tenants per system | 1, verified | none stored | the tenant TenantVerifier confirms (auth.test) |
| report, video call | 0 or 1 each | report_url, meet_url | references when mappable, else dropped and counted |
| each of the five roles | 0 or 1 | incident_commander, operations_lead | as stored |
| action items | 0..many (TASK-147.2 core store) | none (postmortem document) | nothing |
| root / workstream links | absent = standalone | none | nothing (TASK-165.5 decides) |
| visibility | security flag yes/no; privacy and embargo later | security_incident, often absent | missing = no; no privacy or embargo inferred |
Contrasting scenarios for TASK-145.5.7.2 tests: (1) happy path: a single-team Closed incident with every field mappable upgrades with no open index and product unset; (2) most likely to break: an open security incident listing several teams, lowercase status, no stored security flag and an integral Decimal number in a guarded field upgrades with open_bucket and opened_at, security_incident false, product unset, teams kept, and the guard values normalised; a concurrent edit to any guarded field between read and write is guard_lost.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-15: scope widened from the open-index reconcile to the single incident legacy upgrade job (human, Stack K layer 5 planning). Needs re-planning at pickup, with a size-gate re-check then.

2026-10-20 (SLACK_TEAM_ID review): this job is the first writer to persist tenants without a request, so it verifies the configured tenant with auth.test before apply (AC7) and owns the lookup warning (AC8). Depends on TASK-157 (inbound tenant guard).

2026-11-04: D10 settled by TASK-157's production smoke (deploy dc79aa33, task-definition :78): /sre help plus a button or modal answered with slack_tenant_mismatch = 0 under the team_id-only [slack.tenant] entry, so no enterprise id arrives inbound and the host TenantVerifier (145.5.7.1) can reuse check_slack_tenant unchanged. 145.5.7.1 implementation unblocked.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-03T19:00:00Z

---

Coordinated incidents target-shape note (doc-11 E1): extend the verified legacy upgrade so it writes one working-surface binding per legacy incident item. Keep the migration idempotent and do not contract the old lookup until the backfill is verified.

---

created: 2026-11-04T00:11:00Z

---

Planning 2026-11-04. (1) AC wording changes, human to confirm: #1 names the mode key [incident_upgrade] mode; #6 now names the files key [incident_core] full_read_max_items (INCIDENT_CORE__FULL_READ_MAX_ITEMS is not an existing setting and is not the documented form after TASK-111, decisions/configuration.md); #7 now says same verdict as the TASK-157 guard (stricter than 'enterprise_id or team_id equals': a returned Enterprise org the entry does not name is a mismatch); #9 added (registration, lease, scope). (2) Binding backfill (comment #1, doc-11 row 18): NOT in this task. The bindings table, key, index and ADR amendment A1 (row 17a) do not exist and this layer's deps exclude A1; the job first runs after TASK-145.8 deploys, i.e. after TASK-145.7's re-plan creates bindings. Recommendation: TASK-145.7 (or a task it creates) adds an idempotent put_if_not_exists binding step to this job before its first production run; TASK-145.13 retires by_channel/channel_id only after a run reports no missing bindings. The plan keeps the per-item function separate so that step is additive. (3) TASK-145.12 AC3 and step 3 cite INCIDENT_CORE__FULL_READ_MAX_ITEMS and say 145.5.7 adds it: reword to [incident_core] full_read_max_items. (4) Size gate trips as one PR; two-slice decomposition proposed in the plan, awaiting approval, no subtasks created. (5) Implementation waits for TASK-157 merged and deployed with its smoke recorded.

---

created: 2026-11-04T14:06:00Z

---

2026-11-04: the human approved decisions D1-D10 (host-owned TenantVerifier; lease_ttl on the registry; incident.response as plugin; enablement in base/ci, mode as the only switch; keys in [incident_response] with full_read_max_items in [incident_core]; D6 write guard; D7 unreadable/dropped reporting; D8 no binding backfill here; D10 auth.test org-token shape as an assumption confirmed by the first production dry run) and the decomposition into TASK-145.5.7.1, .2 and .3 (one Stack K layer each). Parent ACs #1, #6, #7, #9 reworded to the decisions; each AC is verified by the subtask named in its text. Two code conflicts need a human answer before the dependent slice starts: CONFLICT 1 (contract (m) vs importers of response.settings, blocks .3) and CONFLICT 2 (ExpectedValue has no Decimal, blocks .2); see the plan.

---

created: 2026-11-04T14:18:00Z

---

2026-11-04 (human approved): OQ11 (entry module features.incident.response.plugin, contract (m) protects that module) and OQ12 (integral Decimal guarded as int, non-integral unreadable, ExpectedValue not widened) approved; the TASK-145.5.7.1 plan approved.

---

created: 2026-11-04T17:26:00Z

---

2026-11-04 (human approved, coordinated-incidents reconciliation): R1 (legacy teams not mapped to product), the revised R2/R3 (product stays on the record, optional, a product-catalogue id from TASK-165.1; a product is not a team; ADR amended) and R4 option C (ProductCatalog built with the catalogue in TASK-165.1, never over Drive folders) approved; the scenario and cardinality evidence is appended to the plan.

---
<!-- COMMENTS:END -->
