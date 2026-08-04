---
id: TASK-25.2.3
title: >-
  Migrate AWS Lambda integration off execute_aws_api_call; delete
  integrations/aws/sqs.py
status: To Do
assignee: []
created_date: '2026-07-31 18:48'
updated_date: '2026-08-04 19:39'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.2
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/aws/lambdas.py
  - app/integrations/aws/sqs.py
parent_task_id: TASK-25.2
priority: high
ordinal: 120000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-25.2 (tiny). Migrate integrations/aws/lambdas.py off execute_aws_api_call/handle_aws_api_errors onto get_aws_client("lambda") + classify_aws_error. Sole production consumer (grep-confirmed 2026-07-31): modules/aws/lambdas.py. Also delete integrations/aws/sqs.py in this slice - zero production consumers confirmed via grep, no migration needed, pure deletion.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/aws/lambdas.py no longer calls execute_aws_api_call/handle_aws_api_errors; routes through get_aws_client("lambda") + classify_aws_error
- [ ] #2 modules/aws/lambdas.py is updated to the raise+classify contract explicitly; resulting error-path behavior documented and human-reviewed (not zero-diff, per the silent-False-swallow caveat noted in sibling slices)
- [ ] #3 integrations/aws/sqs.py is deleted
- [ ] #4 moto-backed integration conformance test(s) under app/tests/integration/ exercise integrations/aws/lambdas.py's list_functions/list_layers/get_layer_version against real Lambda semantics via moto.mock_aws() (mirroring tests/integration/infrastructure/idempotency/conftest.py's fixture pattern), additive alongside existing MagicMock-based unit tests
<!-- AC:END -->
