---
id: TASK-145.5.10
title: >-
  IncidentStore builder: the store from a resolved RecordStore, the incident
  core settings and the configured tenants
status: Done
assignee: []
created_date: '2026-10-19 15:25'
updated_date: '2026-10-19 19:26'
labels:
  - incident
  - features
dependencies:
  - TASK-145.5.9
  - TASK-145.5.8
references:
  - decisions/incident-management.md
  - decisions/dependency-injection.md
  - decisions/workplace-systems.md
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 400000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 8 of Stack K (handoff doc-13), split out of TASK-145.5.5 (human, 2026-10-19). Added beside the legacy lookup and unused until the TASK-145.5.5 cutover, so no behaviour change.

THIS SLICE
- core/api.py: a builder that takes a resolved RecordStore and the configured-systems read (TASK-145.5.9) and returns the IncidentStore: incidents_table from the incident core settings table name, and the tenants mapping (system to tenant id) for the legacy item bridge (TASK-145.5.8) taken from the read. A plain function the entry point calls inside its service scope; no lru_cache provider (decisions/dependency-injection.md).
- The builder does not read the new-incident policy (human, 2026-10-19): the policy is resolved only on the path that creates a new incident (TASK-145.7), so lookups and updates of existing incidents never depend on it.
- A legacy item without record_version reads through the bridge with the configured tenants, tested end to end over the in-memory RecordStore.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 core/api.py builds the IncidentStore from a resolved RecordStore, the incident core table name and the tenants mapping taken from the configured-systems read; no lru_cache provider
- [x] #2 The builder does not read INCIDENT_CORE__NEW_INCIDENT_SYSTEM
- [x] #3 A legacy item without record_version reads through the bridge with the configured tenants, tested end to end over the in-memory RecordStore; a system missing from the read leaves its tenant out of the mapping (tested)
- [x] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
SCOPE
Add build_incident_store to features/incident/core/api.py, beside the legacy lookup and unused until the TASK-145.5.5 cutover. No behaviour change. ACs are current (checked against TASK-145.5.9 merged-in-stack code and the TASK-145.5.5 cutover text); no AC edits.

GROUNDING (call sites)
- features/incident/core/store.py:43 incidents_table(name) -> RecordTable; store.py:91-101 RecordIncidentStore(records, table, tenants: Mapping[WorkplaceSystem, str]); store.py:56 IncidentStore Protocol.
- contracts/workplace/configured_systems.py: ConfiguredSystems.tenants() -> Mapping[WorkplaceSystem, str]; host impl server/configured_systems.py (StaticConfiguredSystems); registered as a core service at server/services.py:47.
- features/incident/common/settings.py:29 INCIDENTS_TABLE; :36 NEW_INCIDENT_SYSTEM (must stay unread); :60 get_incident_core_settings (lru_cache settings singleton, unchanged).
- features/incident/core/api.py: IncidentStore already imported (line ~39) and exported in __all__; lru_cache providers at api.py ~194-218 are the legacy ones the cutover deletes; this slice adds none.
- Dependents: TASK-145.5.5 entry points call build_incident_store(records, systems, settings) inside their ServiceScopeOpener scope after resolving RecordStore and ConfiguredSystems (decisions/dependency-injection.md: entry points resolve, features build from resolved contracts via core/api.py provider functions; no lru_cache provider across layers).

STEPS
1. features/incident/core/api.py (~15 prod LOC): add plain function
   def build_incident_store(records: RecordStore, systems: ConfiguredSystems, settings: IncidentCoreSettings) -> IncidentStore
   returning RecordIncidentStore(records, incidents_table(settings.INCIDENTS_TABLE), dict(systems.tenants())). The mapping is copied so a later change in the read cannot alter the store. Reads only INCIDENTS_TABLE: not NEW_INCIDENT_SYSTEM, no get_incident_core_settings() call inside (the caller passes the slice, so the function has no hidden global). Imports at module top: RecordStore (contracts.records), ConfiguredSystems (contracts.workplace), IncidentCoreSettings (features.incident.common.settings), RecordIncidentStore and incidents_table (core.store). Add "build_incident_store" to __all__; update the module docstring (the store is now built by this function; production calls it from TASK-145.5.5). Docstring states the policy is not read and why (resolved only on the declare path, TASK-145.7).
2. tests/unit/features/incident/core/test_incident_core_api_surface.py: add "build_incident_store" to the exact __all__ list (edited in place; legacy-named lookup/reader entries stay until the cutover).
3. New tests/unit/features/incident/core/test_incident_core_api_build_incident_store.py (InMemoryRecordStore from infrastructure.records.in_memory, a small local ConfiguredSystems fake, IncidentCoreSettings built with explicit fields; top-level imports only, docstrings state behaviour).

AC -> STEP -> TEST
- AC1 (builder from RecordStore, settings table name, tenants from the read; no lru_cache provider): step 1. Tests: test_build_uses_the_configured_incidents_table (settings INCIDENTS_TABLE=custom name; item put into incidents_table(custom) is readable by get, item in the default table is NOT_FOUND); test_build_returns_an_incident_store (isinstance IncidentStore); test_builder_is_a_plain_function (no cache_clear attribute / not functools-wrapped; two calls give distinct stores).
- AC2 (does not read NEW_INCIDENT_SYSTEM): step 1. Tests: test_build_ignores_the_new_incident_policy parametrized over NEW_INCIDENT_SYSTEM None, SLACK, GOOGLE (including a system absent from the read): get and find_by_conversation results are identical for all three; plus a source-level assertion via inspect.getsource that build_incident_store does not mention NEW_INCIDENT_SYSTEM.
- AC3 (legacy item reads through bridge with configured tenants, end to end over in-memory RecordStore; missing system leaves tenant out): steps 1, 3. Tests: test_legacy_item_without_record_version_reads_with_the_configured_tenants (put legacy item, get returns Incident whose conversation has system slack and tenant from the read; find_by_conversation with the slack ConversationReference finds it); test_system_missing_from_the_read_leaves_its_tenant_out (read has only Google: a legacy Slack item is not matched by a Slack reference with the old tenant / the bridge result matches how legacy_items handles an absent tenant, asserted against the observed classification in test_incident_core_incident_store_legacy_items.py); test_tenants_are_copied_at_build (mutating the fake read's mapping after build does not change the reads).
- AC4 (gates): ruff check, mypy with no new errors in touched files, lint-imports, pytest tests --ignore=tests/smoke; step 2 keeps the surface test green.

TEST MATRIX
happy: table name from settings, legacy read end to end, end-state item read. boundary: tenants copied; empty read (no systems). failure: system missing from the read; item in another table is NOT_FOUND. policy: three NEW_INCIDENT_SYSTEM values give identical behaviour. Files: test_incident_core_api_build_incident_store.py (new), test_incident_core_api_surface.py (edited).

SIZE ESTIMATE / GATE
1 prod file, ~15 changed prod LOC (~25 with docstring), 1 subsystem, no mechanical refactor mixed in, single revert safe. Gate passes; no decomposition.

ASSUMPTIONS AND VERIFICATION
- Layer 7 (TASK-145.5.9) exports ConfiguredSystems from contracts.workplace on this branch: verify with rg 'ConfiguredSystems' app/contracts.
- Passing the IncidentCoreSettings slice (not the bare table name) is the shape the cutover entry points can call with get_incident_core_settings() from their scope: verify against TASK-145.5.5 planning that no entry point needs another signature.
- Feature code may import contracts.workplace and features.incident.common.settings from core/api.py: verify with cd app && uv run lint-imports.
- RecordIncidentStore does not read the tenants mapping lazily in a way a copy would break: verify in store.py (_end_state / upgrade_legacy_item call) while writing the copy test.
- Pre-existing repo-wide mypy errors outside touched files are ignored; record 0 in touched files.

BLAST RADIUS / ROLLBACK
Nothing calls the function in production until TASK-145.5.5, so a bug cannot affect runtime; worst case is a failing unit test or import-linter contract. One git revert restores the prior state. No ordering constraints, no env or terraform change.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-10-19 (option A, human-approved): build_incident_store(records, systems, settings) in features/incident/core/api.py returns RecordIncidentStore over incidents_table(settings.INCIDENTS_TABLE) with dict(systems.tenants()); plain function, no lru_cache, never reads NEW_INCIDENT_SYSTEM; exported in __all__ and the module docstring updated. No caller yet: TASK-145.5.5 adds the entry-point calls. Prod diff: 1 file, 20 insertions, 3 deletions (with docstring).
Tests: new tests/unit/features/incident/core/test_incident_core_api_build_incident_store.py (8 cases: table name from settings, plain function, policy None/SLACK/GOOGLE identical, source never names the policy, legacy item end to end with configured tenants, Slack missing from the read makes the legacy Slack item INCIDENT_RECORD_UNREADABLE because the bridge has no tenant, tenants copied at build); api surface test lists build_incident_store.
Gates (from app/): ruff check . -> All checks passed; ruff format applied to api.py; lint-imports -> 12 kept, 0 broken; mypy -> 48 errors in 19 files repo-wide, 0 in touched files; pytest tests --ignore=tests/smoke -> 5373 passed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-19 19:15
---
Plan approved by the human 2026-10-19 (option A: the builder takes the IncidentCoreSettings slice).
---
<!-- COMMENTS:END -->
