---
id: TASK-145.7.12
title: Legacy upgrade job maps the report's Drive roles into the record
status: Done
assignee: []
created_date: '2026-11-16T19:34:00Z'
updated_date: '2026-11-20T22:06:00Z'
labels:
  - incident
  - migration
dependencies:
  - TASK-145.8.5.1
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.7
priority: medium
type: feature
ordinal: 526000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L side PR (doc-11 row 18.L7c, before 18.L8). Created 2026-11-16 (human, TASK-145.8.5 OQ7): legacy roles live only in the report's Drive properties ic_id/ol_id (no legacy writer sets the item's incident_commander/operations_lead), so the backfill reads them through TASK-145.8.5.1's legacy-only core adapter and the shared per-item upgrade plan maps them as optional values (Migration rules 2 and 7) on items with no role on the record. Must merge before the job's apply (TASK-145.7.8). TASK-145.13 deletes it with the bridge. Plan in full at pickup.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The job reads each item's report Drive properties through the legacy roles adapter and the shared upgrade plan sets the record's incident commander and operations lead from them when the item holds no role; a missing report or unreadable properties is counted as dropped (rule 7) and never fails the run
- [x] #2 The run report counts roles mapped and dropped per item; a rerun changes nothing: an item whose record holds a role is never read or written (the roles-absent guard, Migration rule 4)
- [x] #3 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN (awaiting human approval). Planned against main e5b57b29 (#1865). Doc-11 row 18.L7c; Stack L side PR on its own branch task-145.7.12-job-drive-roles from main (doc-16 L7c). Waits: 145.8.5.1 merged (#1862, 557b20ef).

Goal
The legacy upgrade job reads each roleless item's report Drive properties ic_id/ol_id through the existing LegacyRolesReader (core/adapters/legacy_roles.py, the one mapping the read bridge already uses: Migration rule 2) and writes them to the record's incident_commander/operations_lead in a guarded update. After a production run reports nothing pending, TASK-145.13 can delete the bridge (LegacyRolesReader, read_incident_roles, the adapter and this step).

Findings that shape the design (main e5b57b29)
F1. The store guards every field write on record_version == RECORD_VERSION (store.py:537, 565, 661, 678, 719), and create stamps RECORD_VERSION (incident_items.py:166). Raising RECORD_VERSION to 3 would turn every item at 2 into an upgrade-on-write case, but plan_item_upgrade is pure and cannot read Drive. Rejected: no marker bump (OQ1).
F2. Items already at 2 lack roles: since L6b (#1859) and L7a.1 (#1862) deployed, upgrade-on-write raises legacy items to 2 through set_status/update_fields without Drive roles. The job skips items at 2 today (item_upgrade.py:117), so a backfill keyed on the marker would miss them, and they would lose their roles when TASK-145.13 deletes the bridge (OQ2).
F3. read_incident_roles (core/api.py:522) bridges only when the record holds none of the five roles and the report is Google. The backfill uses the same condition, so the bridge and the backfill agree on every item.
F4. LegacyRolesReader is async; LegacyUpgrade.run is sync and runs on the scheduler thread (Callable[[], None], contracts/scheduler/registry.py). Precedent: asyncio.run at the sync edge (capabilities/oncall/entrypoints/slack.py:76, comms entrypoints; outbound-clients.md async-port rule) (OQ4).
F5. upgrade_mode is "off" in base.toml:225 and no environment overrides it, so the merge is dark. 145.7.8 (L8) switches dry_run, then apply.

Design
1. core/adapters/item_upgrade.py (pure, no I/O):
   - roles_report(item, tenants) -> ReportReference | NoRolesSource | None: None when the item's end-state form (bridge output for a legacy item, the item for one at 1 or 2) holds any of the five roles. A ReportReference when it holds none and its report is Google. NoRolesSource when it holds none and has no Google report.
   - with_legacy_roles(item, plan: ItemUpgrade | None, roles) -> ItemUpgrade: adds SetAttribute(incident_commander/operations_lead) for each role read, before the version marker (marker last), and guards all five role attributes absent (None) together with the guards the plan already holds. For an item at RECORD_VERSION (plan None) it returns a roles-only ItemUpgrade: from_version=RECORD_VERSION, binding None, changes = the roles, expected = record_version at 2 plus the five roles None. ItemUpgrade gains roles: tuple[IncidentRole, ...] = () so the report can count them.
   - plan_item_upgrade is unchanged, so upgrade-on-write still never reads Drive.
2. core/legacy_upgrade.py: LegacyUpgrade takes read_roles: Callable[[ReportReference], OperationResult[Mapping[IncidentRole, str]]] (keyword). After classification it calls read_roles once, sequentially, for every plannable item (no blocker) and every item at 2 whose roles_report is a ReportReference:
   - success with roles -> with_legacy_roles;
   - success, empty -> roles_none;
   - NOT_FOUND or PERMANENT_ERROR, or NoRolesSource -> dropped (incident_id, "roles"): Migration rule 7, never fails the run;
   - TRANSIENT_ERROR (rate limit included) or UNAUTHORIZED (an access the human can restore) -> roles_unread (incident id with the status), counted in pending and read again next run, never fails the run (OQ3);
   - an exception the classifier does not know (GoogleCredentialsRefused raised outside HttpError, an unlisted status) propagates to the scheduler's safe_run boundary. The reads all happen before the first write, so the run fails with nothing written (reliability.md: background jobs).
   Reads run in dry run and apply alike, so the L8 dry run shows the counts. The apply write loop is unchanged: binding first when present, then one guarded update. A roles-only plan has no binding and is not counted in binding_skipped. A lost guard (a concurrent set_roles) is guard_lost; the next run re-reads, sees the role and skips the item (outbound-clients.md 2026-11-17: the recompute is the next run's re-read, not a retry).
3. UpgradeReport and the report event gain: roles_to_map (items planned with at least one role), roles_mapped (written, apply), roles_none, roles_unread (ids). The "dropped" list also carries (id, "roles"). pending = shape plans not written + roles-only plans not written + len(roles_unread). The event never logs a role holder.
4. core/api.py build_legacy_upgrade(..., read_roles) passes it through. response/legacy_upgrade_job.py, the sync job edge, opens one asyncio.Runner per run, resolves get_legacy_roles_reader() and passes read_roles=lambda report: runner.run(legacy.read(report)): one event loop and one context per run, as oncall_sync's one asyncio.run per run (packages/oncall_sync/__init__.py:28-32), without making the runner async (F4, OQ4). Every new symbol is tagged TODO(TASK-145.13).
5. Docs: decisions/incident-management.md Migration paragraph (how the backfill works, rerun without a marker) plus a dated Changes line, and rule 4 gets a clause: a side-store input step guarded on the end-state attribute's absence needs no new marker value (OQ1). features/incident/README.md run procedure: the roles step, the new report keys, and a rerun reads Drive again for every roleless item (one call each). response/README.md:40 updated.

Rerun rule (AC #2)
An item whose record holds a role is never read or written. An item mapped once holds a role, so a rerun skips it. Dropped and roles_none items are read again on each run and written never, so a rerun changes nothing. Drive cost: one files.get per roleless item per run, only while upgrade_mode is not off (the L8 window and the rerun after TASK-145.12.2).

Named changes (migration.md step 4, kinds a-d; :67)
None: there is no user surface, and the job is off in every environment. The PR body says so and lists the new report keys for the L8 operator.

Blast radius and rollback
Merging deploys nothing that runs (upgrade_mode off). One git revert undoes it. After an apply, roles written to the record are end-state values that the rebuilt modal already reads; a revert of this PR leaves them, and they stay correct.

TDD (tests first, app/tests/unit/features/incident/core/ and response/)
- test_incident_core_item_upgrade_legacy_roles.py: roles_report (role present -> None; none + Google report -> reference; none + no report -> NoRolesSource; legacy and at-2 items); with_legacy_roles (legacy plan: roles before marker, five-role guards; at-2 roles-only plan; at-1 plan).
- test_incident_core_legacy_upgrade_roles.py: dry run counts roles_to_map/roles_none/dropped/roles_unread and writes nothing; apply writes the roles on legacy, at-1 and at-2 items; 404 and permanent errors are dropped and the run succeeds; transient errors are pending; a concurrent set_roles is guard_lost; a rerun reads but writes nothing; an item with a recorded role is never read (counting fake); a blocked run reads no Drive for blocked items.
- test_incident_core_legacy_upgrade_report.py: the event carries the new keys and never a holder id.
- test_incident_response_upgrade_job_run.py: the job passes the legacy reader through asyncio.run.
- tests/factories/legacy_upgrade.py: the factory takes a roles reader (InMemoryLegacyRolesReader exists, in_memory.py:819).

Size: about 150 production LOC across 4 code files plus 3 docs; one subsystem (incident core migration). Within the single-PR gate.

Gates: ruff and the targeted tests during TDD; make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams; then the full mypy, then the full pytest tests --ignore=tests/smoke, once each.

Open questions, assessed at program scope (2026-11-17; human asked for ADR, doc-11, doc-15 and doc-16 scope, prior and upcoming tasks, cited practice)

OQ1 Rerun rule for the roles step: no new marker value; the step is keyed on the roles being absent.
- ADR: incident-management.md Migration rule 3 (upgrade on write uses the same function, "so an item never carries a partial upgrade") and rule 4 (a later step raises the marker; reruns change nothing). The roles paragraph (2026-11-16, TASK-145.8.5.1) makes the Drive properties an upgrade input but does not say how that input meets rules 3 and 4.
- CONFLICT, already live: since #1859 upgrade-on-write stamps marker 2 on legacy items without their Drive roles. That counts as a partial upgrade under rule 3, and the read bridge hides it. A pure function cannot read a side store, so upgrade on write can never carry this input.
- Prior: TASK-145.7.4 raised the marker 1 -> 2 for bindings, a pure step derived from the item. The store checks record_version == RECORD_VERSION at 5 sites (F1). TASK-145.8.5 OQ7 put the roles input "in the shared per-item plan" (kept: with_legacy_roles lives in item_upgrade.py).
- Upcoming: TASK-154 (status values migration under "the record_version marker") and TASK-83.11 (person-reference migrations under "version marker"; incident role holders are Slack user ids). A directory lookup is a side-store input exactly like this one. TASK-145.13 deletes the bridge on "nothing pending". doc-15 has no incident upgrade step.
- Marker 3 rejected:
  (a) the 5 store sites refuse items at 3, so a revert of this PR after the apply breaks every write to a backfilled incident. That fails rule 1's revert-target test unless a separate expand PR widens the store first.
  (b) Upgrade on write could still only stamp 2, so the marker would no longer mean "upgraded".
  (c) It adds a live version: MongoDB's schema-versioning guidance asks to keep the number of live versions minimal (https://www.mongodb.com/docs/manual/data-modeling/design-patterns/data-versioning/schema-versioning/).
- Practice for a field filled from elsewhere: select and guard on the field's absence, so the work is idempotent and resumable (GitLab batched background migrations are idempotent and resumable: https://docs.gitlab.com/ee/development/database/batched_background_migrations.html; DynamoDB conditional writes on attribute absence: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html). A backfill also ignores rows the live writers already filled (https://will-keleher.com/posts/backfills-should-fail-in-minutes-not-days/).
- Proposed ADR fix (Migration, rules 3 and 4 plus a Changes line): the marker versions the item's shape and its pure upgrade. An input held in a side store is not marker-versioned:
  - the batch runner alone maps it, never upgrade on write;
  - it selects and guards on the end-state attribute's absence, so a rerun reads again and writes nothing;
  - its report counts are its own "pending";
  - a read bridge covers it until that report shows nothing pending.
  An item at the marker without that input is therefore not a partial upgrade.
- Scope changes: AC #2 reworded to "a rerun changes nothing: an item whose record holds a role is never read or written (the roles-absent guard, Migration rule 4)". After approval, comments on TASK-154 and TASK-83.11: a pure step raises the marker only after its own expand PR widens the store's record_version equality checks (rollback); a side-store step (e.g. a directory lookup for person references) follows the absence-keyed form.

OQ2 Include items already at marker 2.
- ADR: rule 1 (backfill before contract); the TASK-145.8.5 OQ7 ruling ("switching reads without a backfill shows empty roles for every existing incident").
- Prior: TASK-145.8.1 upgrade on write, live since #1859 and #1862.
- Upcoming: TASK-145.13 deletes the bridge, so items at 2 must be covered or they lose their roles.
- No gap once OQ1 is ruled. Recommended.

OQ3 Classifying a failed Drive read.
- ADR: rule 7 ("an optional value it cannot map" is dropped and counted); reliability.md:28 (consumers of TRANSIENT_ERROR decide whether to retry, honoring retry_after); outbound-clients.md (no hand-rolled retry loops; SDK retries stay in the SDK); reliability.md:32 (a job lets unexpected exceptions reach the error boundary).
- Prior: the job's write_failed precedent; the README says a throttled run resumes on the next run.
- Recommended:
  - NOT_FOUND, PERMANENT_ERROR and no Google report are dropped (rule 7, AC #1);
  - TRANSIENT_ERROR and UNAUTHORIZED are pending (roles_unread) and read again next run, never in-run;
  - unknown exceptions propagate before any write.
- No gap. Because the step has no marker, a dropped item is read again on every run: a report restored later still gets mapped.

OQ4 Calling the async reader from the sync runner.
- ADR: outbound-clients.md "Async ports over blocking SDKs" (a Protocol consumed from async code is async; adapters offload) and its Migration list "sync ports with async consumers ... until TASK-25".
- GAP: the reverse case, an async port called from a sync job body, is not ruled.
- Prior: oncall_sync bridges its sync job to the async service with one asyncio.run per run (packages/oncall_sync/__init__.py:28-32); the Bolt entry points call asyncio.run at the sync edge (TASK-145.8.5 rulings).
- Upcoming: TASK-25 makes RecordStore async, after which LegacyUpgrade could become async; TASK-145.13 likely deletes the job first.
- Practice: asyncio.Runner (3.11+) runs several top-level coroutines in one loop and one contextvars context; asyncio.run is meant to be called once (https://docs.python.org/3.14/library/asyncio-runner.html).
- Recommended: one asyncio.Runner per run at the job edge (response/legacy_upgrade_job.py); LegacyUpgrade stays sync. Making it async now would rewrite 49 call sites in 10 test files, a mechanical refactor mixed with a behaviour change that the size gate forbids.
- Proposed ADR line (outbound-clients.md, Migration list plus Changes): a sync job body that consumes an async port opens one asyncio.Runner per run at the job edge, never per call and never inside core, until the job's own ports are async (TASK-25).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-17: plan APPROVED by the human as recommended (OQ1-OQ4, program-scope reassessment): no marker bump, absence-keyed batch-only roles step; items at version 2 included; NOT_FOUND/PERMANENT/no Google report dropped, TRANSIENT/UNAUTHORIZED pending, unknown exceptions propagate before any write; one asyncio.Runner per run at the job edge. AC #2 reword, the Migration rules 3/4 amendment, the outbound-clients.md line and the TASK-154/TASK-83.11 comments ride with the implementation.

2026-11-17 (human): the TASK-145.7.8 dry run goes first, and the apply no longer waits on this task: its roles step also covers items the apply raises to version 2. This task merges after the apply and maps the roles in a rerun (dry_run, then apply), before TASK-145.13.

2026-11-17 (TASK-145.7.8 OQ4, human approved): conditional scope. If a production dry-run report drops 10 or more fields in one run (the warning alarm's 10 per minute), this task also gives the runner a silent drop sink: in a batch run the bridge's drops go only into the report's dropped list, and the read path keeps its incident_legacy_field_dropped warning. It also adds a clause to incident-management.md Migration rule 3: a batch run reports per-item outcomes in its report, not one log event per item. Decided at implementation from the recorded TASK-145.7.8 dry-run report.

2026-11-17: the TASK-145.7.8 production dry run dropped no fields (dropped []), so OQ4's conditional drop sink and Migration rule 3 clause are not needed; reassess only if a later run drops 10 or more.

2026-11-18: implementation started on task-145.7.12-job-drive-roles from main 203aeea1 (human-created branch); TASK-176 asked (unchanged).

2026-11-18: implemented (TDD) per the approved plan on task-145.7.12-job-drive-roles from main 203aeea1.
- core/adapters/item_upgrade.py: roles_report(item, plan) (the end-state form is the item overlaid with its plan's changes, so the bridge runs once per item and logs its drops once; None when any of the five roles is non-blank text, as read_incident_roles decides, or the item is above RECORD_VERSION; RolesUnmappable when there is no Google report or a stored role no guard can hold) and with_legacy_roles (roles before the marker; roles-only plan at RECORD_VERSION). ItemUpgrade.roles added. Deviation from the plan text, same intent: the five roles are guarded at their read value (None when absent, as planned), so an item with a blank role, which the read bridge treats as roleless, is mapped instead of being guard_lost on every run.
- core/legacy_upgrade.py: RolesRead (sync), LegacyUpgrade(read_roles=...), _map_roles before any write; report keys roles_to_map, roles_mapped, roles_none, roles_unread; dropped carries (id, roles); pending adds roles-only plans not written and roles_unread.
- core/api.py build_legacy_upgrade(..., *, read_roles); response/legacy_upgrade_job.py: one asyncio.Runner per run, providers.legacy_roles_reader() (the provider substitution seam the roles entry point uses).
- Docs: incident-management.md Migration rules 3/4 (side-store inputs are not marker-versioned; a marker raise needs its own expand PR), the roles paragraph and a 2026-11-18 Changes line; outbound-clients.md Migration list and Changes line (asyncio.Runner at a sync job edge); features/incident/README.md run procedure (roles step, report keys, removal), response/README.md roles line. Comments on TASK-154 and TASK-83.11.
- Tests: test_incident_core_item_upgrade_legacy_roles.py, test_incident_core_legacy_upgrade_roles.py (new); report, builder and job-run tests extended; tests/factories/legacy_upgrade.py takes roles or read_roles.
Gates (from app/): ruff check . All checks passed; make check-import-contracts 14 kept 0 broken; check-settings-key-ownership OK; check-package-shape OK (3 baselined); check-test-seams OK (47/12 baselined); mypy Found 40 errors in 13 files (baseline, none in touched files; one arg-type error in legacy_upgrade.py found and fixed before the counted run); pytest tests --ignore=tests/smoke 7680 passed.
AC #1, #2, #3 checked. Merges after the TASK-145.7.8 apply; the rerun (dry_run then apply) maps the roles before TASK-145.13. Stays In Progress; commit, PR and merge are the human's.

2026-11-20: closed by the agent: PR #1869 merged 2026-11-18 (98918309); all ACs checked.
<!-- SECTION:NOTES:END -->
