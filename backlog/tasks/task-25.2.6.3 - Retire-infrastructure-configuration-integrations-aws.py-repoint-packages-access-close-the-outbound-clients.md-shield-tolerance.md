---
id: TASK-25.2.6.3
title: >-
  Retire infrastructure/configuration/integrations/aws.py; repoint
  packages/access; close the outbound-clients.md shield tolerance
status: In Progress
assignee:
  - '@claude'
created_date: '2026-09-18 15:34'
updated_date: '2026-09-24 16:00'
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
- [x] #1 infrastructure/configuration/integrations/aws.py is deleted; AwsSettings and get_aws_settings are gone from infrastructure/configuration/integrations/__init__.py's imports and __all__
- [x] #2 packages/access/sync/adapters/aws_identity_center.py imports get_aws_settings from integrations.aws.settings; its tests (tests/unit/packages/access/sync/test_aws_identity_center_adapter.py) still pass unchanged
- [x] #3 tests/unit/infrastructure/configuration/test_integration_settings_singletons.py, test_aws_settings_fields.py and test_settings_delegation.py no longer reference infrastructure.configuration.integrations.aws, AwsSettings or the barrel's get_aws_settings
- [x] #4 decisions/outbound-clients.md's Migration section lists every divergence tolerated today, each with its owning ticket (TASK-87.1-.3, TASK-25.4-.10, TASK-26, TASK-24, TASK-18), no longer lists the shield, and its stale AWSShield Consequences bullet is rewritten, with a dated Changes line; ruff, mypy and pytest tests --ignore=tests/smoke pass, output recorded in notes
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
WHAT CHANGED
- Deleted app/infrastructure/configuration/integrations/aws.py (AwsSettings, get_aws_settings); removed its import and both __all__ entries from infrastructure/configuration/integrations/__init__.py.
- packages/access/sync/adapters/aws_identity_center.py now imports get_aws_settings from integrations.aws.settings (ruff isort moved the line into alphabetical position; no other line changed). Field parity re-verified: INSTANCE_ID alias AWS_SSO_INSTANCE_ID and SERVICE_ROLE_MAP identical.
- Tests: test_integration_settings_singletons.py drops the import + TestAwsSettingsSingleton; test_aws_settings_fields.py drops the cross-module parity test, its import and docstring sentence, plus the deprecated `from __future__ import annotations` (touched-file rule); test_settings_delegation.py drops get_aws_settings import + both cache_clear calls; test_settings_structure.py (missed by the plan, see comment) drops AwsSettings from the barrel import and the instantiable list.
- decisions/outbound-clients.md: Migration rewritten to list every open divergence with its owner (TASK-87.1/.2/.3, TASK-25.4-.10, TASK-26, TASK-24, TASK-18), states only AWS follows the decision in full, shield bullet removed; AWSShield Consequences bullet rewritten to current state; dated Changes line added. Each bullet grep-verified 2026-09-24 and every owning ticket is still To Do. Correction vs plan wording: Google Workspace settings also still live in infrastructure/configuration/integrations/ (integrations/google_workspace/client.py imports it), so the TASK-24 bullet says "every vendor's settings except AWS's".
- No new tests: pure deletion + import repoint onto an identical target (plan TEST MATRIX).

EVIDENCE (from app/)
- uv run ruff check . -> All checks passed!
- uv run pytest tests/unit/packages/access/sync/test_aws_identity_center_adapter.py tests/unit/infrastructure/configuration tests/unit/integrations/aws -q -> 213 passed (adapter tests unmodified).
- uv run pytest tests --ignore=tests/smoke -> 6 failed, 3502 passed. The 6 are the known TASK-90 order-dependent failures (3 in tests/modules/webhooks/test_webhooks_aws_sns.py, 3 in tests/unit/infrastructure/directory/test_google.py); those two files run in isolation -> 111 passed.
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> 0 errors in the 6 Python files touched this session. The repo-wide run reports 78 errors in 27 untouched files; those are out of scope per the session-scoped mypy workflow (a `git archive HEAD` copy gives 79, so this change removes one).
- bash bin/generate_client_usage_matrix.sh -> runs clean after the edit below.

ALSO CHANGED
- app/bin/generate_client_usage_matrix.sh: dropped the stale `grep -v '^app/infrastructure/clients/'` filter (that directory was deleted in an earlier slice; bin scripts are updated as deprecated directories go). No other bin/ script references a path this sweep deleted.

DELETED-CONCEPT CLEANUP (requested in session, 2026-09-24)
Removed references to deleted code (AWSShield / "shield", `_next.py` twins, AWSClients facade, infrastructure/clients) from decisions and repo files. Backlog task history untouched.
- decisions/outbound-clients.md: Context no longer names the "shield" layer; dropped "The term 'shield' is retired."; dropped the AWS-status Consequences bullet (Migration's "Only AWS follows this decision in full" already says it); 2026-09-24 Changes line reworded to cover both edits.
- decisions/layers.md: "shield" wording removed from Context; `_next.py` twins removed from Current state and the Migration tolerated list (none remain: no *_next.py under app/); Changes line added.
- decisions/sdk-typing.md: Context describes the three anti-patterns generically (no dead file paths) and says they are deleted; Migration says "AWS facade" instead of `AWSClients`; Changes line added. Checks kept, since they guard against the patterns returning.
- decisions/transport-slack.md: rejected alternative no longer called "Slack shield". Wording only, decision unchanged; the record has no Changes section, so none added.
- app/packages/access/sync/adapters/README.md: the AWS requirements table and paragraph described AWSClients injection (wrong); now describe build_aws_identity_center_adapter() reading integrations.aws.settings and injecting the get_aws_client("identitystore", role_arn=...) client.
- tests/unit/integrations/aws/conftest.py: "shield" docstrings fixed; deprecated `from __future__ import annotations` removed.
- tests/unit/packages/access/sync/test_aws_identity_center_adapter.py and tests/integration/packages/access/sync/adapters/aws/conftest.py: AWSClients-facade wording removed; AC#1/AC#5 labels removed from docstrings/section comment (test docstring rule). Assertions unchanged.
- tests/unit/bin/test_bin_freeze_guard_check.py: baseline-parsing fixture uses neutral paths instead of the deleted integrations/aws/sqs.py and shield.py.
Evidence (from app/): ruff check . -> All checks passed; pytest tests/unit/integrations/aws tests/unit/packages/access/sync/test_aws_identity_center_adapter.py tests/unit/bin/test_bin_freeze_guard_check.py tests/integration/packages/access/sync/adapters/aws -> 135 passed; mypy on those 4 files -> 0 errors in them (16 reported in untouched imported modules infrastructure/i18n and integrations/slack/help.py, out of scope).
Left as is (Slack scope, TASK-25.4/26): tests/unit/integrations/slack/conftest.py docstrings and test_slack_bootstrap.py local variables still use "shield" for the Slack bootstrap/providers.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-18 16:51
---
2026-09-18 (human decision): step 7 and AC#4 widened. outbound-clients.md must list every divergence tolerated today with its owner (Google writes, MaxMind, Slack, Opsgenie, Sentinel, Notify, Trello, OpenAI, settings, import-linter), not only drop the shield line. It must not imply the contract is in place where it is not. OpenAI counts as non-compliant and migrates under TASK-25.10.
---

created: 2026-09-24 15:42
---
2026-09-24 plan review: plan missed one reader of the deleted barrel export — tests/unit/infrastructure/configuration/test_settings_structure.py imports AwsSettings from infrastructure.configuration.integrations (line 34) and instantiates it in test_all_integration_settings_classes_instantiable (line 135). Handled as step 6b: drop AwsSettings from that import and instance list. No failing tests authored: the slice is a pure deletion + import repoint onto a field-for-field identical target; existing adapter tests (unchanged) and full-suite collection are the regression proof, per the plan's TEST MATRIX.
---
<!-- COMMENTS:END -->
