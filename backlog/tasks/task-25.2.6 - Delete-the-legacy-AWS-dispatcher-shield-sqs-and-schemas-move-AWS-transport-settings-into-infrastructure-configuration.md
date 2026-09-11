---
id: TASK-25.2.6
title: >-
  Delete the legacy AWS dispatcher, shield, sqs, schemas and the infrastructure
  AWS settings module; prune the guard baselines
status: To Do
assignee: []
created_date: '2026-09-11 15:36'
updated_date: '2026-09-11 15:56'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.2.3
  - TASK-25.2.4
  - TASK-25.2.5
references:
  - app/integrations/aws/client.py
  - app/integrations/aws/settings.py
  - app/integrations/aws/shield.py
  - app/integrations/aws/sqs.py
  - app/integrations/aws/schemas.py
  - app/infrastructure/configuration/integrations/aws.py
  - app/infrastructure/configuration/integrations/__init__.py
  - app/packages/access/sync/adapters/aws_identity_center.py
  - app/bin/check_vendor_package_contract.py
  - app/bin/check_sdk_typing.py
  - decisions/outbound-clients.md
parent_task_id: TASK-25.2
priority: high
ordinal: 123000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 5 (final) of TASK-25.2. With no mirror module left, remove from integrations/aws/client.py: handle_aws_api_errors, execute_aws_api_call, paginator, assume_role_session, get_aws_service_client and the module-level constants re-exported from settings (SYSTEM_ADMIN_PERMISSIONS, VIEW_ONLY_PERMISSIONS, AWS_REGION, THROTTLING_ERRS, RESOURCE_NOT_FOUND_ERRS). Delete integrations/aws/shield.py (this executes TASK-25.5: zero production consumers), sqs.py (zero consumers) and schemas.py (unused Pydantic models). integrations/aws/settings.py STAYS: it is the colocated home of all AWS settings until TASK-88 (human decision 2026-09-11); shield.py's AWSSettings usage is simply removed with shield.

Retire infrastructure/configuration/integrations/aws.py and its AwsSettings/get_aws_settings export from infrastructure/configuration/integrations/__init__.py (that barrel is why AWS settings were moved out of infrastructure/configuration). Its last reader is packages/access/sync/adapters/aws_identity_center.py (SERVICE_ROLE_MAP and INSTANCE_ID); since TASK-25.2.2 gives integrations/aws/settings.py the same field names, repoint that single import line and nothing else in packages/access. Small direct edits to packages/access for this repoint are fine; the access feature is not enabled yet, so anything beyond keeping it importing and passing its tests is out of scope.

Tests deleted: tests/unit/integrations/aws/{test_executor,test_shield}.py, tests/integrations/aws/{test_sqs,test_legacy_aws_client}.py, tests/smoke/integrations/aws/test_shield_smoke.py; the AWS entries in tests/unit/infrastructure/configuration/test_integration_settings_singletons.py go with the infrastructure module; tests/unit/integrations/aws/conftest.py keeps its AWSSettings fixture for client.py tests.

Guardrails: bin/baselines/vendor_package_contract.txt and bin/baselines/sdk_typing_antipatterns.txt end with no integrations/aws entries; make check-vendor-package-contract, make check-sdk-typing and make client-usage-matrix are run and their output recorded. decisions/outbound-clients.md gets at most one short dated sentence if the eager AssumeRole choice needs recording.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/aws/ contains only __init__.py, client.py and settings.py; client.py exports get_aws_client and classify_aws_error only
- [ ] #2 shield.py, sqs.py, schemas.py and the listed tests are deleted; grep -rn shield app/integrations returns zero code hits
- [ ] #3 infrastructure/configuration/integrations/aws.py and its barrel export are deleted, with packages/access repointed to integrations/aws/settings.py
- [ ] #4 Both guard baselines have no integrations/aws entries and the three make checks pass with output recorded in notes
<!-- AC:END -->
