---
id: TASK-25.2.3.2.4
title: >-
  Delete the dead AWS access-request flow and request_aws_account_access, flip
  healthcheck lambda, delete integrations/aws/identity_store.py, prune guard
  baselines
status: To Do
assignee: []
created_date: '2026-09-11 20:56'
updated_date: '2026-09-14 14:08'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.3.2.1
  - TASK-25.2.3.2.2
  - TASK-25.2.3.2.3
references:
  - app/modules/aws/aws.py
  - app/jobs/scheduled_tasks.py
  - app/integrations/aws/identity_store.py
  - app/bin/baselines/sdk_typing_antipatterns.txt
  - app/bin/baselines/vendor_package_contract.txt
  - decisions/outbound-clients.md
  - app/modules/aws/aws_access_requests.py
  - app/jobs/revoke_aws_sso_access.py
  - .devcontainer/dynamodb-create.sh
  - app/bin/seed.sh
  - app/bin/db.sh
parent_task_id: TASK-25.2.3.2
priority: high
ordinal: 197000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 (contract, final) of TASK-25.2.3.2 (split 2026-09-11 under the single-PR size gate; re-scoped 2026-09-14). Must land after slices 1-3, once no live production caller of integrations.aws.identity_store remains.

Human decisions carried over: request_aws_account_access is dead code (no production caller; confirmed by rg) and is deleted with its three pinned tests, along with the now-unused get_account_id_by_name import in modules/aws/aws.py; the scheduled_tasks.py 'aws' healthcheck registration becomes 'lambda: build_identity_center_adapter().healthcheck().is_success', mirroring the existing maxmind pattern at the same call site.

Re-scope 2026-09-14 (human decisions):
- The AWS account access-request flow is DELETED, not migrated, and no code parity is kept. It is not operational in production: /aws access is labelled "currently disabled", jobs/revoke_aws_sso_access.py is not registered in jobs/scheduled_tasks.py and only processes rows that flow writes, and packages/access will re-provide the capability. Removing a dead Slack command inside a frozen module is recorded as a bug-fix-shaped change under decisions/migration.md rule 1; there is no ADR amendment and no pre-deletion smoke test. The characterized defects in this flow (access_view_handler's unreachable 'is None' guard; the revoke job forwarding a failed lookup) are resolved by this deletion, not fixed.
- Production deletions: app/modules/aws/aws_access_requests.py and app/jobs/revoke_aws_sso_access.py. In app/modules/aws/aws.py: the 'Access to AWS accounts' docstring line (:4), the aws_access_requests import (:20), the '(currently disabled)' /aws access help-text lines (:48-51), bot.view("aws_access_view") (:64) and the `case "access":` branch (:102-103). A typed `/aws access` then falls to the existing 'Unknown command' reply. With request_aws_account_access also gone, aws.py imports nothing from integrations.aws and drops out of TASK-25.2.4's caller list.
- Test deletions: tests/unit/modules/aws/test_aws_access_requests_handler.py; tests/unit/jobs/test_revoke_aws_sso_access.py; tests/integration/jobs/test_revoke_aws_sso_access_integration.py; test_should_open_access_modal_when_access_command_given in test_aws_command_handler.py (:64); test_modules_aws_access_requests_dynamodb_endpoint_matrix and its aws_access_requests import in tests/unit/integrations/aws/test_dynamodb_local_endpoint.py. The docstrings in test_aws_command_registration.py that say register() calls bot.view() twice (aws_access_view, aws_health_view) are corrected to the single aws_health_view registration.
- Local-dev table cleanup: the aws_access_requests block in .devcontainer/dynamodb-create.sh (:42-59); seed_aws_request (:138-184), its aws-request usage/example lines (:24-26, :35-36) and its `aws-request)` case branch (~:201) in app/bin/seed.sh; the aws_access_requests example line in app/bin/db.sh (:27).
- Out of scope: terraform/dynamodb.tf (aws_access_requests_table and its entry in the aws_backup_selection resources) and terraform/iam.tf:51. A separate follow-up task that depends on this one owns them, so data retention and backup recovery points can be checked before the prod table is destroyed. README.md:21 ("Manage AWS access requests and approvals") describes the capability packages/access delivers and stays. The organizations/sso_admin mirrors are not deleted here: ops_group_assignment, spending and aws_account_health still use them (TASK-25.2.4).
- Size gate: the human knowingly overrode it on 2026-09-14. Roughly 820 production lines are deleted across ~6 app files plus 3 shell scripts, together with ~1,300+ test lines. They stay in one PR because every change is dead-code removal or the one-line healthcheck flip; no live behaviour changes beyond that flip.

Then integrations/aws/identity_store.py and tests/integrations/aws/test_identity_store.py (890 lines) are deleted outright, and the identity_store lines are removed from bin/baselines/sdk_typing_antipatterns.txt and bin/baselines/vendor_package_contract.txt. tests/integration/integrations/aws/test_identity_store_conformance.py exercises packages/access's own adapter via moto and never imports the legacy module -- it stays untouched, as does packages/access.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/aws/aws.py no longer defines request_aws_account_access, imports get_account_id_by_name, integrations.aws.identity_store or aws_access_requests, registers aws_access_view, routes an 'access' action, or lists /aws access in its help text; the three pinned request_aws_account_access tests and the access-modal routing test in test_aws_command_handler.py are deleted
- [ ] #2 modules/aws/aws_access_requests.py, jobs/revoke_aws_sso_access.py, test_aws_access_requests_handler.py, test_revoke_aws_sso_access.py and test_revoke_aws_sso_access_integration.py are deleted, as is the aws_access_requests case in test_dynamodb_local_endpoint.py; a grep of app/ for aws_access_requests, revoke_aws_sso_access and aws_access_view returns zero hits
- [ ] #3 The local aws_access_requests table is gone from .devcontainer/dynamodb-create.sh, app/bin/seed.sh (seed_aws_request plus its usage and case entries) and app/bin/db.sh, and bash -n passes on all three; terraform/ is untouched
- [ ] #4 jobs/scheduled_tasks.py's 'aws' healthcheck entry is 'lambda: build_identity_center_adapter().healthcheck().is_success', and no longer imports integrations.aws.identity_store; the integration test in test_scheduled_tasks_integration.py is retargeted to patch build_identity_center_adapter
- [ ] #5 integrations/aws/identity_store.py and tests/integrations/aws/test_identity_store.py are deleted; the identity_store lines are removed from bin/baselines/sdk_typing_antipatterns.txt and bin/baselines/vendor_package_contract.txt; test_identity_store_conformance.py and packages/access are untouched
- [ ] #6 ruff, mypy (no new errors), pytest, make check-sdk-typing and make check-vendor-package-contract pass with output recorded; a repo-wide grep shows zero references to integrations.aws.identity_store anywhere in app/
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-14 14:08
---
2026-09-14 re-scope (human decisions): this task now also deletes the whole dead AWS access-request flow (aws_access_requests.py, /aws access, jobs/revoke_aws_sso_access.py) with no code parity, plus its local-dev table setup. That flow is not operational in production, and packages/access re-provides the capability. The work was placed here rather than in a new subtask by explicit human choice, overriding the ~400 production LOC size gate because all of it is dead-code removal. Terraform (dynamodb.tf table and backup selection, iam.tf:51) is excluded and moves to a separate follow-up task that depends on this one. ACs rewritten: new #1-#3 cover aws.py, the dead flow and the local scripts; the old #2-#4 become #4-#6 unchanged. Needs a fresh /plan-task pass before implementation.
---
<!-- COMMENTS:END -->
