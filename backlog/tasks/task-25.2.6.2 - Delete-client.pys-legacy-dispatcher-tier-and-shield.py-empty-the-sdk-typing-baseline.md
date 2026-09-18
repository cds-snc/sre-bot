---
id: TASK-25.2.6.2
title: >-
  Delete client.py's legacy dispatcher tier and shield.py; empty the sdk-typing
  baseline
status: To Do
assignee: []
created_date: '2026-09-18 15:34'
updated_date: '2026-09-18 15:35'
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
- [ ] #1 integrations/aws/ contains only __init__.py, client.py and settings.py; client.py exports get_aws_client and classify_aws_error only; grep -rn shield app/integrations returns zero code hits
- [ ] #2 tests/unit/integrations/aws/test_executor.py, test_shield.py, tests/integrations/aws/test_legacy_aws_client.py and tests/smoke/integrations/aws/test_shield_smoke.py are deleted
- [ ] #3 bin/baselines/sdk_typing_antipatterns.txt and the shield entries in bin/baselines/vendor_package_contract.txt are empty of integrations/aws entries
- [ ] #4 decisions/sdk-typing.md's Migration section records the four tolerated anti-patterns as closed, with a dated Changes line; ruff, mypy and pytest tests --ignore=tests/smoke pass; make check-sdk-typing, make check-vendor-package-contract and make client-usage-matrix output is recorded in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (2026-09-18, after TASK-25.2.6.1 lands). app/integrations/aws/client.py:224-432 is a single contiguous block starting with the comment "# --- Legacy dispatcher helpers ---... Kept only for the per-service mirror modules and deleted together with the last of them" and containing, in order: the five re-exported constants (229-233), handle_aws_api_errors (236), assume_role_session (289), get_aws_service_client (311), execute_aws_api_call (336), paginator (392). After TASK-25.2.6.1, sqs.py (their only production caller) is gone, so this block's only remaining callers are tests/integrations/aws/test_legacy_aws_client.py and tests/unit/integrations/aws/{test_executor,test_shield}.py and tests/smoke/integrations/aws/test_shield_smoke.py. Deleting lines 224-432 leaves these imports unused and must be removed too: line 12 `from functools import wraps` (only used by handle_aws_api_errors's @wraps), line 16 `import structlog` and line 38 `logger = structlog.get_logger()` (only used inside the deleted block), line 17 `from botocore.client import BaseClient` (only used as paginator's parameter type), and line 21 `from infrastructure.configuration.integrations.aws import get_aws_settings as _get_legacy_aws_settings` (only used to build _legacy_settings at line 228). Confirmed by grepping lines 1-223 of client.py for each name: none appear outside the deleted block. shield.py's AWSShield has zero production consumers (only its own three dedicated test files reference it). Google-side anti-patterns (execute_google_api_call, get_google_api_command_parameters, google_service.py, *_next.py) are already fully gone repo-wide (2026-09-18 grep), and no AWSClients facade class exists anywhere (only two docstring/comment mentions confirming its absence, in test_aws_identity_center_adapter.py:4,465 and tests/integration/packages/access/sync/adapters/aws/conftest.py:8).

STEPS
1. In app/integrations/aws/client.py: delete lines 224-432 in full (the legacy-helpers comment block through the end of the file). Delete the now-unused imports: `from functools import wraps` (line 12), `import structlog` (line 16), `from botocore.client import BaseClient` (line 17), `from infrastructure.configuration.integrations.aws import get_aws_settings as _get_legacy_aws_settings` (line 21), and the module-level `logger = structlog.get_logger()` (line 38). Leave `from typing import TYPE_CHECKING, Any, Literal, overload` as-is (Any/Literal/overload/TYPE_CHECKING all still used by get_aws_client's overloads). Run ruff after to catch anything missed (F401 unused import).
2. Delete app/integrations/aws/shield.py (124 lines: AWSShield class — __init__, client(), execute(), _classify_client_error()).
3. Delete the four now-orphaned test files: tests/unit/integrations/aws/test_executor.py, tests/unit/integrations/aws/test_shield.py, tests/integrations/aws/test_legacy_aws_client.py, tests/smoke/integrations/aws/test_shield_smoke.py.
4. Edit app/bin/baselines/sdk_typing_antipatterns.txt: remove the two data lines `integrations/aws/client.py` and `integrations/aws/sqs.py` (the second is already stale after TASK-25.2.6.1 but was left for this slice to remove together). Leave the header comment block; the file becomes header-only (zero entries), which `make check-sdk-typing` treats as passing. Do not delete bin/check_sdk_typing.py itself — its own "Retirement" docstring note ties that decision to a human reading decisions/sdk-typing.md's "migration complete" criteria, not to this task's scope.
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
