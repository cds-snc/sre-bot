---
id: TASK-25.1.6.8.3
title: >-
  Introduce a packages/role feature adapter and migrate modules/role/role.py
  onto DriveProvider
status: To Do
assignee: []
created_date: '2026-09-08 18:58'
updated_date: '2026-09-08 23:13'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.8.1
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - decisions/feature-packages.md
  - decisions/migration.md
  - app/packages/incident/documents/adapters/google_docs.py
  - app/modules/role/role.py
parent_task_id: TASK-25.1.6.8
priority: medium
ordinal: 158000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
modules/role/role.py (the talent/hiring interview-panel workflow) calls google_drive.create_folder once and google_drive.copy_file_to_folder seven times (template-copying interview documents into a newly-created candidate folder). This is unrelated to the incident feature and must not be routed through packages/incident's adapter.

PACKAGE HOME (decided 2026-09-08 with human review, changed from the original "packages/role"): a new flat feature package app/packages/talent/ (empty __init__.py, no hookimpl and no entry-point line) holding adapters/google_drive.py. "talent" is the concern's final home per decisions/migration.md rule 5 and decisions/feature-packages.md: the module's own vocabulary is talent (INTERNAL_TALENT_FOLDER, talent_role_* log events, the /sre talent-role command), and relocating later costs more than naming it correctly at creation. Flat, not an umbrella: one subdomain today.

This is migration.md rule 5's lighter path, not a capability migration: role.py stays the registered, frozen legacy module and keeps its Slack command surface; only host-surface-free Drive I/O relocates. The adapter is built on TASK-25.1.6.8.1's DriveProvider via infrastructure.drive.factory.get_drive_provider(), never constructing GoogleDriveProvider directly.

ADAPTER SHAPE: domain-oriented function names (create_role_folder, copy_template_to_role_folder), translating DriveProvider's OperationResult into the shapes role.py consumes (dict | None for the folder, str | None for a copied file id), with failure logging mirroring packages/incident/drive/adapters/google_drive.py.

DELEGATION (decided 2026-09-08 with human review): the adapter owns the SRE_BOT_EMAIL delegation internally and passes delegated_user_email to every DriveProvider call. role.py drops its BOT_EMAIL constant and stops naming the Google auth subject. The delegated value reaching Google is unchanged.

FAILURE SEMANTICS (decided 2026-09-08 with human review): today a Drive SDK exception propagates out of role_view_handler and aborts the whole flow before the Slack channel is created. DriveProvider returns a classified OperationResult instead, so the adapter returns None on failure and role.py logs an error and returns early, mirroring its existing folder-creation failure path. No half-provisioned channel; the crash becomes a logged abort.

ALSO IN SCOPE: delete role.py's unused ROLE_SCOPES constant (dead Drive scope list, zero references repo-wide).

NOT IN SCOPE: modules/incident/*, jobs/scheduled_tasks.py (TASK-25.1.6.8.2, already done), modules/reports/google_groups.py and the deletion of app/integrations/google_workspace/google_drive.py (TASK-25.1.6.10), any Slack/i18n/command behavior in role.py, and relocating app/tests/modules/role/test_role.py out of the legacy test tree.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A new flat feature package app/packages/talent/ exists (empty __init__.py, adapters/__init__.py, no hookimpl and no entry-point line) with adapters/google_drive.py built on infrastructure.drive.factory.get_drive_provider(), never constructing GoogleDriveProvider directly
- [ ] #2 The adapter owns the SRE_BOT_EMAIL delegation and passes delegated_user_email to every DriveProvider call; modules/role/role.py no longer defines BOT_EMAIL or ROLE_SCOPES and no longer imports integrations.google_workspace.google_drive
- [ ] #3 modules/role/role.py calls the adapter for its folder creation and all seven template copies, with call order, document names and log events preserved
- [ ] #4 A failed Drive operation (classified OperationResult error) logs an error and aborts role_view_handler before any Slack channel is created, instead of raising out of the handler
- [ ] #5 Existing Drive coverage in app/tests/modules/role/test_role.py is preserved at the new adapter boundary, plus new unit tests for the adapter under app/tests/unit/packages/talent/adapters/
- [ ] #6 Focused tests, ruff, mypy, and app/bin/check_sdk_typing.py pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (grep/read verified 2026-09-08 against main)
Call sites to migrate, all inside modules/role/role.py::role_view_handler:
- role.py:16-18 google_settings = get_google_workspace_settings(); BOT_EMAIL = google_settings.SRE_BOT_EMAIL
- role.py:11 from integrations.google_workspace import google_drive
- role.py:31 ROLE_SCOPES (dead: zero references repo-wide)
- role.py:215-221 google_drive.create_folder(role_name, INTERNAL_TALENT_FOLDER, "id", delegated_user_email=BOT_EMAIL)
- role.py:222-231 isinstance(folder, dict) guard + talent_role_folder_creation_failed error + return
- role.py:241-302 seven google_drive.copy_file_to_folder(TEMPLATE, name, TEMPLATES_FOLDER, folder_id, delegated_user_email=BOT_EMAIL) calls, each followed by log_document_created(label, id)
- role.py:322 the channel topic embeds scoring_guide_id (the first copy result)
Shipped capability surface (TASK-25.1.6.8.1, Done): infrastructure/drive/provider.py::DriveProvider.create_folder(name, parent_folder_id, *, delegated_user_email) and copy_file_to_folder(file_id, name, source_parent_id, destination_folder_id, *, delegated_user_email); both return OperationResult[DriveFile]. No fields parameter on the Protocol. infrastructure/drive/factory.py::get_drive_provider() is a @cache singleton.
Precedent adapter: packages/incident/drive/adapters/google_drive.py (TASK-25.1.6.8.2, Done) - _to_dict/_log_failure shape, module-level config read, get_drive_provider() called per function.
Guardrail baselines checked: neither app/bin/baselines/deprecated_infra_client_imports.txt nor sdk_typing_antipatterns.txt lists modules/role/role.py, so no baseline edits are required or possible here.

STEP 1 - package scaffold
Create app/packages/talent/__init__.py (empty), app/packages/talent/adapters/__init__.py (empty), app/packages/talent/adapters/google_drive.py. No hookimpl, no entry-point line, no registration anywhere (migration.md rule 5 lighter path). Module docstring states this is the only talent file allowed to reach the Drive boundary.

STEP 2 - adapter (app/packages/talent/adapters/google_drive.py)
- Module level: BOT_EMAIL = get_google_workspace_settings().SRE_BOT_EMAIL (mirrors the incident adapter's module-level INCIDENT_TEMPLATE read; SRE_BOT_EMAIL defaults to "" in infrastructure/configuration/integrations/google.py:36, so import is safe under pytest where the env var is unset).
- _log_failure(event, result) -> None: structlog warning with status=result.status.value, error_code, retry_after (identical shape to packages/incident/drive/adapters/google_drive.py).
- create_role_folder(name: str, parent_folder_id: str) -> dict[str, Any] | None: get_drive_provider().create_folder(name, parent_folder_id, delegated_user_email=BOT_EMAIL); on failure log "talent_drive_create_folder_failed" and return None; on success with data None return None; else return {"id": data.id, "name": data.name}.
- copy_template_to_role_folder(template_id: str, name: str, templates_folder_id: str, destination_folder_id: str) -> str | None: get_drive_provider().copy_file_to_folder(template_id, name, templates_folder_id, destination_folder_id, delegated_user_email=BOT_EMAIL); on failure log "talent_drive_copy_template_failed" (include document_name=name) and return None; on success return data.id (None if data is None).
No fields argument: DriveProvider's Protocol has none, so the Google response carries its default projection instead of today's fields="id". Behavior-neutral at this boundary (the adapter returns only id/name).

STEP 3 - role.py imports and constants
Drop "from integrations.google_workspace import google_drive"; add "from packages.talent.adapters import google_drive as talent_drive". Delete line 16 (google_settings = ...), line 18 (BOT_EMAIL = ...) and line 31 (ROLE_SCOPES), and remove get_google_workspace_settings from the infrastructure.configuration.integrations.google import (keep get_google_resources_config, still used by the template/folder constants).

STEP 4 - role.py folder creation
Replace the create_folder call plus the isinstance(folder, dict) branch with:
  folder = talent_drive.create_role_folder(role_name, INTERNAL_TALENT_FOLDER)
  if folder is None: log.error("talent_role_folder_creation_failed", folder_name=role_name); return
  folder_id = folder.get("id")
The error event name and kwargs are preserved exactly; only the falsy check changes from isinstance-on-dict to is-None (the adapter already returns dict | None). The talent_role_folder_created info log is unchanged.

STEP 5 - role.py template copies
Add one local helper beside the existing log_document_created closure:
  def copy_template(template_id, document_name, label):
      file_id = talent_drive.copy_template_to_role_folder(template_id, document_name, TEMPLATES_FOLDER, folder_id)
      if file_id is None: log.error("talent_role_document_copy_failed", document_name=label)
      else: log_document_created(label, file_id)
      return file_id
Each of the seven copies becomes "<x>_id = copy_template(<TEMPLATE>, <document name f-string>, <label>)" followed by "if <x>_id is None: return". Template ids, document-name strings, labels and call order are unchanged byte-for-byte; the happy-path info-log count stays 10. The early return keeps a failed copy from producing a Slack channel whose topic points at a document that was never created (AC#4).

STEP 6 - repoint existing tests in place (app/tests/modules/role/test_role.py; legacy tree kept, per the TASK-25.1.6.7 / .8.2 precedent of not relocating legacy test files during an import-path swap)
- Replace all eight @patch("modules.role.role.google_drive.create_folder" / ".copy_file_to_folder") decorators with @patch("modules.role.role.talent_drive.create_role_folder") / @patch("modules.role.role.talent_drive.copy_template_to_role_folder") at lines 310-311, 331-332, 355-356, 451-452, 475-476.
- Delete the three @patch("modules.role.role.BOT_EMAIL", "bot_email") decorators (lines 309, 329, 353): the constant no longer exists in role.py.
- test_create_new_folder (312): assert create_role_folder called once with ("foo", "internal_talent_folder") - no fields positional, no delegated_user_email kwarg.
- test_create_new_folder_failed (333): mocked return becomes None (was ""); the bound_logger.error assertion and copy-not-called assertion are unchanged.
- test_copy_files_to_internal_talent_folder (357): rewrite the seven assert_has_calls entries to call(template_id, document_name, "mock_templates_folder", "folder_id") - same order and strings, no delegated_user_email kwarg; keep the bound_logger.info.call_count == 10 assertion.
- test_role_creates_channel_and_sets_topic_and_announces_channel (453) and test_role_add_invited_users_to_channel (477): repoint patches only; the topic assertion keeps using the mocked copy return value.
- NEW test in the same file: a copy returning None logs talent_role_document_copy_failed and returns before client.conversations_create is called (proves AC#4 at the handler).

STEP 7 - new adapter unit tests
Create app/tests/unit/packages/talent/__init__.py, app/tests/unit/packages/talent/adapters/__init__.py and app/tests/unit/packages/talent/adapters/test_talent_drive_adapter.py, mirroring app/tests/unit/packages/incident/drive/adapters/test_incident_drive_adapter.py (patch packages.talent.adapters.google_drive.get_drive_provider with a MagicMock provider returning real OperationResult values built over DriveFile - Protocol-shaped fake data, no SDK mocking, per decisions/testing.md).
Cases: create_role_folder success returns {"id","name"} and calls the provider with delegated_user_email=BOT_EMAIL; create_role_folder classified failure returns None; copy_template_to_role_folder success returns the DriveFile id and passes the four positional arguments plus delegation; copy_template_to_role_folder classified failure returns None; success-with-data-None boundary returns None for both functions.

STEP 8 - guardrails
cd app && uv run pytest tests/unit/packages/talent tests/modules/role tests/unit/modules/role -q; uv run ruff check .; uv run mypy packages/talent modules/role; uv run python bin/check_sdk_typing.py. No baseline file edits (verified above).

AC TRACEABILITY
AC#1 (packages/talent exists, built on get_drive_provider, no direct GoogleDriveProvider) -> Steps 1, 2; proven by Step 7's tests patching get_drive_provider.
AC#2 (adapter owns SRE_BOT_EMAIL; role.py drops BOT_EMAIL/ROLE_SCOPES and the google_drive import) -> Steps 2, 3; proven by Step 7's delegation assertions and Step 6's removal of the BOT_EMAIL patches.
AC#3 (role.py calls the adapter for folder + seven copies, order/names/log events preserved) -> Steps 4, 5; proven by Step 6's assert_has_calls and info-count assertions.
AC#4 (classified failure logs and aborts before channel creation) -> Steps 2, 4, 5; proven by Step 6's updated failure test and the new copy-failure test.
AC#5 (existing coverage preserved + new adapter tests) -> Steps 6, 7.
AC#6 (gates pass) -> Step 8.

TEST MATRIX
Happy path: adapter create/copy success (unit); role_view_handler end-to-end with mocked adapter creating folder, seven copies, channel, topic, invites (existing tests, repointed).
Boundary: OperationResult.success with data None -> adapter returns None; folder dict without an id is not specially handled (DriveFile.id is always a str).
Failure: classified OperationResult error on create_folder -> None + talent_drive_create_folder_failed warning + handler logs talent_role_folder_creation_failed and returns, no copies attempted; classified error on a copy -> None + talent_drive_copy_template_failed warning + handler logs talent_role_document_copy_failed and returns before conversations_create.
Not covered (intentional): Slack API failures, i18n/locale behavior, and the Google SDK itself (owned by infrastructure/drive tests from TASK-25.1.6.8.1).

ASSUMPTIONS AND DOUBTS FOR HUMAN REVIEW
(a) packages/incident/drive/ and packages/incident/drive/adapters/ shipped WITHOUT __init__.py files (verified: only documents/, scheduling/ and the umbrella have them), contrary to decisions/feature-packages.md's layout table, even though TASK-25.1.6.8.2's notes claim they were added. This plan adds them for packages/talent; the incident gap is flagged as a comment on TASK-25.1.6.8.2 and is not fixed here.
(b) delegated_user_email on the Path A DriveProvider is a Google auth-subject concept, which decisions/layers.md's 2026-09-08 portability note would normally push into the provider implementation. Not re-litigated here: the human's 2026-09-08 comment on this task explicitly sanctions passing it through the Google implementation boundary for this migration.
(c) Dropping fields="id" from the folder creation means Google returns its default field projection instead of just the id. Assumed harmless (larger response, same adapter output); verify no Drive API error at implementation time if the discovery stub types fields as required (it does not - the incident adapter already creates folders without it).
(d) role.py stays registered through the legacy hard-coded list and keeps its Slack command surface; no plugin/entry-point change (migration.md rule 5 bright line).
(e) app/tests/modules/role/test_role.py stays in the legacy tree; moving it to tests/unit/modules/role/ was considered and declined for this PR (human-decided) to keep the diff reviewable.

BLAST RADIUS AND ROLLBACK
Only the /sre talent-role modal-submission path changes. One intentional behavior change: a Drive failure now logs and aborts instead of raising an unhandled exception out of the Bolt view handler; in both the old and new behavior no Slack channel is created, so the externally visible outcome is unchanged apart from cleaner logging. app/integrations/google_workspace/google_drive.py is untouched (still consumed by modules/reports/google_groups.py and by the incident adapter's metadata pass-throughs; deletion is owned by TASK-25.1.6.10). No infrastructure/drive/, settings, terraform or CI changes. A single git revert restores today's behavior with no partial-migration state.

SIZE GATE
Production: packages/talent/__init__.py, packages/talent/adapters/__init__.py, packages/talent/adapters/google_drive.py (~65 LOC new), modules/role/role.py (~45 LOC changed) = 4 files, roughly 110 production LOC, one subsystem, no mixed mechanical/behavior refactor beyond the single flagged failure-semantics change. Comfortably inside the single-PR gate; no decomposition needed.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-08 20:12
---
2026-09-08 portability confirmation: this task can proceed unchanged against the adjusted DriveProvider. create_folder and copy_file_to_folder are shared file/folder capabilities; the role adapter preserves BOT_EMAIL by passing delegated_user_email through the Google implementation boundary, while modules/role/role.py calls only the role adapter. No metadata or other Google-only behavior is involved. Keep the adapter domain-oriented and preserve the existing return shapes and failure logging.
---

created: 2026-09-08 23:13
---
PLAN WRITTEN 2026-09-08 (task-planner), grounded against shipped main. Four human decisions taken during planning, all reflected in the rewritten Description and ACs: (1) the package home is app/packages/talent/ (flat), not packages/role/ - the module's own vocabulary is talent and migration.md rule 5 requires the concern's final home at creation; the coordinator TASK-25.1.6.8's AC#3 was updated to match. (2) The adapter owns the SRE_BOT_EMAIL delegation internally; role.py drops its BOT_EMAIL constant (AC#2 reworded from the original 'role.py passes delegated_user_email=BOT_EMAIL through unchanged' - the value reaching Google is unchanged, only who names it). (3) A classified Drive failure now logs and aborts role_view_handler early instead of raising out of the Bolt handler; new AC#4 covers it. (4) Dead ROLE_SCOPES constant is deleted. Test placement follows the TASK-25.1.6.7/.8.2 precedent: repoint app/tests/modules/role/test_role.py in place, new adapter tests under app/tests/unit/packages/talent/adapters/. Size: 4 production files, ~110 LOC - fits one PR, no decomposition.
---
<!-- COMMENTS:END -->
