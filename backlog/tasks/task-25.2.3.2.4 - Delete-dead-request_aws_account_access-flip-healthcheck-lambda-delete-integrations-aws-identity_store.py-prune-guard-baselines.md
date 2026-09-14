---
id: TASK-25.2.3.2.4
title: >-
  Delete dead request_aws_account_access, flip healthcheck lambda, delete
  integrations/aws/identity_store.py, prune guard baselines
status: To Do
assignee: []
created_date: '2026-09-11 20:56'
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
parent_task_id: TASK-25.2.3.2
priority: high
ordinal: 197000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 (contract, final) of TASK-25.2.3.2 (split 2026-09-11 under the single-PR size gate). Must land after slices 1-3, once no production caller of integrations.aws.identity_store remains. Human decisions carried over: request_aws_account_access is dead code (no production caller; confirmed by rg) and is deleted with its three pinned tests, along with the now-unused get_account_id_by_name import in modules/aws/aws.py; the scheduled_tasks.py 'aws' healthcheck registration becomes 'lambda: build_identity_center_adapter().healthcheck().is_success', mirroring the existing maxmind pattern at the same call site. Then integrations/aws/identity_store.py and tests/integrations/aws/test_identity_store.py (890 lines) are deleted outright, and the identity_store lines are removed from bin/baselines/sdk_typing_antipatterns.txt and bin/baselines/vendor_package_contract.txt. tests/integration/integrations/aws/test_identity_store_conformance.py exercises packages/access's own adapter via moto and never imports the legacy module -- it stays untouched, as does packages/access.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/aws/aws.py no longer defines request_aws_account_access, and no longer imports get_account_id_by_name or integrations.aws.identity_store; the three pinned request_aws_account_access tests in test_aws_command_handler.py are deleted
- [ ] #2 jobs/scheduled_tasks.py's 'aws' healthcheck entry is 'lambda: build_identity_center_adapter().healthcheck().is_success', and no longer imports integrations.aws.identity_store; the integration test in test_scheduled_tasks_integration.py is retargeted to patch build_identity_center_adapter
- [ ] #3 integrations/aws/identity_store.py and tests/integrations/aws/test_identity_store.py are deleted; the identity_store lines are removed from bin/baselines/sdk_typing_antipatterns.txt and bin/baselines/vendor_package_contract.txt; test_identity_store_conformance.py and packages/access are untouched
- [ ] #4 ruff, mypy (no new errors), pytest, make check-sdk-typing and make check-vendor-package-contract pass with output recorded; a repo-wide grep shows zero references to integrations.aws.identity_store anywhere in app/
<!-- AC:END -->
