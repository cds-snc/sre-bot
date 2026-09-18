---
id: TASK-25.2.6.3
title: >-
  Retire infrastructure/configuration/integrations/aws.py; repoint
  packages/access; close the outbound-clients.md shield tolerance
status: To Do
assignee: []
created_date: '2026-09-18 15:34'
updated_date: '2026-09-18 16:51'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.2.6.2
references:
  - app/infrastructure/configuration/integrations/aws.py
  - app/infrastructure/configuration/integrations/__init__.py
  - app/packages/access/sync/adapters/aws_identity_center.py
  - decisions/outbound-clients.md
parent_task_id: TASK-25.2.6
priority: high
ordinal: 234000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Third slice of TASK-25.2.6's deletion sweep, depends on TASK-25.2.6.2: client.py imports infrastructure.configuration.integrations.aws.get_aws_settings (aliased _get_legacy_aws_settings) to feed the legacy re-exported constants that 25.2.6.2 deletes, so that import must be gone from client.py before this slice deletes the module it points to. Deletes app/infrastructure/configuration/integrations/aws.py (AwsSettings, get_aws_settings) and its export from infrastructure/configuration/integrations/__init__.py's barrel (import line + two __all__ entries). Its only remaining production reader at that point (grep-verified 2026-09-18) is packages/access/sync/adapters/aws_identity_center.py:25, which repoints its single import line from infrastructure.configuration.integrations.aws to integrations.aws.settings — field-name parity confirmed (SERVICE_ROLE_MAP and INSTANCE_ID are identical on both). decisions/outbound-clients.md's Migration section drops the now-closed 'the shield-shaped AWS client;' tolerance bullet with a dated Changes line; the other two tolerated items (non-idempotent Google writes, the six-write num_retries=0 override) are TASK-87's and stay untouched. No sentence about eager AssumeRole is added: that design question is owned by TASK-92 (startup) and TASK-98 (per-call), explicitly out of scope here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 infrastructure/configuration/integrations/aws.py is deleted; AwsSettings and get_aws_settings are gone from infrastructure/configuration/integrations/__init__.py's imports and __all__
- [ ] #2 packages/access/sync/adapters/aws_identity_center.py imports get_aws_settings from integrations.aws.settings; its tests (tests/unit/packages/access/sync/test_aws_identity_center_adapter.py) still pass unchanged
- [ ] #3 tests/unit/infrastructure/configuration/test_integration_settings_singletons.py, test_aws_settings_fields.py and test_settings_delegation.py no longer reference infrastructure.configuration.integrations.aws, AwsSettings or the barrel's get_aws_settings
- [ ] #4 decisions/outbound-clients.md's Migration section lists every divergence tolerated today, each with its owning ticket (TASK-87.1-.3, TASK-25.4-.10, TASK-26, TASK-24, TASK-18), no longer lists the shield, and its stale AWSShield Consequences bullet is rewritten, with a dated Changes line; ruff, mypy and pytest tests --ignore=tests/smoke pass, output recorded in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
STEPS
1. Delete app/infrastructure/configuration/integrations/aws.py.
2. Edit app/infrastructure/configuration/integrations/__init__.py: remove the `from infrastructure.configuration.integrations.aws import AwsSettings, get_aws_settings` import line and the `"AwsSettings"` / `"get_aws_settings"` entries from `__all__`. Leave every other vendor's import/export (google, maxmind, notify, opsgenie, sentinel, slack, trello) untouched.
3. Edit app/packages/access/sync/adapters/aws_identity_center.py line 25: change `from infrastructure.configuration.integrations.aws import get_aws_settings` to `from integrations.aws.settings import get_aws_settings`. No other line in this file changes — SERVICE_ROLE_MAP.get("identitystore") and INSTANCE_ID reads are unchanged since the field/property names match.
4. Edit tests/unit/infrastructure/configuration/test_integration_settings_singletons.py: remove the `from infrastructure.configuration.integrations.aws import AwsSettings, get_aws_settings` import (line 3) and the whole `TestAwsSettingsSingleton` class (lines 52-65, including its trailing blank line). Every other vendor's Test*SettingsSingleton class stays.
5. Edit tests/unit/integrations/aws/test_aws_settings_fields.py: remove the `from infrastructure.configuration.integrations.aws import AwsSettings as InfrastructureAwsSettings` import (line 15); remove `test_service_role_map_matches_the_infrastructure_module_while_both_exist` (lines 131-137) — its premise ("while both exist") is now false, and TestFeatureFields.test_service_role_map_composes_the_configured_role_arns already covers SERVICE_ROLE_MAP's own behavior without the cross-module comparison. Trim the module docstring's sentence "the service-to-role map is compared against the infrastructure settings module that still defines it, so both stay identical while both exist" (lines 6-8) to describe only AWSSettings' own coverage.
6. Edit tests/unit/infrastructure/configuration/test_settings_delegation.py: remove `get_aws_settings` from the `infrastructure.configuration.integrations` import block (line 23) and its two `get_aws_settings.cache_clear()` calls in the autouse fixture (lines 42, 63). Leave the fixture's other cache-clear calls untouched.
7. Rewrite decisions/outbound-clients.md's Migration section (human decision 2026-09-18: the record must not imply the decision is in place where it is not). It lists every divergence tolerated today, each with its owning ticket. Drop the closed shield bullet and the stale 'client-layer convergence' ticket sentence, and state instead:
   - Ticket: TASK-25 (per-vendor contract) and TASK-87 (Google write replay safety).
   - Tolerated until closed:
     - Non-idempotent Google writes (Drive create and copy) on the retrying handle -> TASK-87.3.
     - The per-call num_retries=0 override at six Google writes -> TASK-87.1.
     - Directory members.insert 409 on replay not treated as success -> TASK-87.2.
     - MaxMindClient classifies and returns OperationResult inside the vendor package -> TASK-25.5.
     - Slack has no classify_slack_error, and its Web client is built at four sites -> TASK-25.4. The Slack transport modules still live in integrations/slack/ -> TASK-26.
     - Opsgenie (business operations in the vendor package, no classifier, no timeout) -> TASK-25.6.
     - Sentinel (audit sink in the vendor package, no classifier, imports infrastructure.audit) -> TASK-25.7.
     - Notify (revoke_api_key in the vendor package, no classifier) -> TASK-25.8.
     - Trello (ATIP operations in the vendor package, no classifier, no explicit timeout or retry) -> TASK-25.9.
     - OpenAI, introduced alongside this refactor (Summarizer port in the vendor package, classifier returns OperationResult) -> TASK-25.10.
     - Vendor settings still in infrastructure/configuration/integrations/ -> TASK-24.
     - The import-linter Check is not enforced yet -> TASK-18.
   Also rewrite the stale Consequences bullet 'The existing AWSShield is refactored into a classification function + factory config; _next.py twins resolve into this shape.' to the current state: AWSShield and the _next twins are deleted, and AWS is factory + classify_aws_error. governance.md says amendments rewrite the body in place. Add one dated Changes line. Re-verify each bullet by grep at implementation time, and drop any that has closed by then.

AC TRACEABILITY
- AC#1 (aws.py + barrel export deleted) -> steps 1-2; verify `grep -rn "AwsSettings\|get_aws_settings" app/infrastructure/configuration/integrations/__init__.py` returns nothing.
- AC#2 (packages/access repointed, its own tests pass) -> step 3; run `uv run pytest tests/unit/packages/access/sync/test_aws_identity_center_adapter.py -q`.
- AC#3 (three settings tests updated) -> steps 4-6.
- AC#4 (ADR + gates) -> step 7 plus the verification block below.

TEST MATRIX
No new tests: this slice repoints one import whose target already has field-for-field parity (grep-confirmed) and deletes tests whose only job was proving that parity while both settings modules coexisted. Regression coverage is: (a) tests/unit/packages/access/sync/test_aws_identity_center_adapter.py continuing to pass unmodified proves the repoint preserves behavior; (b) the full suite passing proves no other reader of the deleted module was missed.

ASSUMPTIONS AND DOUBTS
- Assumes packages/access/sync/adapters/aws_identity_center.py has exactly one import line to change and no other reference to the infrastructure module (grep-confirmed: only line 25 imports it; line 27 already imports classify_aws_error/get_aws_client from integrations.aws.client). Re-grep immediately before editing as a final check.
- Assumes test_settings_delegation.py's pre-existing lack of test_ functions (only an autouse fixture) is out of scope to fix — flagging it, not fixing it, per "fix bugs in files a task touches" being about bugs the task's own change touches, not unrelated pre-existing test-file gaps discovered incidentally.
- Step 7's divergence list reflects the tasks as of 2026-09-18; if any listed ticket has closed before this lands, drop its bullet rather than keep a stale one.
BLAST RADIUS AND ROLLBACK
- One settings module with a single, grep-confirmed, parity-verified importer being repointed to its already-existing replacement. A single `git revert` fully restores prior state. This slice depends on TASK-25.2.6.2 (client.py's own import of the module being deleted here must be gone first); if TASK-25.2.6.2 has not landed, `make check-runtime-imports`/pytest collection will fail immediately and loudly on import, not silently.

VERIFICATION (run from app/)
cd app && uv run ruff check .
cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'
cd app && uv run pytest tests --ignore=tests/smoke
Record command output in --notes. The 6 SNS/google-directory order-dependent failures in the single-process pytest run are known (TASK-90) and pre-existing; call them out explicitly if seen, do not fix them here.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-18 16:51
---
2026-09-18 (human decision): step 7 and AC#4 widened. outbound-clients.md must list every divergence tolerated today with its owner (Google writes, MaxMind, Slack, Opsgenie, Sentinel, Notify, Trello, OpenAI, settings, import-linter), not only drop the shield line. It must not imply the contract is in place where it is not. OpenAI counts as non-compliant and migrates under TASK-25.10.
---
<!-- COMMENTS:END -->
