---
id: TASK-186
title: >-
  Reshape incident/comms into the layout table: interfaces.py, service and
  domain packages, the publisher an adapter
status: In Progress
assignee: []
created_date: '2026-11-06T02:57:00Z'
updated_date: '2026-11-06T19:56:00Z'
labels:
  - incident
  - plugin-architecture
milestone: m-7
dependencies:
  - TASK-114.1
references:
  - decisions/feature-packages.md
  - decisions/incident-management.md
ordinal: 489000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-145.4 carried the status-update modules into features/incident/comms/ flat (approval, comms_profile, form, history, ports, prompt, publisher). The layout table amended on 2026-11-06 (TASK-114.1) gives them homes: the Protocols move from ports.py to interfaces.py; the use cases move into a service/ package, one module per use case; the comms profile and copy-ready rendering, pure business rules, move into domain.py. A move with importers and tests repointed, behaviour-neutral dedupes and dead-code deletion, and no behaviour change. Single PR from main; it removes comms' entries from app/bin/baselines/package_shape.txt.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 features/incident/comms/ holds only names from the amended layout table; its package_shape baseline entries are deleted
- [x] #2 Every importer and test is repointed; no behaviour changes (the comms tests pass unchanged apart from import paths)
- [x] #3 Ruff, import contracts, check-package-shape, mypy and pytest pass
- [x] #4 Duplicated private helpers in comms are deduplicated and dead code (get_pending_status_update, the unread TIMEZONE setting, the text_generation_available wrapper, the local unavailable code) is deleted, with no behaviour change
- [x] #5 decisions/feature-packages.md records that pure rules shared by adapters live in domain.py and that service/ splits one module per use case in the domain's language; the comms README lists the new paths
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Basis
Planned against origin/main 641b3879; approved as a single PR with a size exception (human, 2026-11-06), after a program-scope review (ADRs, doc-11, doc-15, backlog) of the open questions and a shape review of comms. Side PR from main on task-186-comms-layout.

## Decisions (approved 2026-11-06)
- D1 Pure rendering of the comms profile is a business rule: ProfileLabels, format_profile_time, render_profile_sections, render_profile (comms_profile.py) and render_copy_ready (publisher.py) move into domain.py. A pure function two adapters share lives in domain.py, never inside one adapter (adapters do not import each other; DRAFT-10 adds a second StatusPagePublisher adapter). ADR gap closed in feature-packages.md (domain.py row and a rule line).
- D2 domain.py stays a module (~245 lines; feature-packages.md:47 grows it on readability). Split domain/profile.py when TASK-165.8 or DRAFT-10 grows the profile.
- D3 service/ is one module per use case, named in the ADR's language (rule 2 applied inside a package); helpers shared by those modules stay private inside service/. ADR gap closed in feature-packages.md. Mapping: service.py draft use cases -> service/draft.py; service.py overview (the ADR's approved history) -> service/history.py; history.py (published toggle, copy-ready read) -> service/publication.py; approval.py, form.py, prompt.py -> service/ under the same names. service/__init__.py is docstring only, no re-exports.
- D4 ports.py -> interfaces.py; no Protocol renames (TextGenerator, StatusPagePublisher carry no Port). StatusPagePublisher and approve_and_publish keep the ADR's names (DRAFT-10 makes them literal).
- D5 Behaviour-neutral cleanups in the same PR: one private service/_results.py replaces the 4 identical _failure copies and the 2 _STAGE_ORDER copies; service.text_generation_available (a wrapper) is deleted, callers use providers.text_generation_available; adapters/text_generation.py uses ErrorCode.TEXT_GENERATION_UNAVAILABLE (same string) instead of a local constant; dead get_pending_status_update (tests only) deleted with its tests; dead setting TIMEZONE (no reader, set nowhere, extra=ignore) deleted with its test lines; surface wording ("modal", the slash command) removed from service/domain docstrings.
- D6 Kept separate (domain-model-evolution gate): DraftedFields and StatusUpdateEdit.
- D7 Out of scope, recorded on other tasks: mrkdwn_blocks (comms and scribe) and build_profile_labels (catalogue -> ProfileLabels, needed by a Teams handler too) -> note on TASK-43; comms TextGenerator after TASK-25.10 (incident-management.md:128 vs 25.10 AC #2) -> note on TASK-25.10; TASK-145.6 and TASK-140.11 cite comms/service.py paths -> notes to re-ground.

## Domain-model evolution gate (D6)
Scenarios: (a) happy path: responder drafts with AI, then edits: generate returns DraftedFields, form.py:157 converts the base to a StatusUpdateEdit at the hand-off; (b) breaking: TASK-140.11 pre-generates a draft with no responder: the model output has no human author and has not been reviewed; (c) TASK-165.8 bounded personalisation edits the responder's content. Lifecycle: DraftedFields is transient model output (owner: the generation step, never stored); StatusUpdateEdit is a responder submission validated by blank_fields (owner: the form). Neither is stored (core StatusUpdate is). Same shape, different provenance and authority: merging would blur AI output with responder content. Decision: keep both; no field changes in this PR.

## Steps
1. git mv ports.py interfaces.py; its imports read ProfileLabels/CopyReadyText from domain.
2. Merge comms_profile.py and publisher.py into domain.py (pure functions, ProfileLabels, the zone constant); delete both files; domain imports only core.api and stdlib.
3. Create service/__init__.py (docstring). git mv service.py service/draft.py, then move the overview read (get_status_update_overview and its private helpers) to service/history.py; git mv history.py service/publication.py; git mv approval.py, form.py, prompt.py into service/. Add service/_results.py (failure, STAGE_ORDER); delete the copies. Delete get_pending_status_update and service.text_generation_available.
4. adapters/copy_ready.py imports render_copy_ready from domain; adapters/text_generation.py uses ErrorCode.TEXT_GENERATION_UNAVAILABLE; providers.py imports interfaces.
5. Repoint entrypoints/slack.py and slack_views.py.
6. settings.py: delete TIMEZONE.
7. Repoint tests (imports and string patch targets only): tests/unit/features/incident/comms/*, tests/integration/features/incident/comms/*, test_..._new_entrypoint.py _TARGET, test_..._slack.py _SERVICE_MODULES (assert each listed module imports), tests/unit/bin/test_bin_fake_coverage_check.py fixture path; delete test_incident_comms_status_update_pending.py and the get_pending cases of the overview test; drop TIMEZONE from the settings test.
8. Docs: comms README (call path, files); decisions/feature-packages.md (domain.py row, service/ rule, change line); INVENTORY.md line refs if shifted.
9. Delete app/bin/baselines/package_shape.txt comms lines.

## AC traceability
AC1 <- steps 1-3, 9; make check-package-shape. AC2 <- steps 4-7; targeted comms, server, legacy_surface and bin tests pass with assertions unchanged apart from paths and the deleted dead-code tests. AC3 <- gates. AC4 <- step 3, 4, 6 (dedupe and dead code) verified by rg. AC5 <- step 8.

## Test matrix
A move: the existing comms unit/integration/legacy-surface tests are the matrix. No new behaviour test. _SERVICE_MODULES gains an import check so a missed rename cannot weaken the handler-discipline test.

## Blast radius and rollback
Merging deploys; no runtime behaviour change (TIMEZONE unread; error code string identical). The entry point features.incident.comms is untouched. One git revert restores. Independent of #1833 apart from INVENTORY line refs.

## Gates
cd app: ruff; targeted tests; make check-import-contracts; make check-settings-key-ownership; make check-package-shape; make check-fake-coverage; then once each, sequentially: full mypy, full pytest.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-06: plan approved as a single PR with a size exception (human). Implementing on task-186-comms-layout from main 641b3879.

2026-11-06 implemented on task-186-comms-layout (from main 641b3879), all ACs checked, In Progress for review.
- Moves: ports.py -> interfaces.py; service.py -> service/draft.py (overview -> service/history.py); history.py -> service/publication.py; approval.py, form.py, prompt.py -> service/; comms_profile.py and publisher.py merged into domain.py. service/__init__.py docstring only; service/_results.py holds failure() and STAGE_ORDER.
- Deleted: 4 _failure copies, 2 _STAGE_ORDER copies, service.text_generation_available (form imports providers.text_generation_available under the same name, so form-attribute patches are unchanged), TEXT_GENERATION_UNAVAILABLE_CODE (ErrorCode member, same string), get_pending_status_update and its tests, the unread TIMEZONE setting (extra=ignore; set nowhere).
- entrypoints: the copy-ready label kwargs (ProfileLabelArgs, profile_label_args) moved from slack.py to slack_views.py beside build_profile_labels, so slack.py still imports nothing from comms.domain (the existing discipline test holds unchanged).
- Tests: imports and string patch targets repointed; _SERVICE_MODULES lists the service/ modules and a new parametrized check asserts each exists. INVENTORY.md comms ref now slack.py:124 (was a stale :117).
- ADR: feature-packages.md domain.py row, service/ and shared-rule sentences, 2026-11-06 change line. Baseline: 7 comms entries removed.
- Gates: ruff clean; targeted tests 1307 passed; make check-import-contracts 13 kept 0 broken; check-settings-key-ownership OK; check-package-shape OK (3 baselined); check-fake-coverage OK; mypy 41 errors in 14 files, all pre-existing in legacy modules/, none in comms; pytest 6478 passed.
- Merging deploys with no runtime behaviour change; one git revert restores.
<!-- SECTION:NOTES:END -->
