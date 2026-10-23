---
id: TASK-25.2.6.1
title: Delete the zero-consumer AWS sqs.py and schemas.py mirrors
status: Done
assignee: []
created_date: '2026-09-18 15:33'
updated_date: '2026-09-18 15:52'
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
- [x] #1 integrations/aws/sqs.py and integrations/aws/schemas.py are deleted
- [x] #2 tests/integrations/aws/test_sqs.py is deleted; no other test references integrations.aws.sqs or integrations.aws.schemas
- [x] #3 bin/baselines/vendor_package_contract.txt no longer lists module:integrations/aws/sqs.py or module:integrations/aws/schemas.py, and bin/baselines/sdk_typing_antipatterns.txt no longer lists integrations/aws/sqs.py
- [x] #4 ruff, mypy and pytest tests --ignore=tests/smoke pass; make check-vendor-package-contract and make check-sdk-typing output is recorded in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
STEPS
1. Delete app/integrations/aws/sqs.py (99 lines: get_queue_url, send_message, receive_message, delete_message, all @handle_aws_api_errors-decorated, all calling execute_aws_api_call).
2. Delete app/integrations/aws/schemas.py (93 lines: ExternalId, Group, GroupsListResponse, NameObject, Email, Address, PhoneNumber, User, UsersListResponse, MemberIdObject, GroupMembership, GroupMembershipsListResponse).
3. Delete app/tests/integrations/aws/test_sqs.py (315 lines) — its only subject is gone.
4. Prune both guard baselines of the entries this slice's deletions make stale (the guards report stale entries but never fail on them, so the prune is manual):
   - app/bin/baselines/vendor_package_contract.txt: remove `module:integrations/aws/schemas.py` and `module:integrations/aws/sqs.py`. Leave `module:integrations/aws/shield.py` and `operation-result:integrations/aws/shield.py` for TASK-25.2.6.2.
   - app/bin/baselines/sdk_typing_antipatterns.txt: remove `integrations/aws/sqs.py` (added 2026-09-18, human decision: the stale entry belongs to the slice that makes it stale). Leave `integrations/aws/client.py` for TASK-25.2.6.2.
5. Confirm app/tests/integrations/aws/test_legacy_aws_client.py (client.py's own legacy-tier tests) is untouched here — it stays until TASK-25.2.6.2 deletes the functions it tests.
6. Confirm app/integrations/aws/client.py is untouched in this slice: execute_aws_api_call, handle_aws_api_errors etc. still exist (now with zero non-test callers, since sqs.py — their last production-shaped caller — is gone), ready for TASK-25.2.6.2 to delete next.

AC TRACEABILITY
- AC#1 (sqs.py/schemas.py deleted) -> steps 1-2.
- AC#2 (test_sqs.py deleted, no dangling references) -> step 3; verify with `grep -rn "integrations.aws.sqs\|integrations.aws.schemas" app/` returning zero hits.
- AC#3 (both baselines pruned of sqs/schemas) -> step 4; verify with `make check-vendor-package-contract` and `make check-sdk-typing`, neither reporting a stale sqs/schemas entry.
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
cd app && make check-sdk-typing
Record command output in --notes. The 6 SNS/google-directory order-dependent failures in the single-process pytest run are known (TASK-90) and pre-existing; call them out explicitly if seen, do not fix them here.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-09-18.

CHANGES
- Deleted app/integrations/aws/sqs.py, app/integrations/aws/schemas.py and app/tests/integrations/aws/test_sqs.py.
- app/bin/baselines/vendor_package_contract.txt: removed module:integrations/aws/schemas.py and module:integrations/aws/sqs.py.
- app/bin/baselines/sdk_typing_antipatterns.txt: removed integrations/aws/sqs.py (plan amended 2026-09-18). Only integrations/aws/client.py remains, for TASK-25.2.6.2.
- No other file changed. client.py still has its legacy tier, now with no caller outside tests/integrations/aws/test_legacy_aws_client.py.

PRE-DELETE CHECKS (plan doubts resolved). rg for integrations.aws.sqs / integrations.aws.schemas / from integrations.aws import across app/ (not .venv): only test_sqs.py. rg for aws/sqs, aws.sqs, aws/schemas, aws.schemas in non-Python files repo-wide: only the two baselines. integrations/aws/__init__.py re-exports neither. Remaining 'sqs' string hits are the unrelated RETRY_BACKEND option and a shield test.

VERIFICATION (from app/)
- uv run ruff check . -> All checks passed!
- make check-vendor-package-contract -> OK: no net-new vendor-package contract violations (18 baselined entry(ies) remain).
- make check-sdk-typing -> OK: no net-new SDK anti-patterns (1 baselined file(s) remain).
- rg 'integrations\.aws\.(sqs|schemas)' . -> no hits.
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 78 errors in 27 files (checked 355 source files). All pre-existing, in files this change does not touch (modules/incident, modules/webhooks, integrations/slack, infrastructure/resilience, etc.); none in integrations/aws. mypy is not blocking yet (TASK-16).
- uv run pytest tests --ignore=tests/smoke -> 6 failed, 3555 passed. The 6 failures are the known order-dependent ones from the single-process run (TASK-90): 3 in tests/modules/webhooks/test_webhooks_aws_sns.py and 3 in tests/unit/infrastructure/directory/test_google.py. Not caused or touched here.

No new tests: pure deletion of dead code and its own test file (see plan TEST MATRIX).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-18 15:47
---
2026-09-18 (human decision): plan step 4 and AC#3 now also prune integrations/aws/sqs.py from sdk_typing_antipatterns.txt, which the original plan missed. The stale entry belongs to the slice that makes it stale. Step 4 now names entries instead of line numbers (sqs.py was on line 10, not 9). TASK-25.2.6.2 is reworded to match.
---
<!-- COMMENTS:END -->
