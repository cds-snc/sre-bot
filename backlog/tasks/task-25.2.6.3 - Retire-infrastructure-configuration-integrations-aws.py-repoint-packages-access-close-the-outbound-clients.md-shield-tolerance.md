---
id: TASK-25.2.6.3
title: >-
  Retire infrastructure/configuration/integrations/aws.py; repoint
  packages/access; close the outbound-clients.md shield tolerance
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
- [ ] #4 decisions/outbound-clients.md's Migration section no longer lists the shield-shaped AWS client tolerance, with a dated Changes line; ruff, mypy and pytest tests --ignore=tests/smoke pass, output recorded in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (2026-09-18 grep, repo-wide including packages/ and tests/). app/infrastructure/configuration/integrations/aws.py (79 lines) defines AwsSettings(IntegrationSettings) and get_aws_settings(). After TASK-25.2.6.2 lands, its only importer anywhere in app/ is packages/access/sync/adapters/aws_identity_center.py:25 (`from infrastructure.configuration.integrations.aws import get_aws_settings`), used at line 1225 (`settings.SERVICE_ROLE_MAP.get("identitystore")`) and line 1227 (`settings.INSTANCE_ID`). app/integrations/aws/settings.py::AWSSettings already defines both with identical names: SERVICE_ROLE_MAP is the same property (audit/organizations/identitystore/sso-admin/logging/ce/config/guardduty/securityhub keys, same ORG_ROLE_ARN/AUDIT_ROLE_ARN/LOGGING_ROLE_ARN sourcing) and INSTANCE_ID is the same field (alias AWS_SSO_INSTANCE_ID). The barrel infrastructure/configuration/integrations/__init__.py:3 imports `AwsSettings, get_aws_settings` and re-exports both in __all__ (lines 37, 46 alongside Slack/Google/MaxMind/etc — do not touch the other six vendors' entries, they belong to TASK-24 per this task's scope boundary). Three tests reference the module being deleted: tests/unit/infrastructure/configuration/test_integration_settings_singletons.py (imports AwsSettings/get_aws_settings at line 3; TestAwsSettingsSingleton class at lines 52-65 tests it directly), tests/unit/integrations/aws/test_aws_settings_fields.py (imports it as InfrastructureAwsSettings at line 15, used only in test_service_role_map_matches_the_infrastructure_module_while_both_exist at lines 131-137 — a bridge test whose whole purpose was proving the two settings modules stayed identical "while both exist"), and tests/unit/infrastructure/configuration/test_settings_delegation.py (imports get_aws_settings from the barrel at line 23, calls its cache_clear() in the autouse fixture at lines 42 and 63 — this file currently has no test_ functions of its own beyond the fixture, a pre-existing state unrelated to this task; not restructured here).

STEPS
1. Delete app/infrastructure/configuration/integrations/aws.py.
2. Edit app/infrastructure/configuration/integrations/__init__.py: remove the `from infrastructure.configuration.integrations.aws import AwsSettings, get_aws_settings` import line and the `"AwsSettings"` / `"get_aws_settings"` entries from `__all__`. Leave every other vendor's import/export (google, maxmind, notify, opsgenie, sentinel, slack, trello) untouched.
3. Edit app/packages/access/sync/adapters/aws_identity_center.py line 25: change `from infrastructure.configuration.integrations.aws import get_aws_settings` to `from integrations.aws.settings import get_aws_settings`. No other line in this file changes — SERVICE_ROLE_MAP.get("identitystore") and INSTANCE_ID reads are unchanged since the field/property names match.
4. Edit tests/unit/infrastructure/configuration/test_integration_settings_singletons.py: remove the `from infrastructure.configuration.integrations.aws import AwsSettings, get_aws_settings` import (line 3) and the whole `TestAwsSettingsSingleton` class (lines 52-65, including its trailing blank line). Every other vendor's Test*SettingsSingleton class stays.
5. Edit tests/unit/integrations/aws/test_aws_settings_fields.py: remove the `from infrastructure.configuration.integrations.aws import AwsSettings as InfrastructureAwsSettings` import (line 15); remove `test_service_role_map_matches_the_infrastructure_module_while_both_exist` (lines 131-137) — its premise ("while both exist") is now false, and TestFeatureFields.test_service_role_map_composes_the_configured_role_arns already covers SERVICE_ROLE_MAP's own behavior without the cross-module comparison. Trim the module docstring's sentence "the service-to-role map is compared against the infrastructure settings module that still defines it, so both stay identical while both exist" (lines 6-8) to describe only AWSSettings' own coverage.
6. Edit tests/unit/infrastructure/configuration/test_settings_delegation.py: remove `get_aws_settings` from the `infrastructure.configuration.integrations` import block (line 23) and its two `get_aws_settings.cache_clear()` calls in the autouse fixture (lines 42, 63). Leave the fixture's other cache-clear calls untouched.
7. Edit decisions/outbound-clients.md's Migration section: remove the `- the shield-shaped AWS client;` bullet. Leave the "Ticket: client-layer convergence (...)" heading sentence as-is even though its own named item is now closed — it stays as the historical pointer for what TASK-25.2.6 closed; do not touch the other two tolerated bullets (non-idempotent Google writes, the six-write num_retries=0 override), both owned by TASK-87. Add one dated Changes line: "- 2026-09-18: removed the closed 'shield-shaped AWS client' tolerance (TASK-25.2.6 deleted AWSShield and the legacy dispatcher; adapters call get_aws_client directly)." Do not add a sentence about eager AssumeRole — that is TASK-92/TASK-98's scope, explicitly excluded here.

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
- Assumes leaving the "Ticket: client-layer convergence" heading sentence in outbound-clients.md (step 7) even though its named item just closed is the minimal, task-instructed edit; a human may prefer restructuring the Migration section further once TASK-87 also closes — not this task's call.

BLAST RADIUS AND ROLLBACK
- One settings module with a single, grep-confirmed, parity-verified importer being repointed to its already-existing replacement. A single `git revert` fully restores prior state. This slice depends on TASK-25.2.6.2 (client.py's own import of the module being deleted here must be gone first); if TASK-25.2.6.2 has not landed, `make check-runtime-imports`/pytest collection will fail immediately and loudly on import, not silently.

VERIFICATION (run from app/)
cd app && uv run ruff check .
cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'
cd app && uv run pytest tests --ignore=tests/smoke
Record command output in --notes. The 6 SNS/google-directory order-dependent failures in the single-process pytest run are known (TASK-90) and pre-existing; call them out explicitly if seen, do not fix them here.
<!-- SECTION:PLAN:END -->
