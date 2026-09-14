---
id: TASK-25.2.4.3
title: Migrate ops_group_assignment.py onto the Organizations and SSO-Admin adapters
status: To Do
assignee: []
created_date: '2026-09-14 17:39'
updated_date: '2026-09-14 18:35'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.4.1
references:
  - app/modules/aws/ops_group_assignment.py
  - app/tests/unit/modules/aws/test_ops_group_assignment_handler.py
parent_task_id: TASK-25.2.4
priority: high
ordinal: 202000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2a of TASK-25.2.4. modules/aws/ops_group_assignment.py already branches on OperationResult for the Identity Center adapter (lines 23-45: build_identity_center_adapter().get_group_id, .status is OperationStatus.NOT_FOUND special-cased from other failures, then .is_success/.data/.message/.error_code) -- reuse that exact caller-side pattern for the organizations and sso_admin calls. Replace: organizations.list_organization_accounts() (line 48), sso_admin.list_account_assignments_for_principal() (line 49) -- crashes today if either mirror returns False into the set/list comprehensions at line 50 and the dict lookups in the unassigned_accounts comprehension (lines 53-57); sso_admin.create_account_assignment() (line 85) -- today branches on truthy/falsy bool (line 91) which silently swallows the failure reason. Each becomes an explicit OperationResult branch with a logged/returned status on non-success, mirroring the existing get_group_id handling.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/aws/ops_group_assignment.py no longer imports integrations.aws.organizations or integrations.aws.sso_admin; all three call sites use the organizations and sso_admin adapters and branch on OperationResult explicitly
- [ ] #2 The three call sites that crashed on a bare False return (TASK-25.2.1 characterization) instead produce a logged/returned failure status; the pinned crash tests in tests/unit/modules/aws/test_ops_group_assignment_handler.py are replaced by tests of the new explicit-status behaviour
- [ ] #3 Per-call-site error-path behaviour (what happens on NOT_FOUND vs TRANSIENT_ERROR vs PERMANENT_ERROR for each of the three calls) is documented in the task notes for review
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Human decision 2026-09-14: keep ops_group_assignment migration to the bare minimum. The feature hasn't been called in at least 3 weeks and has no known active user; it will be reassessed when the business feature moves to packages/.
- create_account_assignment/delete_account_assignment keep the legacy behaviour: success is judged on the initial response Status != FAILED, with no polling of describe_account_assignment_creation_status/_deletion_status (IN_PROGRESS counts as success).
- Do only what AC#1-#3 require: swap to the adapters, add a simple explicit OperationResult branch with logging at the three call sites, and replace the pinned crash tests. No new retry, polling or UX logic.
- AC#3's per-status notes can be brief. One line per call site covering non-success (logged and handled like the existing get_group_id failure branch) is enough; there is no need to split NOT_FOUND/TRANSIENT/PERMANENT beyond what the existing pattern already does.
<!-- SECTION:NOTES:END -->
