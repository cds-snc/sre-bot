---
id: TASK-133
title: >-
  Emit registry error codes from the AWS and Google classifiers, distinguishing
  UNAUTHENTICATED from FORBIDDEN
status: To Do
assignee: []
created_date: '2026-09-28 14:55'
labels:
  - operation-result
  - clients
milestone: m-7
dependencies:
  - TASK-105.2
references:
  - decisions/operation-result.md
  - decisions/outbound-clients.md
priority: medium
ordinal: 288000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/operation-result.md requires error_code to come from the project registry (TASK-105.2) and UNAUTHORIZED to distinguish UNAUTHENTICATED vs FORBIDDEN via error_code. The live vendor classifiers do not: integrations/aws/client.py::classify_aws_error returns UNAUTHORIZED with the raw botocore code (from AWSSettings catalogues) or type(exc).__name__ as error_code; integrations/google_workspace/client.py::classify_google_error maps 401 and 403 both to UNAUTHORIZED with str(http_status) as error_code. Callers therefore see vendor-specific codes and cannot tell an expired credential from a missing permission.

Make both classifiers emit registry members (UNAUTHENTICATED for 401-class, FORBIDDEN for 403-class, and registry codes for the other families), decide whether the raw vendor code is kept anywhere (for example as a structured log field or in cause) rather than as error_code, and update callers that branch on the old values. This changes the codes callers and logs see, so it ships as a standalone PR, not in a stack. OpenAI's classifier is moved onto the outbound-client contract by TASK-25.10, which should also emit registry codes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 classify_aws_error and classify_google_error return only ErrorCode registry members as error_code
- [ ] #2 401-class failures map to UNAUTHENTICATED and 403-class failures to FORBIDDEN, both with status UNAUTHORIZED, covered by unit tests per vendor
- [ ] #3 Where the raw vendor code is still needed it is recorded outside error_code (decision recorded in the PR and in decisions/operation-result.md if it sets a rule)
- [ ] #4 Every caller that compared error_code against a raw vendor value is updated; grep finds no such comparison
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
