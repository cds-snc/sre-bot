---
id: TASK-146.1
title: >-
  Build app/capabilities/oncall: schedules, rotations and who is on call now,
  with Opsgenie and self-managed sources
status: To Do
assignee: []
created_date: 2026-10-09 16:44
updated_date: '2026-11-16T17:08:00Z'
labels:
  - oncall
  - capabilities
dependencies:
  - TASK-114.2
  - TASK-25.6
references:
  - https://github.com/cds-snc/sre-bot/issues/1702
parent_task_id: TASK-146
priority: medium
type: feature
ordinal: 365000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 1 of TASK-146. decisions/oncall.md and plugin-architecture.md: a capability's public surface is api.py.

THIS SLICE
- capabilities/oncall/api.py: OnCallLookup Protocol (who is on call for a schedule reference now; the schedule's members), domain types Schedule, Rotation, Shift, OnCallPerson (a person reference as decisions/people-and-accounts.md defines it today), ScheduleReference carrying system and id, and the provider function. README states the classification (generic) and the consumers (oncall_sync, incident).
- domain.py and service.py: the self-managed rotation logic from packages/user_rotations (weekly rotation, weeks per shift, members) as the "rotations" schedule source, selected by the reference's system, never by a setting.
- adapters/opsgenie.py: the Opsgenie schedule reads from packages/oncall_sync/adapters/opsgenie.py over the TASK-25.6 client, the only importer of integrations.opsgenie; README notes the vendor's end date. adapters/rotations.py: the JSON rotation files. An in-memory fake.
- entrypoints/slack.py: user_rotations' Slack commands, renamed from platforms/ and made to call one service method each.
- Entry point and enablement key in the configuration files; packages/user_rotations is deleted and every importer rewritten (oncall_sync's user_rotations imports point at the capability's api until TASK-146.2 replaces them).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 capabilities/oncall/api.py exposes OnCallLookup, the domain types and the provider; nothing else in the package is imported from outside
- [ ] #2 Both schedule sources are selected by the reference's system; the in-memory fake covers both
- [ ] #3 packages/user_rotations no longer exists and no vocabulary from incident or oncall_sync appears in the capability
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #5 With no Opsgenie settings the capability registers and the self-managed source answers (boot test, decisions/oncall.md)
- [ ] #6 Deleting user_rotations also removes its [plugins.incident_response] key, its module from the protected-plugins import contract, and the oncall_sync -> user_rotations ignore entries (repointed to the capability's api)
- [ ] #7 oncall_sync's job and /sre rotations behave unchanged: the legacy_surface pins pass with assertions unchanged and the rotation files are read from the same packaged directory mechanism
- [ ] #8 The generator scaffold passes make check-package-shape, check-fake-coverage, check-import-contracts, check-settings-key-ownership and check-test-seams with no new baseline entry
- [ ] #9 integrations.opsgenie is imported only by capabilities/oncall/adapters/opsgenie.py and the host's settings reads in server/; every other importer is a shrink-only ignore naming its removing task (TASK-127, TASK-145.7.10, TASK-146.2)
- [ ] #10 An unknown ScheduleReference.system, a source without settings and a failing source each return an error OperationResult and never raise for a classified failure; a response of the wrong shape returns INVALID_RESPONSE; each consumer decides what a failure means
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN v2 (2026-11-16; approved, human; supersedes v1 and its OQ section). Delivered as two subtasks, each a side PR from an up-to-date main:
- TASK-146.1.1 (doc-11 row 18d): the capability, its rotations and Opsgenie sources, fake, protected contract on integrations.opsgenie; nothing calls it; one PR with a size-gate exception (rule 1 only, ~16 files / ~610 LOC). Gates TASK-145.7.9.
- TASK-146.1.2 (doc-11 row 18d.c): rotation files and Slack commands move into the capability, oncall_sync reads through its api, packages/user_rotations deleted; the only slice that changes production runs.
Approved rulings (detail in each subtask plan and the 2026-11-16 notes): lookups are async and return OperationResult (outbound-clients.md:37), consumers decide what a failure means; OnCallPerson(email | None, account: Account | None) with Account shaped as TASK-83.4; protected contract allows server and the adapter, other importers are shrink-only ignores naming their removing task, oncall.md Checks reworded; entry point capabilities.oncall.plugin; no requirements; Opsgenie get_schedule UNSUPPORTED_OPERATION; sync configured_rotations() for the job gate; rotation files byte-identical, tolerated path updated in organisation-content.md. AC map: #1, #2, #5, #9, #10 -> 146.1.1; #3, #6, #7 -> 146.1.2; #4, #8 -> both.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-09 (human, Stack L OQ1): pulled forward as a side PR during Stack L L0-L8; the declare cutover (TASK-145.7 L9b) waits on it. Depends on TASK-25.6 (decisions/oncall.md:39: the Opsgenie adapter follows the outbound-client contract).

2026-11-16 (TASK-25.6 OQ1 R1a, human): OnCallLookup is async def (consumed by the async declare, 145.7.9); adapters/opsgenie.py awaits the async build_opsgenie_client (httpx.AsyncClient) directly, with no asyncio.to_thread (outbound-clients.md async-native rule). Move the reads from packages/oncall_sync/adapters/opsgenie.py, which is already async after TASK-25.6.

2026-11-16 planning (row 18d): plan v1 written by /plan-task against main 41319bcc; TASK-176 asked, unchanged. Size gate trips (~800 prod LOC added/moved + ~380 deleted, ~24 files; rules 1 and 3): split proposed A (expand: scaffold, api, domain, service, rotations source, fake) -> B (Opsgenie adapter, import contract; 145.7.9 needs A+B) -> C (contract: Slack entrypoints, oncall_sync repointed, user_rotations deleted). OQ program-scope assessment (PROPOSED, awaiting human): OQ1 settled with a refinement: protected contract on integrations.opsgenie, allowed_importers server (host settings reads, as contract (j)) and capabilities.oncall.adapters.opsgenie, shrink-only ignores for jobs.scheduled_tasks (TASK-127), modules.incident.on_call (145.7.10), packages.oncall_sync.adapters.opsgenie (146.2); oncall.md Checks clarified for host settings reads; AC #3 reworded. OQ2 settled (oncall.md:42 tolerated; 146.2 AC #1). OQ3 settled (plugin.py, precedent features.incident.response.plugin in protected-plugins). OQ4 settled (no requirement; oncall.md Checks boot test). OQ5 REVERSED, ADR conflict: outbound-clients.md:37 adapters return OperationResult and core ports do (features/incident/core/api.py:209); swallowing failures into () would make oncall_sync shrink usergroups on a failed rotation (today packages/oncall_sync/service.py:90-95 skips the group); OnCallLookup returns OperationResult, unknown system ADAPTER_NOT_FOUND, not configured CONFIG_NOT_CONFIGURED, unknown exceptions propagate (outbound-clients.md:33); consumers decide (declare invites nobody and says so, oncall.md:20; oncall_sync skips the group); no OnCallSourceError; AC #9 reworded. OQ6 settled: Opsgenie get_schedule returns UNSUPPORTED_OPERATION. OQ7 verified (lifespan.py:310 calls the sync job registration inside the running loop): sync config-time accessor in api. OQ8 amended: no slack_user_id in the vendor-neutral api (outbound-clients.md:37); OnCallPerson(email | None, account: PlatformAccount(platform, account_id) | None), people-and-accounts.md platform account shape. OQ9 settled: file bytes unchanged, adapter maps to neutral names. No gap needed web research.

2026-11-16 (human): split ruled: A and B combined as one PR with a size-gate exception (rule 1 only: ~16 prod files / ~610 LOC, one subsystem, no consumer, so nothing in production calls it); C separate (the only slice that changes production runs). OQ reassessment at program scope (ADRs, doc-11, doc-15, prior and upcoming tasks; PROPOSED, awaiting human): OQ1 ADR wording conflict, oncall.md Checks 'imported only by the adapter' vs host settings reads (server/plugins/requirements.py:25, server/configuration/host_configuration.py:41); fix: protected contract allowed_importers server + the adapter, shrink-only ignores per removing task (import-linter 2.15 protected contract: allowed_importers permanent, ignore_imports with unmatched=error for debt; precedent contracts (j), (m)); oncall.md Checks reworded. OQ8 gap: no typed person reference until TASK-83.4 (Account(platform, tenant, account_id) in capabilities/people/api.py); incident roles are 'an email or platform account today' (incident-management.md:32); vendors return their own account id and email only sometimes (PagerDuty user reference id/summary, GoAlert user id with optional email, Opsgenie participant name); fix: OnCallPerson(email | None, account: Account | None) with Account shaped exactly as 83.4 specifies (tenant optional), moved to people.api by 83.4 (a capability may import a lower capability's api, plugin-architecture.md:39); 83.4 gains a note. OQ9 settled by organisation-content.md:57,77 (rosters become managed content in the TASK-146 re-cut, doc-15 E2; interim in-code files tolerated): C updates the tolerated path. doc-15:22-23,42: coordination (E5) is a third consumer (leads from on-call); README lists it. OQ2-OQ7 settled by ADRs or prior tasks (OQ5: outbound-clients.md:37 and core ports return OperationResult; OQ7: lifespan.py:310).

2026-11-16 (TASK-146.1 rulings, human): plan APPROVED: split into TASK-146.1.1 (A+B, size exception, doc-11 row 18d) and TASK-146.1.2 (C, row 18d.c); OQ1-OQ9 approved as reassessed; ACs #3 and #9 reworded (now #9 and #10). Plan v2 written.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-03T19:00:00Z

---

Re-cut for E2: the GoAlert schedule source is the target, not a simultaneous Opsgenie/self-managed-source build. The on-call ADR decision precedes implementation; remove the Opsgenie adapter as part of the cutover. The delivery map places this after coordination and treats 2027-04-05 as non-binding within the 2–3 week window.

---

created: 2026-11-03T19:02:00Z

---

Dependency re-cut (2026-11-03): TASK-25.6 is Opsgenie-client-specific and is no longer a prerequisite for the GoAlert target within the 2–3 week window. Re-add it only if the accepted on-call design explicitly needs a transitional Opsgenie read.

---

created: 2026-11-09T18:37:00Z

---

Stack L OQ assessment 2026-11-09 (OQ1), proposed: pulled forward as a side PR during Stack L L0-L8 so the rebuilt declare invites on-call through the capability (no interim Opsgenie adapter in the incident umbrella). Missing dependency: TASK-25.6 (decisions/oncall.md:39 builds the adapter after 25.6; the client lacks a per-attempt timeout, outbound-clients.md:21). Not added until the human rules.

---

created: 2026-11-16T16:46:00Z

---

Planner proposal (no AC removed): reword AC #3 to 'no package, feature or capability other than capabilities/oncall/adapters/opsgenie.py imports integrations.opsgenie, enforced by a protected import-linter contract whose allowed_importers ledger lists the remaining importers with their removing task (oncall_sync adapter: TASK-146.2; modules/incident/on_call.py: TASK-145.7.10; jobs/scheduled_tasks.py: TASK-127; server settings reads: permanent)'. Reason: rg shows five other importers today (app/jobs/scheduled_tasks.py:18, app/modules/incident/on_call.py:11, app/packages/oncall_sync/adapters/opsgenie.py:17, app/server/plugins/requirements.py:25, app/server/configuration/host_configuration.py:41). Also proposed: split into 146.1a/b/c per plan section 2; plan is not handoff-ready until approved.

---
<!-- COMMENTS:END -->
