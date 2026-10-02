---
id: TASK-135.4
title: >-
  Add packages/incident/scribe holding the draft and summarize use cases, not
  yet registered
status: In Progress
assignee: []
created_date: '2026-10-02 15:39'
updated_date: '2026-10-02 18:01'
labels:
  - plugin-architecture
  - features
  - slack
milestone: m-7
dependencies:
  - TASK-135.2
  - TASK-135.3
  - TASK-97
references:
  - decisions/feature-packages.md
  - decisions/plugin-architecture.md
  - decisions/incident-management.md
parent_task_id: TASK-135
priority: medium
type: task
ordinal: 305000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 of TASK-135 (expand). Rescoped on 2026-10-02 (human): the merge of the two packages was split in two PRs for review size. This slice adds the merged subdomain as new code that nothing registers; TASK-135.5 switches both commands to it and deletes packages/incident_draft and packages/incident_summary.

THIS SLICE
- packages/incident/scribe/ holds both use cases as a copy of the two packages after TASK-135.2 and TASK-135.3: two handlers and one register_commands in platforms/slack.py, one service module, one settings module, one providers module, the Google Docs and Slack bookmark adapters, both locale catalogues and one README.
- Its __init__.py defines no hookimpl, so plugin discovery finds the package and registers nothing from it: packages.incident_draft and packages.incident_summary still own both commands and their i18n resources.
- The unit tests of both packages are copied to tests/unit/packages/incident/scribe/ with imports and patch strings rewritten, so the new code is tested before it is switched on. The originals stay until TASK-135.5.
- The incident umbrella layers contract gains scribe; the copy needs four import-linter ignore entries beside the six that name the two packages, until TASK-135.5 deletes the originals.
- No behaviour change and no change to any existing production module other than app/pyproject.toml.

Human decision 2026-10-02: the merged subdomain has one service.py (decisions/feature-packages.md layout table), about 1,030 lines until TASK-134 moves draft's answer parsing to the text-generation capability.

Whether IncidentDocumentStore and IncidentReportLinkLookup belong in core/ is decided by the TASK-97 packet and is not changed here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 packages/incident/scribe/ holds both use cases (two handlers, one service, one settings and one providers module, the adapters and both locale catalogues) and imports packages.incident.core only through core/api.py; its __init__.py defines no hookimpl, so it registers no command and no i18n resource
- [x] #2 No existing production module changes other than app/pyproject.toml: packages/incident_draft, packages/incident_summary and their tests are untouched, and the legacy_surface suite is green with no change to its files
- [x] #3 The scribe code is the two packages' code with import paths rewritten and the name-collision renames listed in the plan, and nothing else; its unit tests live under tests/unit/packages/incident/scribe/
- [x] #4 The incident umbrella layers contract lists scribe as an independent sibling above core with exhaustive = true; exactly four import-linter ignore entries are added, the scribe copies of the six entries naming the two packages, whose originals TASK-135.5 deletes
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Split (human, 2026-10-02): this task was planned and approved as the whole merge. After implementation it was split in two for review size. The full approved plan now sits on TASK-135.5 with a note of which steps each task took; this task keeps the part below.

STEPS (numbers are those of the approved plan)
0. Re-verification on top of layers 1 to 3: done, recorded as a comment on this task.
1. Create app/packages/incident/scribe/ from the two packages: domain.py, adapters/google_docs.py, adapters/slack.py and providers.py as they are with import paths rewritten; both locale catalogues under locales/ with their file names unchanged; one settings.py holding IncidentDraftSettings and IncidentSummarySettings with their aliases unchanged; one service.py (draft's module with summary's functions appended); one platforms/slack.py with both handlers; one README.md. The originals are copied, not moved: they are deleted by TASK-135.5.
2. Resolve the name collisions the merge creates, and nothing else: platforms/slack.py _DOMAIN -> _DRAFT_DOMAIN and _SUMMARY_DOMAIN, one register_commands making both registrar.register_command calls, _error_response -> _draft_error_response and _summary_error_response, the --limit coercion helper kept once; service.py EMPTY_HISTORY_CODE, logger and _now kept once, the two limit and window helpers renamed by use case.
3 (part). app/packages/incident/scribe/__init__.py is a docstring only. The hookimpls are TASK-135.5.
5 (part). app/pyproject.toml: the incident-umbrella first layer becomes "documents | drive | meet | scheduling | scribe"; four ignore entries are added for the copy (no-host-imports: google_docs -> infrastructure.configuration.integrations.google, google_docs -> infrastructure.drive, platforms.slack -> infrastructure.i18n; integrations-via-adapters: service -> integrations.openai). The six originals and the two temporary feature-independence entries stay until TASK-135.5.
6 (part). Copy the 13 unit test files to app/tests/unit/packages/incident/scribe/ as test_incident_scribe_<entity>_<action>.py with every import and patch string rewritten.
9. Gates from app/: ruff, mypy (0 errors in touched files), lint-imports, pytest tests --ignore=tests/smoke.

AC MAP
- #1 -> steps 1, 2, 3. #2 -> the commit's file list and the legacy_surface run. #3 -> steps 1, 2, 6. #4 -> step 5. #5 -> step 9.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented as layer 4 of Stack G on stack-g/task-135.4-incident-scribe-subdomain, committed as 6178aa7e on top of d902d38c (TASK-135.3). Status stays In Progress; a human moves it to Done.

WHAT CHANGED (30 files, +7528 / -1; every file but app/pyproject.toml is new)
- app/packages/incident/scribe/: __init__.py (docstring only, no hookimpl), service.py (1034 lines), settings.py, providers.py, domain.py, adapters/google_docs.py, adapters/slack.py, platforms/slack.py, locales/ (four catalogue files), README.md.
- app/tests/unit/packages/incident/scribe/: the 13 unit test files of the two packages, renamed test_incident_scribe_*.py, imports and patch strings rewritten.
- app/pyproject.toml: scribe added to the incident-umbrella layer; four ignore entries added for the copy.
- Collision renames, the only edits to function bodies against the originals: platforms/slack.py _DOMAIN -> _DRAFT_DOMAIN and _SUMMARY_DOMAIN, _error_response -> _draft_error_response and _summary_error_response, the four dispatch closures named per command, _parse_limit kept once; service.py _resolve_limit -> _resolve_draft_limit and _resolve_summary_limit, _resolve_window_start -> _resolve_draft_window_start and _resolve_summary_window_start, EMPTY_HISTORY_CODE, logger and _now kept once. 'from __future__ import annotations' is dropped from the merged settings module and from four of the copied test files.

FOR REVIEW
1. Three copied unit tests differ in body from their originals: the draft and summarize registration tests asserted a single register_command call, which the merged register_commands no longer makes. They pick their command's registration from the recorded calls; the assertions on command, parent, handler and fallback are the same.
2. Labels in this commit name the wrong task: the scribe __init__.py docstring and the two pyproject comments beside the added ignore entries say TASK-135.4 switches registration and deletes the originals. That is TASK-135.5. All three lines are replaced or removed by TASK-135.5's commit, so nothing wrong reaches main once both layers merge; the text is only visible in this PR's diff.
3. GitHub shows this PR as about 7,500 added lines because a copy cannot be displayed as a rename. Against the originals the content differs only by import paths and the renames above.

GATES (run on an export of 6178aa7e, 2026-10-02)
- ruff check . -> All checks passed!
- mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 65 errors in 22 files (baseline count; 385 source files checked); 0 in packages/incident/scribe.
- lint-imports -> Contracts: 9 kept, 0 broken.
- pytest tests/integration/legacy_surface -> 17 passed, with no change to its files.
- pytest tests --ignore=tests/smoke -> 6 failed, 3973 passed (3675 before, plus the copied scribe tests). The 6 are the known TASK-90 order leaks.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-02 16:46
---
2026-10-02: unblocked by TASK-97. The subdomain is packages/incident/scribe (entry point incident.scribe after TASK-124.5). IncidentDocumentStore and IncidentReportLinkLookup stay here; TASK-38.2 moves the document store into core/ behind IncidentReport and retires the link lookup. The only AC text change is the <subdomain> placeholder in AC #4, now scribe; order and wording are otherwise unchanged.
---

created: 2026-10-02 17:11
---
Re-verified TODAY against main at 8bcbf373 (2026-10-02). Since c8de7643 main gained only #1528 (blazer formatter, aws_sns_notification) and #1529 (planning records); git diff c8de7643..8bcbf373 is empty for packages/incident, packages/incident_draft, packages/incident_summary, their unit tests, tests/integration/legacy_surface, app/pyproject.toml and server/. TASK-25.10, TASK-134 and TASK-110 are still To Do and unmerged: the services still import integrations.openai and pyproject declares no entry points. No difference, so step 5's 'or none if TASK-25.10 has already moved the summarizer' does not apply (one merged integrations.openai entry) and step 8's entry-point merge does not apply (TASK-110 unmerged). pyproject lines are as planned: no-host-imports :289-292, integrations-via-adapters :341-342, feature-independence modules :354-355. Step 0 is re-run when this layer starts, on top of layers 1 to 3. Delivery changed: this slice is layer 4 of the TASK-135 stack.
---

created: 2026-10-02 17:45
---
Step 0 re-run 2026-10-02 on top of layers 1 to 3 (d902d38c; main still at 8bcbf373, the stack's base). TASK-25.10, TASK-134 and TASK-110 are still To Do: both services import integrations.openai and pyproject declares no entry points, so the integrations-via-adapters entries become one and there is no entry point to merge. Differences from the plan's lists: (1) rg finds two files the plan did not name: decisions/outbound-clients.md:66 names incident_draft in prose (updated with the other records), and tests/modules/incident/test_incident_helper.py has two legacy test functions named test_legacy_handle_incident_summary_command*, which belong to modules/incident and are left alone. (2) infrastructure/i18n/resources.py deduplicates registrations on path alone and logs i18n_resource_duplicate_skipped for the second; the loader reads every <domain>.<locale>.yml under a path and spec.domain is only logged. Two specs on the shared locales directory (plan step 3) would therefore drop the second with a warning at every boot, so the package registers the directory once. (3) Merging the two register_commands functions means the three unit tests that asserted a single register_command call cannot keep their bodies (plan step 6 expected no body edits).
---

created: 2026-10-02 18:01
---
2026-10-02 (human, in session): rescoped. The merge was implemented as one change and then split by the human into two commits for review size: this task is the unregistered package (6178aa7e) and the new TASK-135.5 is the switch and the deletion (5c5bcd37). Title, description, ACs, plan and notes are rewritten for the smaller scope; the approved full plan moved to TASK-135.5. Comment #3 (step 0) stands for both tasks.
---
<!-- COMMENTS:END -->
