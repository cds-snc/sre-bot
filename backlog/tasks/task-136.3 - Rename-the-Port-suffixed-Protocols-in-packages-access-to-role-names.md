---
id: TASK-136.3
title: Rename the Port-suffixed Protocols in packages/access to role names
status: In Progress
assignee: []
created_date: '2026-10-02 00:38'
updated_date: '2026-10-02 13:23'
labels:
  - plugin-architecture
  - naming
milestone: m-7
dependencies: []
references:
  - decisions/feature-packages.md
  - .claude/skills/type-model-boundaries/SKILL.md
  - app/packages/access/request/service.py
parent_task_id: TASK-136
priority: medium
ordinal: 300000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-136. Applies the Protocol naming rule to packages/access: the three public Protocols (AccessRequestServicePort in request/service.py, CatalogServicePort in catalog/service.py, AccessSyncApplicationServicePort in sync/application.py) and the six route-local ones in the three interactions/http.py modules (_AccessRequestSettingsPort, _AccessRequestServicePort, _AccessSyncSettingsPort, _AccessSyncApplicationServicePort, _CatalogSettingsPort, _CatalogServicePort) get role names that do not collide with the concrete service classes. The new names, and whether the route-local twins are kept or collapsed into the public Protocols, are decided by the human and recorded in this task's plan; the plan is intentionally empty until then. Mechanical rename only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every Port-suffixed Protocol under packages/access has a role name that does not collide with the concrete service classes (AccessRequestService, CatalogService, AccessSyncApplicationService), or, where the plan records that a route-local twin is removed, no longer exists; rg finds no Protocol class ending in Port under app/packages/access and no importer of an old name
- [x] #2 The test that asserts the sync ingress dependency type by class-name string (tests/unit/packages/access/sync/test_access_sync_application_service_naming.py) and the other access tests that name these Protocols are updated in place to the new names, with the same assertions on behaviour and signatures
- [x] #3 Docstrings and comments in the touched access files say 'interface' instead of 'port'
- [x] #4 No behaviour change: the TASK-36 legacy_surface suite is green with no assertion change
- [x] #5 Full CI sequence from app/ passes: ruff check, make fmt-ci check-sdk-typing check-vendor-package-contract check-aws-platform-seam check-runtime-imports check-import-contracts test, and mypy shows no new errors in touched files
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Applies the Protocol naming rule recorded by TASK-136.1 (roles, not patterns; 'interface' in prose) to packages/access. Mechanical rename inside one subsystem; no structural change.

Decisions (settled in chat 2026-10-02, not reopened here):
- Public Protocols: AccessRequestServicePort becomes AccessRequestWorkflow, CatalogServicePort becomes EntitlementCatalog, AccessSyncApplicationServicePort becomes AccessSynchronizer. A bare strip of the suffix would collide with the concrete classes AccessRequestService, CatalogService and AccessSyncApplicationService, which keep their names.
- Private route-local Protocols keep existing and take the public name with a leading underscore: _AccessRequestServicePort becomes _AccessRequestWorkflow, _CatalogServicePort becomes _EntitlementCatalog, _AccessSyncApplicationServicePort becomes _AccessSynchronizer.
- Private settings Protocols: _AccessRequestSettingsPort becomes _AccessRequestRouteSettings, _CatalogSettingsPort becomes _CatalogRouteSettings, _AccessSyncSettingsPort becomes _AccessSyncRouteSettings (the concrete slices AccessRequestsSettings, AccessCatalogSettings and AccessSyncSettings in common/settings.py are untouched).
- The twins are not collapsed here. Catalog and sync twins are method-for-method identical to the public Protocols; the request twin omits advance_from_sync_result. Collapsing them is recorded on TASK-124.1, which rewrites interactions/ into entrypoints/. It is not an access/core matter: each twin has one subdomain consumer.
- No alias or re-export at any old name.

Found call sites (rg, 2026-10-02; none of the nine new names exists in app/ today; no Makefile, .github, pyproject, app/bin or guardrail baseline names the old ones):
- Production (8 files, 47 lines): request/interactions/http.py 18 (classes at :43 and :49, module docstring :11, _require helper :154-155, _noop_request_service :160, and the settings/service Annotated parameters of six routes :184-453); catalog/interactions/http.py 9 (classes :33 and :40); sync/interactions/http.py 7 (classes :49 and :57); sync/job_runner.py 5 (:28 import, :56, :138, :248, :294 annotations); sync/interactions/ingress.py 3 (:19 import, :55, :137); request/service.py 3 (:57 class, docstrings :17 'Protocol port' and :61 naming the sync Protocol); catalog/service.py 1 (:31 class); sync/application.py 1 (:42 class).
- Tests (3 files, 5 lines plus two test names): tests/unit/packages/access/sync/test_access_sync_application_service_naming.py :15 hasattr(module, 'AccessSyncApplicationServicePort'), :36 __name__ comparison, :30 test name ..._uses_application_service_port; tests/unit/packages/access/request/test_access_request_package_init.py :12 import, :149 getattr, :138 test name test_access_request_service_port_...; tests/unit/packages/access/sync/test_access_sync_routes.py docstrings :33 and :57.

Steps:
1. Tests first, in place: the naming test asserts hasattr(module, 'AccessSynchronizer'), that the old name is absent, and that the ingress coordinator type is named 'AccessSynchronizer' (test renamed ..._uses_access_synchronizer); the package-init test imports AccessRequestWorkflow (test renamed test_access_request_workflow_uses_parameterized_operation_result_returns). Both fail until steps 2-3. Same assertions on signatures and behaviour; only the names change.
2. Rename the three public Protocols in request/service.py, catalog/service.py and sync/application.py, and their importers (sync/job_runner.py, sync/interactions/ingress.py). Reword request/service.py:17 ('Protocol interface') and :61.
3. Rename the six private Protocols in the three interactions/http.py modules (whole-token replace per name), and the module docstring at request/interactions/http.py:11.
4. Fix the two docstrings in test_access_sync_routes.py.
5. rg for 'Port\b' class names and '_port\b' under app/packages/access and app/tests/**/access returns nothing.

Test matrix: the existing access unit and integration suites (routes, ingress, job runner, package init, naming) and tests/integration/legacy_surface are the behaviour guard. No new test file: the naming test already pins the public sync name and gains the absence check.

Verify (from app/): uv run ruff check .; make fmt-ci check-sdk-typing check-vendor-package-contract check-aws-platform-seam check-runtime-imports check-import-contracts test; mypy with no new errors in touched files; rg -n '\w+Port\b' app/packages/access (empty); the OpenAPI schema is unchanged (the Protocols are dependency annotations, not response models: compare app.openapi() before and after, or the existing schema test if one covers access).

AC map: #1 steps 2-3 + rg; #2 steps 1 and 4; #3 steps 2-4 (rg -i '\bport\b' over the touched files is empty); #4 legacy_surface unchanged; #5 gates.

Size: 8 production files, about 47 changed lines, one subsystem (packages/access); 3 test files edited. Under the gate.
Behaviour: none. The Protocols are structural and used only as annotations; FastAPI resolves the dependencies from the Depends(...) callables, not from the annotation names.
Blast radius: packages/access only; a missed importer fails at import and is caught by collection and mypy. Rollback: git revert.
Ordering: independent of TASK-136.2 (no shared file). Depends on TASK-136.1 only for the recorded rule.

Doubts to verify: (1) FastAPI treats Annotated[_Protocol, Depends(fn)] by the Depends callable only, so renaming the annotation changes no OpenAPI component name (check the generated schema). (2) No test stub or patch string names a private Protocol beyond the two docstrings found (re-run rg over app/tests).

Amendments after re-checking the tree at f182ecd2 (2026-10-02, after TASK-136.2):
- Call sites unchanged: 8 production files, 47 lines; catalog/interactions/http.py classes are at :34 and :40. None of the nine new names exists in app/.
- request/service.py carries 'from __future__ import annotations' (deprecated under the CPython 3.14 baseline). It is removed in this task because the file is touched. Its TYPE_CHECKING-only imports (DirectoryMember, DirectoryProvider) stay valid under lazy annotations; test_access_request_package_init.py calls get_type_hints on six Protocol methods and guards this.
- test_access_sync_application_service_naming.py: the module docstring ('Fail-first naming tests for Sprint 1 ...') and the 'renamed' wording in two test docstrings carry a sprint label and transitory state; they are reworded to describe the observable behaviour while the file is edited.
- Step 1 as written asserts the old name is absent, and step 5 expects rg for 'Port' names under the access tests to be empty. Both cannot hold if the old name is a string literal in the test. Which one gives way is the human's call at plan approval.
- Baselines taken before any edit: OpenAPI schema of the three access routers (35011 bytes, contains none of the Protocol names); pytest tests/unit/packages/access + tests/integration/legacy_surface 355 passed; mypy on packages/access plus the three test files 15 errors in 2 files, none in packages/access; IncidentChannelPort / get_incident_channel_port 53 occurrences in 13 files.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
What changed (mechanical rename inside packages/access, no behaviour change, no alias at any old name):
- Public Protocols: AccessRequestServicePort -> AccessRequestWorkflow (request/service.py), CatalogServicePort -> EntitlementCatalog (catalog/service.py), AccessSyncApplicationServicePort -> AccessSynchronizer (sync/application.py), with the importers sync/job_runner.py and sync/interactions/ingress.py.
- Route-local Protocols in the three interactions/http.py modules: _AccessRequestServicePort -> _AccessRequestWorkflow, _CatalogServicePort -> _EntitlementCatalog, _AccessSyncApplicationServicePort -> _AccessSynchronizer, _AccessRequestSettingsPort -> _AccessRequestRouteSettings, _CatalogSettingsPort -> _CatalogRouteSettings, _AccessSyncSettingsPort -> _AccessSyncRouteSettings. The twins are kept (collapse is TASK-124.1).
- request/service.py: module docstring says 'Protocol interface'; the deprecated 'from __future__ import annotations' is removed.
- Tests edited in place, same assertions: test_access_sync_application_service_naming.py (new name in the hasattr and __name__ checks, test renamed ..._uses_access_synchronizer, sprint label and 'renamed' wording dropped from docstrings); test_access_request_package_init.py (import, getattr, test renamed test_access_request_workflow_...); test_access_sync_routes.py (two stub docstrings). Both edited tests failed before the production rename (ImportError on AccessRequestWorkflow at collection). No absence assertion, per the approval decision.
- 8 production files, 3 test files; 47 production lines plus the future-import removal.

Evidence (2026-10-02, from app/, on f182ecd2 plus this change):
- AC1: rg -n '\w+Port\b' packages/access tests/unit/packages/access -> no match; rg for the nine old names over app/ -> no match.
- AC2: the three test files above; pytest tests/unit/packages/access green inside the full run.
- AC3: rg -n -i '\bport\b|_port\b' packages/access tests/unit/packages/access -> no match.
- AC4: pytest tests/integration/legacy_surface -> 17 passed; no file under tests/integration changed.
- AC5: ruff check . -> All checks passed. make fmt-ci check-sdk-typing check-vendor-package-contract check-aws-platform-seam check-runtime-imports check-import-contracts test -> rc 0; 783 files already formatted; import contracts 8 kept, 0 broken; 2858 passed and 760 passed. mypy on packages/access plus the three test files: 15 errors in 2 files before and after, identical once line numbers are stripped, none in packages/access or the edited tests (infrastructure/i18n and integrations/openai settings, pre-existing).
- Plan doubt 1: app.openapi() for the three access routers is byte-identical before and after (35011 bytes). Doubt 2: no test names a private Protocol beyond the two docstrings.
- IncidentChannelPort / get_incident_channel_port: 53 occurrences in 13 files, unchanged.

For the human: the change is uncommitted on feat/rename_port_suffix_protocols (HEAD f182ecd2, same commit as main); commit, PR, review, then move to Done.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-02 13:19
---
Plan approved 2026-10-02 (Guillaume Charest, in session), as written plus the appended amendments. Decision: the naming test asserts the new name only; absence of the old names is proven by rg, not by a test assertion (same as TASK-136.2).
---
<!-- COMMENTS:END -->
