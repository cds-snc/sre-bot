---
id: TASK-25.2.6.2
title: >-
  Delete client.py's legacy dispatcher tier and shield.py; empty the sdk-typing
  baseline
status: In Progress
assignee: []
created_date: '2026-09-18 15:34'
updated_date: '2026-09-18 16:47'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.2.6.1
references:
  - app/integrations/aws/client.py
  - app/integrations/aws/shield.py
  - app/bin/baselines/sdk_typing_antipatterns.txt
  - app/bin/baselines/vendor_package_contract.txt
  - decisions/sdk-typing.md
parent_task_id: TASK-25.2.6
priority: high
ordinal: 233000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second slice of TASK-25.2.6's deletion sweep, depends on TASK-25.2.6.1 (sqs.py, client.py's last legacy caller, must be gone first so client.py's execute_aws_api_call/handle_aws_api_errors/assume_role_session/get_aws_service_client/paginator have zero callers before deletion). Deletes integrations/aws/client.py lines 224-432 (the block explicitly commented 'Kept only for the per-service mirror modules and deleted together with the last of them'): the five legacy re-exported constants (SYSTEM_ADMIN_PERMISSIONS, VIEW_ONLY_PERMISSIONS, AWS_REGION, THROTTLING_ERRS, RESOURCE_NOT_FOUND_ERRS) and handle_aws_api_errors/assume_role_session/get_aws_service_client/execute_aws_api_call/paginator; also removes the now-dead infrastructure.configuration.integrations.aws import (line 21) and the imports it leaves unused (functools.wraps, structlog, botocore.client.BaseClient, the module logger). Deletes integrations/aws/shield.py (AWSShield: zero production consumers, grep-verified 2026-09-18). client.py keeps get_aws_client, classify_aws_error and their private helpers only. With execute_aws_api_call and execute_google_api_call both gone repo-wide (Google side already closed per grep) and the AWSClients facade and *_next.py generation already gone, bin/baselines/sdk_typing_antipatterns.txt becomes empty of entries and decisions/sdk-typing.md's Migration section records all four tolerated anti-patterns as closed, with TASK-25 left open for the MaxMind/Slack contract work that never carried these patterns. Do not flip sdk-typing.md's applies: target status in this task — that is a separate, larger call for a human to make once MaxMind/Slack's own vendor-facade status is assessed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 integrations/aws/ contains only __init__.py, client.py and settings.py; client.py exports get_aws_client and classify_aws_error only; grep -rn shield app/integrations returns zero code hits
- [x] #2 tests/unit/integrations/aws/test_executor.py, test_shield.py, tests/integrations/aws/test_legacy_aws_client.py and tests/smoke/integrations/aws/test_shield_smoke.py are deleted
- [x] #3 bin/baselines/sdk_typing_antipatterns.txt and the shield entries in bin/baselines/vendor_package_contract.txt are empty of integrations/aws entries
- [x] #4 decisions/sdk-typing.md's Migration section records the four tolerated anti-patterns as closed, with a dated Changes line; ruff, mypy and pytest tests --ignore=tests/smoke pass; make check-sdk-typing, make check-vendor-package-contract and make client-usage-matrix output is recorded in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
STEPS
1. In app/integrations/aws/client.py: delete lines 224-432 in full (the legacy-helpers comment block through the end of the file). Delete the now-unused imports: `from functools import wraps` (line 12), `import structlog` (line 16), `from botocore.client import BaseClient` (line 17), `from infrastructure.configuration.integrations.aws import get_aws_settings as _get_legacy_aws_settings` (line 21), and the module-level `logger = structlog.get_logger()` (line 38). Leave `from typing import TYPE_CHECKING, Any, Literal, overload` as-is (Any/Literal/overload/TYPE_CHECKING all still used by get_aws_client's overloads). Run ruff after to catch anything missed (F401 unused import).
2. Delete app/integrations/aws/shield.py (124 lines: AWSShield class — __init__, client(), execute(), _classify_client_error()).
3. Delete the four now-orphaned test files: tests/unit/integrations/aws/test_executor.py, tests/unit/integrations/aws/test_shield.py, tests/integrations/aws/test_legacy_aws_client.py, tests/smoke/integrations/aws/test_shield_smoke.py.
4. Edit app/bin/baselines/sdk_typing_antipatterns.txt: remove the last data line, `integrations/aws/client.py` (TASK-25.2.6.1 already removed `integrations/aws/sqs.py`). Leave the header comment block; the file becomes header-only (zero entries), which `make check-sdk-typing` treats as passing. Do not delete bin/check_sdk_typing.py itself — its own "Retirement" docstring note ties that decision to a human reading decisions/sdk-typing.md's "migration complete" criteria, not to this task's scope.
5. Edit app/bin/baselines/vendor_package_contract.txt: remove `module:integrations/aws/shield.py` and `operation-result:integrations/aws/shield.py` (the two remaining aws lines after TASK-25.2.6.1 pruned the schemas/sqs module lines).
6. Edit decisions/sdk-typing.md's Migration section. Replace the final two sentences ("Tolerated until those close: the execute_*_api_call dispatchers, the *_next twins, the docstring-param scraper, and the AWSClients facade — each named in its owning ticket.") with text stating all four tolerated anti-patterns are now closed repo-wide (cite: no execute_aws_api_call/execute_google_api_call, no *_next.py twin, no __doc__-based parameter discovery, no AWSClients facade), while TASK-25 stays open for TASK-25.3 (MaxMind) and TASK-25.4 (Slack), which never carried these four anti-patterns. Do not change the `applies: target` frontmatter field — flag in the PR description that all of sdk-typing.md's Checks now appear to pass on main, but leave the applies-field decision to a human review (it is a broader claim than this task's grep scope covers, e.g. it doesn't re-verify MaxMind/Slack have no vendor-facade class). Add one dated Changes line: "- 2026-09-18: AWS execute_aws_api_call/AWSShield deleted (TASK-25.2.6); all four tolerated anti-patterns are closed repo-wide, TASK-25 stays open for MaxMind/Slack."

AC TRACEABILITY
- AC#1 (client.py trimmed, shield grep-clean) -> steps 1-2; verify `grep -rn shield app/integrations` returns zero, and `python3 -c "import ast,sys; ..."` or simply reading client.py confirms only get_aws_client/classify_aws_error (+ private helpers) remain.
- AC#2 (four test files deleted) -> step 3.
- AC#3 (both baselines empty of aws entries) -> steps 4-5; verify with `make check-sdk-typing` and `make check-vendor-package-contract`.
- AC#4 (ADR + gates) -> step 6 plus the verification block below.

TEST MATRIX
No new tests. Regression coverage: the full suite continuing to pass with these files gone proves nothing else depended on them. No happy-path/boundary/failure cases to add since no behavior changes — get_aws_client and classify_aws_error are untouched by this slice.

ASSUMPTIONS AND DOUBTS
- Assumes TASK-25.2.6.1 has already landed (sqs.py deleted) before this slice starts, per the --dep wiring; if worked out of order, deleting execute_aws_api_call while sqs.py still imports it breaks the import graph immediately (caught by ruff/mypy/pytest collection, not silently).
- Assumes no other file does `from integrations.aws.client import execute_aws_api_call` etc. beyond what TASK-25.2.6.1's and this slice's own research covered — re-grep `execute_aws_api_call|handle_aws_api_errors|assume_role_session|get_aws_service_client` repo-wide immediately before deleting as a final check, since time will have passed since the 2026-09-18 survey.
- Assumes flipping sdk-typing.md's `applies` field is out of scope (see step 6) — this is a deliberate scope boundary, not an oversight; raise it to the human in the PR description rather than deciding it here.

BLAST RADIUS AND ROLLBACK
- All deletions are of code with zero production consumers (grep-confirmed) or their own dedicated tests. A single `git revert` of this PR fully restores the prior state; TASK-25.2.6.3 depends on this slice (it deletes the module client.py's line 21 import points to), so revert this slice only after reverting or coordinating with .3 if both have landed.

VERIFICATION (run from app/)
cd app && uv run ruff check .
cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'
cd app && uv run pytest tests --ignore=tests/smoke
cd app && make check-sdk-typing
cd app && make check-vendor-package-contract
cd app && make client-usage-matrix
Record command output in --notes. The 6 SNS/google-directory order-dependent failures in the single-process pytest run are known (TASK-90) and pre-existing; call them out explicitly if seen, do not fix them here.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
CHANGES
- app/integrations/aws/client.py: deleted the legacy dispatcher block through the end of the file (five re-exported constants; handle_aws_api_errors, assume_role_session, get_aws_service_client, execute_aws_api_call, paginator). Also removed the imports it orphaned: functools.wraps, structlog, botocore.client.BaseClient, the infrastructure.configuration.integrations.aws import, and the module logger. 432 -> 211 lines. The module now defines only get_aws_client (overloads), classify_aws_error and the private helpers _build_config, _session_for and _assume_role_credentials.
- Deleted app/integrations/aws/shield.py.
- Deleted tests/unit/integrations/aws/test_executor.py, tests/unit/integrations/aws/test_shield.py, tests/integrations/aws/test_legacy_aws_client.py and tests/smoke/integrations/aws/test_shield_smoke.py. Also removed the two directories this emptied: tests/integrations/aws/ (only __pycache__ left) and tests/smoke/integrations/aws/ (only __init__.py left).
- Baselines: sdk_typing_antipatterns.txt lost its last entry (integrations/aws/client.py) and is now header-only. vendor_package_contract.txt lost module:integrations/aws/shield.py and operation-result:integrations/aws/shield.py.
- decisions/sdk-typing.md: Migration section rewritten; the four tolerated anti-patterns are deleted and no divergence is tolerated. Dated Changes line added. applies stays target (see below).

DEVIATION FROM PLAN (grep before deletion, found and fixed in scope)
- Three moto integration test modules imported the deleted AWS_REGION constant from integrations.aws.client: tests/integration/infrastructure/idempotency/conftest.py, tests/integration/infrastructure/storage/conftest.py and tests/integration/integrations/aws/test_identity_store_conformance.py. The plan's survey missed them. They now read get_aws_settings().AWS_REGION from integrations.aws.settings. Equivalence checked at runtime: both settings classes default to ca-central-1 and both follow the AWS_REGION env var (us-west-2 override -> us-west-2 in both).
- The plan's ADR wording 'TASK-25 left open for MaxMind/Slack' was stale: TASK-25.3 (MaxMind) is Done, and on 2026-09-18 the human decided the remaining vendors get new tasks. The text says 'the remaining vendors' instead.

APPLIES FIELD (not changed, for human decision). decisions/governance.md: applies: now requires every Check to pass on main, and target requires listing tolerated divergences, of which there are now none. Every grep Check passes (0 baselined files; no *_next.py; no __doc__ scraping; both stub packages present since TASK-70). The one open item is the review Check 'no per-vendor client facade class exposing an SDK handle': integrations/maxmind MaxMindClient and integrations/slack SlackClientManager.get_client() need a human judgement.

VERIFICATION (from app/)
- uv run ruff check . -> All checks passed!
- make check-sdk-typing -> OK: no net-new SDK anti-patterns (0 baselined file(s) remain).
- make check-vendor-package-contract -> OK: no net-new vendor-package contract violations (16 baselined entry(ies) remain).
- make client-usage-matrix -> generated tmp/client_{callsite_audit_sorted,external_usage_sorted,usage_matrix}.tsv. rg for execute_aws_api_call|handle_aws_api_errors|assume_role_session|get_aws_service_client|AWSShield|integrations.aws.(shield|sqs|schemas) across all three returns no match (tmp/ is gitignored).
- rg -i shield app/integrations -> no hits. ls integrations/aws -> __init__.py, client.py, settings.py.
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 78 errors in 27 files. Same count as before this slice, all pre-existing and in untouched files; none in integrations/aws or tests/integration. mypy is not blocking yet (TASK-16).
- uv run pytest tests --ignore=tests/smoke -> 6 failed, 3503 passed. The 6 are the known order-dependent failures from the single-process run (TASK-90): 3 in tests/modules/webhooks/test_webhooks_aws_sns.py and 3 in tests/unit/infrastructure/directory/test_google.py. The deleted files held 59 tests (collected and passed 59/59 from a git-archive export of HEAD 3ce72e35). The net fall from 3555 (the TASK-25.2.6.1 run) is 52, because #1496, the user-rotations slash command, landed between the two runs and added tests.
- uv run pytest tests/integration/infrastructure/storage tests/integration/infrastructure/idempotency tests/integration/integrations/aws -> 32 passed (the three repointed moto suites).

UPDATE 2026-09-18 (human decision, replaces the APPLIES FIELD paragraph above). sdk-typing.md must not imply the decision is fully in place. The review confirmed two real client facades. The Migration section now lists them as tolerated divergences with owners, instead of saying 'No divergence is tolerated':
- MaxMindClient -> TASK-25.5 (new);
- SlackClientManager and the four Slack Web-client construction sites -> TASK-25.4 (re-scoped).
applies stays target until both close.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-18 15:47
---
2026-09-18: step 4 reworded. TASK-25.2.6.1 now removes integrations/aws/sqs.py from sdk_typing_antipatterns.txt, so this slice removes only the last entry, integrations/aws/client.py.
---
<!-- COMMENTS:END -->
