---
id: TASK-25.1.6.11.1
title: >-
  Delete the dead Google Workspace vendor modules and execute helpers; relocate
  the test-only schemas
status: Done
assignee: []
created_date: '2026-09-10 17:25'
updated_date: '2026-09-10 18:04'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies: []
references:
  - decisions/outbound-clients.md
  - app/integrations/google_workspace/client.py
  - app/tests/factories/google.py
parent_task_id: TASK-25.1.6.11
priority: medium
ordinal: 181000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
First slice of TASK-25.1.6.11. Pure deletion and relocation of code with zero production consumers; no runtime behaviour change. Reviewed for completeness, not correctness.

CURRENT STATE (grep-verified on main 2026-09-10):
- integrations/google_workspace/google_calendar.py (130 LOC) and meet.py (29 LOC) have ZERO importers repo-wide. TASK-25.1.6.9 migrated their callers onto packages/incident/{scheduling,meet}/adapters and checked its 'deleted' criterion, but both files are still on disk. They are the last callers of execute_google_api_request (google_calendar.py:38, :108; meet.py:28).
- integrations/google_workspace/google_meet.py (38 LOC) is a legacy g.co/meet URL builder with zero production importers; only tests/integrations/google_workspace/test_google_meet.py imports it.
- client.py::execute_google_api_request (:176-192) becomes caller-less once the two files above go. client.py::execute_batch_request (:195-225) already has zero consumers: TASK-25.1.6.3.1 moved batch orchestration into GoogleDirectoryProvider, which classifies per-item HttpErrors via classify_google_error instead of the helper's blanket PERMANENT_ERROR/BATCH_ERRORS. Deleting both leaves OperationResult (:21) unused; logger, Any and cast stay (used by _build_service and the factories).
- integrations/google_workspace/schemas.py (145 LOC, Pydantic Name/User/Member/Group/...) has ZERO production importers. It is consumed only by tests/factories/google.py:1 and tests/test_factory_validation.py:1, whose fixtures (conftest google_groups/google_users/google_groups_w_users) are still used by tests/modules/provisioning/test_provisioning_groups.py and tests/utils/test_filters.py. Relocate it under tests/factories/, do not delete it.
- Stale references: packages/incident/scheduling/__init__.py:4 (docstring names the deleted google_calendar.py path), packages/incident/documents/adapters/google_docs.py:6 (docstring names execute_google_api_request), tests/unit/infrastructure/directory/test_google.py:1762 (test_vendor_batch_helper_is_not_imported becomes vacuous once the helper no longer exists).

NOT IN SCOPE: google_service.py (TASK-25.1.7); the vendor-package CI guardrail (sibling slice); classify_google_error (unchanged - 400s stay mapped per provider, decided 2026-09-10); GoogleDirectoryProvider residuals (standalone follow-up tasks).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 integrations/google_workspace/google_calendar.py, meet.py and google_meet.py are deleted together with tests/integrations/google_workspace/test_google_meet.py; a repo-wide grep outside backlog/ and tmp/ finds no import of or path reference to any of them
- [x] #2 integrations/google_workspace/client.py defines neither execute_google_api_request nor execute_batch_request and does not import OperationResult; their tests are removed and a repo-wide grep for both names outside backlog/ and tmp/ returns zero hits
- [x] #3 schemas.py is relocated under app/tests/factories/; tests/factories/google.py and tests/test_factory_validation.py import it from there and no file under app/ imports integrations.google_workspace.schemas
- [x] #4 app/integrations/google_workspace/ contains only __init__.py, client.py and google_service.py (the last removed by TASK-25.1.7)
- [x] #5 ruff, mypy, pytest tests --ignore=tests/smoke, bin/check_sdk_typing.py and bin/check_deprecated_infra_client_imports.py pass with no behaviour change
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (grep/read-verified on main 2026-09-10; line numbers are from that snapshot - re-grep before editing)
- integrations/google_workspace/ holds: __init__.py (empty), client.py (225), google_calendar.py (130), google_meet.py (38), google_service.py (273, TASK-25.1.7), meet.py (29), schemas.py (145). No settings.py (Google settings stay in infrastructure/configuration/integrations/google.py until TASK-24).
- execute_google_api_request callers: google_calendar.py:38, :108 and meet.py:28 only - both files have zero importers. execute_batch_request: zero callers. OperationResult is used in client.py only by execute_batch_request.
- schemas.py importers: tests/factories/google.py:1, tests/test_factory_validation.py:1 only. Fixtures built on them are used by tests/modules/provisioning/test_provisioning_groups.py and tests/utils/test_filters.py.
- No references in .github/, .claude/, decisions/ or docs (rg --hidden).

STEP 1 - delete the orphaned vendor modules
Pre-flight (re-run immediately before deleting): rg -n --hidden -g '!backlog/**' -g '!tmp/**' -g '!**/.venv/**' 'integrations[./]google_workspace[./](google_calendar|meet|google_meet)\b|google_workspace import (google_calendar|meet|google_meet)\b|create_google_meet'. Qualify patterns with the vendor path: packages/incident/scheduling/adapters/google_calendar.py and packages/incident/meet/adapters/google_meet.py are the live replacements and share the bare file names.
Delete app/integrations/google_workspace/google_calendar.py, meet.py, google_meet.py and app/tests/integrations/google_workspace/test_google_meet.py. Leave test_google_service.py for TASK-25.1.7.

STEP 2 - client.py execute helpers
app/integrations/google_workspace/client.py: delete execute_google_api_request (:176-192), execute_batch_request (:195-225) and `from infrastructure.operations.result import OperationResult` (:21). Keep structlog/logger (still used at :127), Any, cast and the TYPE_CHECKING AdminDirectoryResource import (used by get_admin_directory_service). OperationStatus stays (classify_google_error).
app/tests/unit/integrations/google_workspace/test_client.py: delete the four test_execute_google_api_request_* tests (:289-347). MagicMock (:110, :160, :249) and HttpError stay in use.
app/tests/unit/infrastructure/directory/test_google.py: delete test_vendor_batch_helper_is_not_imported (:1762-1764). It asserts the provider module lacks a symbol that no longer exists anywhere; the vendor-package guardrail (sibling slice) takes over preventing regrowth.

STEP 3 - relocate schemas.py
Move app/integrations/google_workspace/schemas.py to app/tests/factories/google_schemas.py with content unchanged. Update imports in app/tests/factories/google.py:1 and app/tests/test_factory_validation.py:1 to `from tests.factories.google_schemas import ...`. Both are legacy test files: minimal import edit only, per testing-standards; do not migrate them. Rejected alternative: merging the models into tests/factories/google.py, which would make the move unreviewable as a pure relocation.

STEP 4 - stale references in docstrings
app/packages/incident/scheduling/__init__.py:3-4: replace the ``integrations/google_workspace/google_calendar.py`` path with "the Google Workspace vendor package", keeping the decisions/migration.md rule 5 rationale.
app/packages/incident/documents/adapters/google_docs.py:6: drop the "(no execute_google_api_request)" parenthetical and keep the sentence grammatical (read lines 1-12 first).

STEP 5 - verification (from app/)
- AC#1: rg -n --hidden -g '!backlog/**' -g '!tmp/**' -g '!**/.venv/**' 'google_workspace[./](google_calendar|meet|google_meet)\b|google_workspace import (google_calendar|meet|google_meet)\b|create_google_meet' .. -> zero hits
- AC#2: same rg over 'execute_google_api_request|execute_batch_request' -> zero hits
- AC#3: same rg over 'google_workspace[./]schemas|google_workspace import schemas' -> zero hits
- AC#4: ls integrations/google_workspace -> __init__.py client.py google_service.py
- AC#5: uv run ruff check . ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' ; uv run pytest tests --ignore=tests/smoke ; uv run python bin/check_sdk_typing.py ; uv run python bin/check_deprecated_infra_client_imports.py

AC TRACEABILITY
AC#1 -> Steps 1, 4; evidence: Step 5 grep plus a clean pytest collection.
AC#2 -> Steps 2, 4; evidence: Step 5 grep; remaining test_client.py tests (factories, retry request builder, classify_google_error) pass.
AC#3 -> Step 3; evidence: Step 5 grep; test_factory_validation.py, test_provisioning_groups.py and test_filters.py pass.
AC#4 -> Steps 1-3; evidence: ls.
AC#5 -> Step 5.

TEST MATRIX
No new tests: the slice removes code with no consumers. Regression proof comes from existing suites:
- Vendor contract intact: tests/unit/integrations/google_workspace/test_client.py - factories with the delegated subject, construction-time retry request builder, classify_google_error for mapped (404, 401/403, 429/5xx with and without retry-after) and unmapped statuses and non-HttpError.
- Replacement adapters unaffected: the packages/incident scheduling, meet and documents adapter tests, and GoogleDirectoryProvider batch tests in tests/unit/infrastructure/directory/test_google.py.
- Relocated models still back the fixtures: tests/test_factory_validation.py, tests/modules/provisioning/test_provisioning_groups.py, tests/utils/test_filters.py.
- Missed consumer: full pytest collection plus mypy fail on any dangling import.
Tests deleted, each covering only a removed symbol: the four execute_google_api_request tests, test_google_meet.py, test_vendor_batch_helper_is_not_imported.

ASSUMPTIONS AND DOUBTS
(a) google_calendar.py and meet.py are dead even though TASK-25.1.6.9 checked their deletion: verify with the Step 1 pre-flight grep, which includes string patch targets. A concurrent branch could re-add a consumer, so re-run it just before deleting.
(b) create_google_meet has no dynamic reference (command registry, getattr, entry point): covered by the create_google_meet term in the pre-flight grep.
(c) schemas.py imports only pydantic/stdlib: check its import block. If it imports app code, the move still works because tests import app modules, but note it.
(d) The google_workspace package __init__.py re-exports nothing (verified empty), so no import path other than the module path exists.
(e) tests/factories/google_schemas.py is a support module, not a test module, so the test_<domain>_<entity>_<action>.py naming rule does not apply. It follows the existing tests/factories/<vendor>.py convention.

BLAST RADIUS AND ROLLBACK
Runtime impact: none. No production importer of any deleted or moved symbol exists. A missed consumer shows up as an ImportError at pytest collection or mypy, both CI gates, before merge. A single git revert restores everything. No settings, env vars, terraform or CI changes. Independent of TASK-25.1.7 (google_service.py untouched) and of TASK-25.1.6.14/.15 (they modify only the factory half of client.py; expect at most a trivial rebase conflict).

SIZE GATE
Production: 7 files. 4 deleted or trimmed in the vendor package (about -250 dead LOC), 1 moved verbatim to tests (145 LOC), 2 one-line docstring edits. Tests: 5 files (1 deleted, 2 trimmed, 2 one-line import edits). One subsystem, one change kind (deletion and relocation). Inside the gate.
<!-- SECTION:PLAN:END -->
