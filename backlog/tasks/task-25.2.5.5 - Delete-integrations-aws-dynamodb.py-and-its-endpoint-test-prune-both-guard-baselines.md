---
id: TASK-25.2.5.5
title: >-
  Delete integrations/aws/dynamodb.py and its endpoint test; prune both guard
  baselines
status: To Do
assignee: []
created_date: '2026-09-15 20:09'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.2.5.2
  - TASK-25.2.5.3
references:
  - app/integrations/aws/dynamodb.py
  - app/tests/unit/integrations/aws/test_dynamodb_local_endpoint.py
  - app/bin/baselines/sdk_typing_antipatterns.txt
  - app/bin/baselines/vendor_package_contract.txt
parent_task_id: TASK-25.2.5
priority: high
ordinal: 218000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 5 (contract) of TASK-25.2.5, in the shape of TASK-25.2.4.7. Runs once .2 and .3 have merged and a re-grep finds no remaining reference.

- Delete app/integrations/aws/dynamodb.py (164 LOC) and app/tests/unit/integrations/aws/test_dynamodb_local_endpoint.py (the ENVIRONMENT-gate matrix for a gate that no longer exists). get_aws_client's AWS_ENDPOINT_URL_DYNAMODB gate is already covered by tests/unit/integrations/aws/test_aws_client_factory_config.py:89-102 (three tests), so no coverage moves.
- Prune app/bin/baselines/sdk_typing_antipatterns.txt:7 (integrations/aws/dynamodb.py) and vendor_package_contract.txt:8 (module:integrations/aws/dynamodb.py).
- Re-verify that no boto3.client/boto3.Session/boto3.resource construction exists in production code outside integrations/aws/client.py (true on 2026-09-15).
- Check TASK-25.2.5's ACs with a traceability note to the children, and leave its status for a human.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/aws/dynamodb.py and tests/unit/integrations/aws/test_dynamodb_local_endpoint.py no longer exist; rg over app/ (production, tests and mock.patch strings) for integrations.aws.dynamodb or 'from integrations.aws import dynamodb' returns zero hits
- [ ] #2 Neither guard baseline carries an integrations/aws/dynamodb.py entry and every other entry is unchanged; make check-sdk-typing and make check-vendor-package-contract print OK with no stale line naming it
- [ ] #3 rg for execute_aws_api_call|handle_aws_api_errors hits only integrations/aws/{client,sqs}.py, their legacy tests, bin/check_sdk_typing.py, the sdk_typing_antipatterns.txt header and decisions/sdk-typing.md, recorded in notes as owned by TASK-25.2.6; rg for boto3.(client|Session|resource) in production code hits only integrations/aws/client.py
- [ ] #4 TASK-25.2.5's ACs are checked with a traceability note to its children and its status is left for a human; ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass with output recorded
<!-- AC:END -->
