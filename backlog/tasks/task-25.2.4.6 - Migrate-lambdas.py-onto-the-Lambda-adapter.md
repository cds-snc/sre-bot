---
id: TASK-25.2.4.6
title: Migrate lambdas.py onto the Lambda adapter
status: To Do
assignee: []
created_date: '2026-09-14 17:39'
updated_date: '2026-09-14 20:01'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.4.2
references:
  - app/modules/aws/lambdas.py
  - app/tests/unit/modules/aws/test_lambdas_handler.py
parent_task_id: TASK-25.2.4
priority: high
ordinal: 205000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2d of TASK-25.2.4. modules/aws/lambdas.py: aws_lambdas.list_functions() (line 48, checked with 'if response' but len()/iteration/dict-access at lines 50,53,54 still assume a list) and aws_lambdas.list_layers() (line 68, same shape at lines 71,74,75). Both today report 'Lambda functions/layers management is currently disabled' on any falsy response (line 57/78), conflating a real AWS error with an intentionally-empty list -- replace with the lambda adapter's OperationResult and give the Slack response a distinct message for a genuine failure (log + user-visible error) versus a confirmed-empty success.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/aws/lambdas.py no longer imports integrations.aws.lambdas; both call sites use the lambda adapter and branch on OperationResult explicitly
- [ ] #2 The two call sites that crashed on a bare False return (TASK-25.2.1 characterization) now distinguish a genuine failure (logged, distinct Slack message) from a confirmed-empty success; the pinned crash tests in tests/unit/modules/aws/test_lambdas_handler.py are replaced by tests of the new explicit-status behaviour
- [ ] #3 Per-call-site error-path behaviour is documented in the task notes for review
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Cross-reference from TASK-25.2.4.2 planning (2026-09-14): the Lambda adapter module is packages/aws_platform/adapters/aws_lambda.py (not lambda.py, because 'lambda' is a Python keyword): LambdaAdapter, build_lambda_adapter(). list_functions/list_layers return OperationResult[list[dict]] across all pages. The client is in-account with no role assumed, matching the mirror. ServiceException now classifies as TRANSIENT; InvalidParameterValueException still propagates.
<!-- SECTION:NOTES:END -->
