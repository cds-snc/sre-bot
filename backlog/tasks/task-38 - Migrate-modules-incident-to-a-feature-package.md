---
id: TASK-38
title: Migrate modules/incident to a feature package
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-09-03 16:29'
labels:
  - migration
  - phase-5
milestone: m-5
dependencies:
  - TASK-36
  - TASK-37
references:
  - decisions/migration.md
  - decisions/feature-packages.md
  - 'https://github.com/cds-snc/sre-bot/issues/1292'
priority: medium
ordinal: 38000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second strangler target (largest user surface; 51 files, plus the incident_helper legacy-list entry). Same recipe as task-37; the webhooks migration (task-37) establishes the pattern to copy.

SEQUENCING (human, 2026-09-03): this task runs AFTER the TASK-25* vendor-integration cleanup. Its exact position in the queue is decided once that cleanup is done, so treat the m-5 milestone and the TASK-36/TASK-37 dependencies as necessary-but-not-sufficient.

STRUCTURE DECIDED (2026-09-03, decisions/feature-packages.md "Complex features: an umbrella directory, never a flat prefix"). incident is genuinely complex (app/modules/incident is 4636 LOC across 17 modules), so it is an umbrella, not a single flat package and not a family of flat incident_* packages:

  app/packages/incident/
  |-- __init__.py   EMPTY (0 bytes) - namespace only, no hookimpls, no entry-point line
  |-- common/       shared kernel: incident domain vocabulary + IncidentSettings tree, no I/O
  \-- <subdomain>/  each shaped like the feature-packages layout table; each is a plugin

Entry-point names carry the dotted prefix ("incident.draft" = "packages.incident.draft", never "draft") because entry-point names are a flat per-group registry.

Candidate subdomain split (to be confirmed during planning, not settled here): declare/ (core.py + incident.py), channel/ (incident_conversation, incident_status, information_display, information_update, incident_roles), documents/ (incident_document, incident_folder), retro/ (schedule_retro), alerts/ (incident_alert, notify_stale_incident_channels), plus draft/ summary/ relocated in and the already-correct scheduling/. db_operations.py and utils.py land in common/.

RECONCILIATION OWED BY THIS TASK. decisions/migration.md rule 5's open shape/naming question is now closed, which makes two shipped packages named deviations this task must relocate:
- packages/incident_draft  -> packages/incident/draft
- packages/incident_summary -> packages/incident/summary
These are import-path + entry-point-name changes with no runtime surface change. Sequence the incident_draft move AFTER TASK-25.1.6.6, which rewrites the same 1704-line test file's patch targets - otherwise those strings get rewritten twice. Note that a rename is NOT sufficient on its own: unittest.mock patch string literals fail at patch time rather than import time, so every "packages.incident_draft..." / "packages.incident_summary..." patch target must be swept too (TASK-25.1.6.2 hit exactly this).

ALREADY CORRECT, NOT THIS TASK'S WORK: app/packages/incident/scheduling/ is created directly in its umbrella position by TASK-25.1.6.2 (redirected 2026-09-03), which also creates the empty app/packages/incident/__init__.py. This task inherits that umbrella rather than creating it, and must not regress it.

Settings consolidation onto a common/settings.py IncidentSettings tree (ACCESS-style, INCIDENT_{SUB}_{FIELD}) renames INCIDENT_SUMMARY__* and incident_draft's aliased env vars. That touches terraform/SSM, so it is deployment-coordinated and belongs in this task's series, not in a layout-only PR.

Steps:
1. Confirm smoke coverage of every incident command/action (task-36 inventory).
2. Fill out app/packages/incident/ as an umbrella per decisions/feature-packages.md (copy the access/ shape); confirm the subdomain split before writing code.
3. Slack handlers via register_slack_commands hookspec; parsing via the shared parser; rendering via the shared renderer; locales/ EN+FR per decisions/i18n.md (parity gate from task-21 applies).
4. Relocate incident_draft and incident_summary into the umbrella, repoint their entry-point names to the dotted form, and sweep mock patch string literals.
5. Consolidate settings onto common/settings.py; coordinate the env-var rename with terraform/SSM.
6. Cut over, delete app/modules/incident/, smoke green pre/post, command names unchanged.
7. Add "packages.incident" as a container on TASK-18's contract (e) with exhaustive = true, and land it green as the final step.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/packages/incident/ matches the layout; handlers pass the five-step review
- [ ] #2 Smoke tests pass pre and post cutover; command names and responses unchanged
- [ ] #3 app/modules/incident/ deleted; legacy list entry removed; baselines never grew
- [ ] #4 EN/FR catalogues complete (parity check green)
- [ ] #5 app/packages/incident/__init__.py is empty (no hookimpls, no re-exports, no entry-point line); every subdomain declares its own entry point under the dotted name incident.<subdomain>
- [ ] #6 Shared incident vocabulary lives in packages/incident/common/ with no I/O and at least two subdomain consumers per item; no subdomain imports another subdomain
- [ ] #7 TASK-18 contract (e) gains a packages.incident container with exhaustive = true and lint-imports is green
- [ ] #8 packages/incident_draft and packages/incident_summary no longer exist; their code, tests and locales live under packages/incident/ and no packages/incident_* directory remains anywhere under app/packages/
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Smoke suite green post-cutover
- [ ] #2 PR series references decisions/migration.md
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-03 16:15
---
SCOPE UPDATE (2026-09-03): description rewritten and 4 ACs added following the umbrella-vs-flat architecture review. decisions/feature-packages.md now carries the umbrella rule and decisions/migration.md rule 5 was amended to point rule-5 relocations at their final umbrella position; this task inherits the resulting reconciliation debt (relocating incident_draft / incident_summary / incident_scheduling). Original AC #1-#4 untouched.

SIZE WARNING for whoever plans this: this task was already the largest strangler target (4636 production LOC, 17 modules) and now also owns three package relocations plus a deployment-coordinated env-var rename. It will not survive the single-PR size gate. Expect decomposition into at least: (i) umbrella skeleton + relocate the three incident_* packages, (ii) one slice per subdomain built + cut over, (iii) settings-tree consolidation with the terraform/SSM change, (iv) modules/incident deletion + the TASK-18 container line. Do that breakdown before any code.

IMMEDIATE, FREE ACTION OUTSIDE THIS TASK: TASK-25.1.6.2 is in flight on branch feat/incident_retro_helpers_relocation with its tests written but app/packages/incident_scheduling/ not yet created (only app/tests/{unit,integration}/packages/incident_scheduling/ exist). Creating it directly as app/packages/incident/scheduling/ costs one directory name today versus a rename PR later. Flagged on TASK-25.1.6.2.

OPEN QUESTION for the human: whether the three relocations should be split out of this task into their own near-term task rather than waiting for m-5. They are independent of TASK-36/TASK-37 (this task's dependencies), they are pure import-path changes, and every week they stay flat is another week of new code keyed to the wrong paths. The one real cost is the incident_draft test file (1704 lines, 135 mock references), which argues for sequencing after TASK-25.1.6.6. Not created unilaterally - say the word and I will.

CANDIDATE SUBDOMAIN SPLIT is a proposal only. The mapping in the description came from module sizes and names, not from reading the call graph. Validate it against actual cohesion during planning; incident_conversation.py (464) and core.py (601) in particular may not fall where the names suggest.
---

created: 2026-09-03 16:29
---
SCOPE CORRECTION (2026-09-03): TASK-25.1.6.2 was redirected to create app/packages/incident/scheduling/ directly, so incident_scheduling is no longer a relocation this task owns - it also creates the empty umbrella app/packages/incident/__init__.py that this task inherits. AC#6 replaced accordingly (now covers incident_draft and incident_summary only, plus a no-packages/incident_*-anywhere sweep). Description updated with the human sequencing decision: this task runs after the TASK-25* vendor-integration cleanup, exact position TBD once that is done. Also recorded the mock-patch-string-literal hazard: renaming directories alone is insufficient because patch targets are strings that fail at patch time, not import time - TASK-25.1.6.2 hit this with 10 patch targets.
---
<!-- COMMENTS:END -->
