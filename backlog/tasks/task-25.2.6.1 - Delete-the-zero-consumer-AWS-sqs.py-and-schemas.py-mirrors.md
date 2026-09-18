---
id: TASK-25.2.6.1
title: Delete the zero-consumer AWS sqs.py and schemas.py mirrors
status: To Do
assignee: []
created_date: '2026-09-18 15:33'
updated_date: '2026-09-18 15:34'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies: []
references:
  - app/integrations/aws/sqs.py
  - app/integrations/aws/schemas.py
  - app/bin/baselines/vendor_package_contract.txt
parent_task_id: TASK-25.2.6
priority: high
ordinal: 232000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
First slice of TASK-25.2.6's deletion sweep. integrations/aws/sqs.py and integrations/aws/schemas.py have zero production importers (grep-verified 2026-09-18): sqs.py is only called from its own dedicated test tests/integrations/aws/test_sqs.py, and schemas.py has no importers anywhere. Deleting them first, before client.py's legacy dispatcher tier, keeps every intermediate commit's main branch green (sqs.py currently imports execute_aws_api_call/handle_aws_api_errors from client.py, so those must outlive sqs.py by at least one slice).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/aws/sqs.py and integrations/aws/schemas.py are deleted
- [ ] #2 tests/integrations/aws/test_sqs.py is deleted; no other test references integrations.aws.sqs or integrations.aws.schemas
- [ ] #3 bin/baselines/vendor_package_contract.txt no longer lists module:integrations/aws/sqs.py or module:integrations/aws/schemas.py
- [ ] #4 ruff, mypy and pytest tests --ignore=tests/smoke pass; make check-vendor-package-contract output is recorded in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (2026-09-18 grep, repo-wide including packages/ and tests/): integrations/aws/sqs.py has exactly one production-shaped caller of its own functions — none; it is called only by tests/integrations/aws/test_sqs.py (15 @patch sites on integrations.aws.sqs.execute_aws_api_call). integrations/aws/schemas.py's 12 Pydantic models have zero importers anywhere in app/ (grep for "from integrations.aws.schemas" / "import integrations.aws.schemas" returns nothing, including in sqs.py, shield.py, client.py, settings.py). Both are already baselined as vendor-package-contract violations (bin/baselines/vendor_package_contract.txt:8,9 "module:integrations/aws/schemas.py", "module:integrations/aws/sqs.py").

STEPS
1. Delete app/integrations/aws/sqs.py (99 lines: get_queue_url, send_message, receive_message, delete_message, all @handle_aws_api_errors-decorated, all calling execute_aws_api_call).
2. Delete app/integrations/aws/schemas.py (93 lines: ExternalId, Group, GroupsListResponse, NameObject, Email, Address, PhoneNumber, User, UsersListResponse, MemberIdObject, GroupMembership, GroupMembershipsListResponse).
3. Delete app/tests/integrations/aws/test_sqs.py (315 lines) — its only subject is gone.
4. Edit app/bin/baselines/vendor_package_contract.txt: remove line 8 (module:integrations/aws/schemas.py) and line 9 (module:integrations/aws/sqs.py). Leave the shield.py module entry (line, renumbered) and the operation-result:integrations/aws/shield.py entry — shield.py is TASK-25.2.6.2's deletion, not this slice's.
5. Confirm app/tests/integrations/aws/test_legacy_aws_client.py (client.py's own legacy-tier tests) is untouched here — it stays until TASK-25.2.6.2 deletes the functions it tests.
6. Confirm app/integrations/aws/client.py is untouched in this slice: execute_aws_api_call, handle_aws_api_errors etc. still exist (now with zero non-test callers, since sqs.py — their last production-shaped caller — is gone), ready for TASK-25.2.6.2 to delete next.

AC TRACEABILITY
- AC#1 (sqs.py/schemas.py deleted) -> steps 1-2.
- AC#2 (test_sqs.py deleted, no dangling references) -> step 3; verify with `grep -rn "integrations.aws.sqs\|integrations.aws.schemas" app/` returning zero hits.
- AC#3 (baseline pruned) -> step 4; verify with `make check-vendor-package-contract`.
- AC#4 (gates green) -> run the standard suite plus the named make target.

TEST MATRIX
No new tests. This is a pure deletion of dead code and its own dedicated test file; no behavior changes, so no new test coverage is owed. Regression coverage is the full suite continuing to pass (nothing else imports these two modules).

ASSUMPTIONS AND DOUBTS
- Assumes no dynamic/string-based import of integrations.aws.sqs or integrations.aws.schemas exists (e.g. importlib, getattr(module, "sqs")) that a plain grep for the import statement forms would miss — verify by also grepping for the bare strings "aws.sqs" and "aws.schemas" repo-wide (including scripts/, jobs/, modules/) before deleting, since app/modules/aws/* was not re-checked in this slice's own research (it was checked in TASK-25.2.3/.4's own migrations, not re-verified here).
- Assumes tests/unit/integrations/aws/conftest.py's AWSSettings fixture has no fixture specifically for sqs/schemas — confirmed by its import list (AWSSettings, get_aws_settings only); no change needed there.

BLAST RADIUS AND ROLLBACK
- Two files with confirmed zero production consumers plus their own test file. A single `git revert` fully restores prior state. No config, no migration, no runtime behavior change — nothing to stage or sequence beyond TASK-25.2.6.2 depending on this landing first (client.py's execute_aws_api_call must outlive sqs.py's import of it).

VERIFICATION (run from app/)
cd app && uv run ruff check .
cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'
cd app && uv run pytest tests --ignore=tests/smoke
cd app && make check-vendor-package-contract
Record command output in --notes. The 6 SNS/google-directory order-dependent failures in the single-process pytest run are known (TASK-90) and pre-existing; call them out explicitly if seen, do not fix them here.
<!-- SECTION:PLAN:END -->
