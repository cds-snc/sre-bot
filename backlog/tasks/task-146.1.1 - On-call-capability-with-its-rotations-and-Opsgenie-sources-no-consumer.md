---
id: TASK-146.1.1
title: On-call capability with its rotations and Opsgenie sources, no consumer
status: In Progress
assignee: []
created_date: '2026-11-16T17:06:00Z'
updated_date: '2026-11-16T17:37:00Z'
labels:
  - oncall
  - capabilities
dependencies:
  - TASK-25.6
  - TASK-114.2
parent_task_id: TASK-146.1
priority: medium
type: feature
ordinal: 523000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice A+B of TASK-146.1 (human, 2026-11-16: one PR with a size-gate exception, rule 1 only: ~16 production files / ~610 LOC, one subsystem, nothing calls it yet). Gates TASK-145.7.9. Side PR from an up-to-date main (doc-11 row 18d).

Builds app/capabilities/oncall/ with the package generator: api.py (OnCallLookup, the domain types, the provider and a sync config-time accessor), domain and service, the self-managed rotations source, the Opsgenie source over the TASK-25.6 async client, an in-memory fake, and a protected import contract on integrations.opsgenie. packages/user_rotations and packages/oncall_sync are untouched; TASK-146.1.2 moves them onto it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 capabilities/oncall/api.py exposes OnCallLookup (async def, each method returning OperationResult), ScheduleReference, Schedule, Rotation, Shift, OnCallPerson, Account, the system constants, the provider and a sync config-time accessor; the entry point and protected module is capabilities.oncall.plugin and nothing else in the package is imported from outside
- [x] #2 The source is selected by ScheduleReference.system: an unknown system returns PERMANENT_ERROR ADAPTER_NOT_FOUND, and the in-memory fake covers both systems
- [x] #3 The Opsgenie source awaits build_opsgenie_client directly (no to_thread) and classifies with classify_opsgenie_error; with no tenant it returns CONFIG_NOT_CONFIGURED and makes no call; a body of the wrong shape returns INVALID_RESPONSE; get_schedule returns UNSUPPORTED_OPERATION; unexpected exceptions propagate
- [x] #4 OnCallPerson carries an email and an Account(platform, tenant, account_id) shaped as TASK-83.4 specifies, at least one set; no platform-named field appears in api.py
- [x] #5 A protected contract on integrations.opsgenie allows server and capabilities.oncall.adapters.opsgenie; jobs.scheduled_tasks (TASK-127), modules.incident.on_call (TASK-145.7.10) and packages.oncall_sync.adapters.opsgenie (TASK-146.2) are shrink-only ignores naming their removing task
- [x] #6 With no Opsgenie settings the capability registers and the self-managed source answers (boot test)
- [x] #7 No vocabulary from incident or oncall_sync appears in the capability; packages/user_rotations and packages/oncall_sync are unchanged
- [x] #8 decisions/oncall.md Checks names the host's settings reads as the allowed exception; the README states the classification, the consumers (incident response, oncall_sync until TASK-146.2, coordination in doc-15 E5) and Opsgenie's 2027-04-05 end date
- [x] #9 ruff, mypy, lint-imports, check-package-shape, check-settings-key-ownership, check-test-seams and pytest tests --ignore=tests/smoke pass with no new baseline entry
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN v1 (2026-11-16; approved, human: split A+B with a size-gate exception, OQ1-OQ9 rulings as in TASK-146.1 notes). Side PR on branch task-146.1.1-oncall-capability from an up-to-date main (doc-11 row 18d). Base: main 41319bcc (TASK-25.6 #1857). Gates TASK-145.7.9.

SIZE: ~16 production files, ~610 LOC, one subsystem (app/capabilities/oncall plus its pyproject/base.toml registration and one ADR line). Exception to rule 1 only (human, 2026-11-16): no mechanical move (user_rotations is untouched), no consumer, so nothing in production calls it.

DECISIONS (approved 2026-11-16)
D1 (OQ5) OnCallLookup methods are async def and return OperationResult (outbound-clients.md:37; core ports precedent features/incident/core/api.py:209). Unknown system -> PERMANENT_ERROR ADAPTER_NOT_FOUND; Opsgenie without a tenant -> CONFIG_NOT_CONFIGURED; classified vendor failures -> the classifier's status and code; unexpected exceptions propagate (outbound-clients.md:33). Consumers decide: declare invites nobody and says so (oncall.md:20), oncall_sync skips the group (packages/oncall_sync/service.py:90-95), coordination falls back to manual (doc-15:23). No OnCallSourceError type.
D2 (OQ8) OnCallPerson(email: str | None, account: Account | None), at least one set. Account(platform: str, tenant: str | None, account_id: str) shaped as TASK-83.4 specifies; TASK-83.4 moves it to capabilities/people/api.py and oncall imports it from there (plugin-architecture.md:39). Rotations source -> Account("slack", None, <member id>); Opsgenie -> email (participant name).
D3 (OQ1) Protected contract on integrations.opsgenie: allowed_importers server and capabilities.oncall.adapters.opsgenie; ignore_imports (shrink-only, each with its removing task) jobs.scheduled_tasks -> TASK-127, modules.incident.on_call -> TASK-145.7.10, packages.oncall_sync.adapters.opsgenie -> TASK-146.2 (precedents: contracts (j) and (m); import-linter 2.15 protected contract, unmatched_ignore_imports_alerting = error). oncall.md Checks reworded: "integrations.opsgenie is imported only by capabilities/oncall/adapters/opsgenie.py, besides the host's settings reads in server/".
D4 (OQ3) Hookimpls in capabilities/oncall/plugin.py; entry point oncall and the protected-plugins module are capabilities.oncall.plugin (precedent features.incident.response.plugin), so packages and features may import capabilities.oncall.api.
D5 (OQ4) No register_requirements entries: boots with no vendor settings (oncall.md Checks boot test; plugins.md:59).
D6 (OQ6) Opsgenie get_schedule returns UNSUPPORTED_OPERATION; list_schedules(opsgenie) returns an empty success (references come from consumers' configuration).
D7 (OQ7) api.configured_rotations() -> tuple[ScheduleReference, ...], sync, reads the loaded rotation files only (no network): job registration runs inside the lifespan loop (server/lifespan.py:310), so no asyncio.run there.
D8 (OQ9) The rotations source reads the existing JSON format (keys slack-usergroup-handle, slack-usergroup-name, members, rotation_type, weeks_per_shift, rotation_start; extra=forbid) and maps to neutral names (handle -> ScheduleReference.id, name -> Schedule.name). Its loader takes the directory as an argument; the default is files(capabilities.oncall)/"rotations", absent -> empty (as user_rotations/settings.py:57-60). The files themselves move in TASK-146.1.2.
D9 ScheduleReference(system: str, id: str) with constants OPSGENIE and ROTATIONS; a str, not an enum, so GoAlert (doc-15 E2) is a constant plus an adapter.

STEPS
1. make new-package ARGS="capability oncall --classification generic --consumer features.incident.response --adapters --service --interfaces" (app/Makefile:125, bin/new_package.py); it creates app/capabilities/__init__.py and bootstraps pyproject (root_packages, wheel packages, contracts b/e/g/k, entry point, protected module) and base.toml [plugins.incident_response] oncall = true (plugins.md:43). Run lint-imports straight after. No --entrypoints here (TASK-146.1.2 adds them).
2. Move the generated hookimpls to capabilities/oncall/plugin.py; point [project.entry-points.sre_bot] oncall and protected-plugins at capabilities.oncall.plugin (D4). pyproject pytest env pin PLUGINS__INCIDENT_RESPONSE gains "oncall": true. ci.toml unchanged (no requirement, stays on).
3. capabilities/oncall/api.py: ScheduleReference, Account, OnCallPerson, Shift, Rotation, Schedule (frozen dataclasses), OPSGENIE/ROTATIONS, OnCallLookup Protocol (on_call_now(reference, *, rotation=None) -> OperationResult[tuple[OnCallPerson, ...]]; get_schedule(reference, *, horizon_weeks=12) -> OperationResult[Schedule]; list_schedules(system) -> OperationResult[tuple[ScheduleReference, ...]]), get_oncall_lookup(), configured_rotations() (D7).
4. interfaces.py: private ScheduleSource Protocol (same three methods, one system). domain.py: whos_on(rotation, at) and shift windows, ported from packages/user_rotations/service.py:27-70 (weekly, weeks_per_shift, wrap-around).
5. service.py: OnCallService(OnCallLookup) holding sources by system; unknown system -> ADAPTER_NOT_FOUND with one structured warning (no secrets). providers.py: lru_cache builder wiring both sources (Opsgenie settings read lazily, so no tenant is fine).
6. adapters/rotations.py: RotationFile pydantic model (ported from packages/user_rotations/settings.py:17-45, the untrusted-file boundary) -> frozen Rotation; loader over a directory (D8); duplicate handle and invalid JSON fail at load with the same messages.
7. adapters/opsgenie.py: OpsgenieSource over build_opsgenie_client (async with) and classify_opsgenie_error. on_call_now without rotation: GET /v2/schedules/{id}/on-calls participants (parse from modules/incident/on_call.py:50-65); with rotation: /timeline (parse from packages/oncall_sync/adapters/opsgenie.py:41-95, gap -> empty success, non-user recipient -> skipped). Explicit shape checks -> INVALID_RESPONSE, never a caught KeyError. Module docstring and README: Opsgenie ends 2027-04-05 (oncall.md:18).
8. adapters/in_memory.py: InMemoryOnCallLookup(OnCallLookup) seeded per system; covers both.
9. README.md: classification generic; consumers features.incident.response; prose: packages.oncall_sync until TASK-146.2, coordination (doc-15 E5).
10. pyproject: protected contract on integrations.opsgenie (D3).
11. decisions/oncall.md: Checks line (D3); Changes entry 2026-11-xx (TASK-146.1.1: lookups return OperationResult, Account shaped as TASK-83.4, host settings reads allowed).

AC TRACEABILITY
#1 steps 2-3 -> test_oncall_api_surface.py + lint-imports. #2 steps 5, 8 -> test_oncall_service_system_dispatch.py, test_oncall_in_memory_lookup_conformance.py. #3 step 7 -> test_oncall_opsgenie_adapter_on_call.py. #4 step 3 -> test_oncall_api_surface.py (field names). #5 step 10 -> lint-imports. #6 steps 2, 5 -> tests/integration/capabilities/oncall/test_oncall_capability_boot_without_opsgenie.py. #7 -> rg guard in test_oncall_api_surface.py; git diff shows packages/ untouched. #8 steps 9, 11. #9 final gates.

TEST MATRIX (tests/unit/capabilities/oncall/, strict seam zone: Protocol fakes, httpx.MockTransport through the client factory, no patching inside capabilities/)
- test_oncall_domain_rotation_assignment.py: week 0/1, exact shift boundary, weeks_per_shift=2, wrap-around, single member, start in the future.
- test_oncall_rotations_adapter_load.py: valid minimal and custom; missing directory -> empty; duplicate handles; invalid JSON; naive timestamp; extra key forbidden; members mapped to Account("slack", None, id).
- test_oncall_service_system_dispatch.py: each system routed; unknown system -> ADAPTER_NOT_FOUND; a source error result passed through; unexpected exception propagates.
- test_oncall_opsgenie_adapter_on_call.py: one participant, several, rotation timeline current, gap -> empty, non-user recipient skipped, 5xx/timeout/connect classified, JSONDecodeError -> INVALID_RESPONSE, wrong shape -> INVALID_RESPONSE, no tenant -> CONFIG_NOT_CONFIGURED with no request, get_schedule -> UNSUPPORTED_OPERATION.
- test_oncall_in_memory_lookup_conformance.py: both systems; fake-coverage enrolment.
- test_oncall_api_surface.py: exported names; no platform-named field; no incident/oncall_sync vocabulary under capabilities/oncall.
- tests/integration/capabilities/oncall/test_oncall_capability_boot_without_opsgenie.py: lifespan boot with oncall on and no [opsgenie.tenant]; registered; the rotations source answers from a fixture directory.

ASSUMPTIONS (verify)
- The generator's capability form bootstraps capabilities/ as described (bin/package_toml.py:239-260); verify by lint-imports and check-package-shape right after step 1.
- packages -> capabilities.oncall.api passes the layers contract once the protected module is .plugin; verify with lint-imports (TASK-146.1.2 relies on it).
- The wheel includes capabilities/; verify with uv build --wheel listing.

BLAST RADIUS AND ROLLBACK
Merging deploys. The only running change is a new enabled plugin with no requirement and no acting hook; an import error aborts boot, caught by the boot test, and the ECS circuit breaker rolls back. No terraform, env var, secret or settings change. One git revert removes it.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-16: implementation started on branch task-146.1.1-oncall-capability from origin/main ac3b8f8d (#1852 merged). TASK-176 unchanged per the answer at TASK-146.1 planning start this session (#1 and #4 open, #2 waits on TASK-182).

2026-11-16 implemented (gates green). Evidence (from app/): ruff check . -> All checks passed; lint-imports -> 14 kept, 0 broken (new protected contract on integrations.opsgenie KEPT, 3 ignored imports); make check-import-contracts, check-settings-key-ownership, check-package-shape (3 baselined), check-test-seams (47/12 baselined) -> OK, no new baseline entries; bin.check_fake_coverage OK; mypy . -> 40 errors in 13 files (= baseline, none in touched files); pytest tests --ignore=tests/smoke -> 7434 passed (first run: 2 failures in test_server_plugins_entrypoint_declaration.py, whose plugin scan did not include capabilities/; fixed by adding the root, rerun green); uv build --wheel lists capabilities/oncall. Tests were written alongside the code rather than red first; a mutation check (unknown system code, the no-tenant guard) failed 5 tests and was reverted. Deviations from the plan: domain types live in domain.py and api.py re-exports them; api's two functions import providers lazily (providers -> service -> api cycle); Rotation(name, members, weeks_per_shift, start), Schedule(reference, name, rotations, shifts); the rotation argument is a rotation name, ignored by the rotations source; ScheduleSource.list_schedules takes no system. Existing test edits: test_lifespan_plugin_loading.py (oncall in the enabled set), test_server_plugins_entrypoint_declaration.py (capabilities root). Opsgenie parsing is byte-for-byte the legacy readers' (modules/incident/on_call.py, oncall_sync adapter). Stays In Progress for human review.
<!-- SECTION:NOTES:END -->
