---
id: TASK-173
title: >-
  While the legacy incident handlers are registered, a Slack transport switched
  on without a Google Workspace tenant fails boot
status: In Progress
assignee: []
created_date: '2026-10-27T18:11:00Z'
updated_date: '2026-10-29T17:08:00Z'
labels:
  - configuration
  - plugins
milestone: m-7
dependencies:
  - TASK-111.10.2
references:
  - decisions/configuration.md
  - decisions/lifecycle.md
priority: medium
ordinal: 454000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/configuration.md (Tolerated, 2026-10-27): the legacy incident code in modules/ needs Google Workspace (documents, Drive, calendar) and is not a plugin, so it cannot state a requirement itself (decisions/plugins.md). Until the legacy incident handlers are deleted (app/modules/incident, TASK-145.13; eight of its modules use Google, so the need outlives declare's rebuild in TASK-145.7), the host states it: in the configuration phase, a Slack transport switched on with GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID unset fails boot naming that key, as a transport switched on without its own vendor's tenant entry already does (decisions/lifecycle.md phase 1). No ENVIRONMENT comparison. TASK-172's register_requirements cannot carry it: the legacy handlers are not plugins.

TODAY: CI and a Codespace without a Google tenant boot and fail at use; production configures the tenant through the environment-only SSM parameters GOOGLE_WORKSPACE__TENANT__* (terraform/ssm.tf, TASK-111.10.2), not production.toml. local.toml enables the transport, so a Codespace needs the GOOGLE_WORKSPACE__TENANT__* secrets.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 With [slack_transport] enabled and GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID unset, boot fails in the configuration phase naming GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID and 'required when [slack_transport] enabled is true'; with the transport off, or with a tenant, boot succeeds (tests)
- [x] #2 The rule is a new function beside the existing transport-requires-vendor check, carries a comment naming the legacy incident handlers it exists for; the existing decisions/configuration.md Tolerated item names TASK-145.13 as its deletion point and a dated Changes line records the rule
- [x] #3 ruff, mypy (no new errors in touched files), pytest tests --ignore=tests/smoke, make check-import-contracts and make check-settings-key-ownership pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PROPOSED, AWAITING HUMAN APPROVAL (2026-10-28). Planned against main 175857b6.

## Findings (real code)
- The transport rule lives in app/server/configuration/host_configuration.py: validate_slack_transport (l.~96-125) returns at once when [slack_transport] enabled is false, then raises ConfigurationError naming [slack.tenant] team_id / SLACK__BOT_TOKEN / SLACK__APP_TOKEN / SLACK__SIGNING_SECRET. It is called from _validate_slices (l.~190) BEFORE get_google_workspace_settings() (l.~194). SlackKey (l.51-56) is the enum of key names the rules cite.
- Google's tenant is optional on the slice: GoogleWorkspaceSettings.tenant: GoogleWorkspaceTenant | None (app/integrations/google_workspace/settings.py:112); a half entry already fails in the slice's validator (l.127-142). The entry is ENVIRONMENT-ONLY (settings.py:7-9, base.toml:56-60): there is NO [google_workspace.tenant] in any toml file, by design (customer id and delegated user are non-public, key is a secret).
- Production: values come from SSM SecureStrings GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID / DELEGATED_USER_EMAIL / SERVICE_ACCOUNT_KEY (terraform/ssm.tf:28-30), injected by the task definition. production.toml (l.8-9) has [slack_transport] enabled = true, so production IS subject to the rule; it boots only if the three parameters hold real values (TASK-111.10.2 merged; verify, see human steps). The task text "production.toml has tenant values" is therefore not how it works.
- local.toml:9-11 has [slack_transport] enabled = true, so a Codespace without Codespaces secrets GOOGLE_WORKSPACE__TENANT__* will fail boot after this ships (intended, per the task). ci.toml has no [slack_transport]; base.toml:49-51 has enabled = false, and pyproject pytest-env sets ENVIRONMENT=ci and blanks the Google vars (pyproject.toml:~136-148). CI and the test run need no toml change.
- Existing tests that turn the transport on and expect success: tests/integration/server/test_server_configuration_phase_logging_render.py:105 (test_configuration_phase_event_renders_as_json_in_production via _transport_on, l.97-98) sets a Slack tenant and tokens but no Google tenant and calls load_host_configuration(); it will fail and needs a Google tenant (monkeypatch GOOGLE_WORKSPACE__TENANT__* with tests/factories/google_service_account.py service_account_key()). Check l.159 test (transport on, no Slack tenant) still fails on the Slack key first (it must, ordering below). tests/integration/server/test_lifespan_vendor_slice_validation.py:137 enables the transport with no Slack tenant and expects the team_id failure: Slack rules must keep running first. tests/unit/server/configuration/test_server_configuration_slack_transport_rules.py calls validate_slack_transport(transport, slack) with two args, so its signature stays.

## Steps (single PR)
1. Production, host_configuration.py: add SlackKey-style key constant (or a module constant) GOOGLE_CUSTOMER_ID = "GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID" and a new function validate_legacy_incident_google_requirement(transport: SlackTransportSettings, google: GoogleWorkspaceSettings) -> None placed directly beside validate_slack_transport: returns when transport.enabled is false; raises ConfigurationError(f"{key} is required when [slack_transport] enabled is true (the legacy incident handlers need Google Workspace)") when google.tenant is None. The comment above it names the legacy incident handlers in modules/ (not plugins, cannot state a requirement), TASK-145.7 AC #9 as the deletion point, and that there is no ENVIRONMENT comparison. Message names the key, never a value. ~20 LOC.
2. In _validate_slices: replace the bare get_google_workspace_settings() call with google = get_google_workspace_settings() and call the new function right after it (so Slack's own keys fail first, and a half Google entry fails inside the slice first). Do NOT fold it into validate_slack_transport: that keeps its two-argument signature and its unit tests, and the single deletion in 145.7 removes one function and one call. ~3 LOC.
3. decisions/configuration.md: the Tolerated item (l.114) already lists TASK-173; keep it, and add a dated Changes line (2026-10-28) saying the rule exists, where it runs, and that it is deleted by TASK-145.7. Docs only.
4. Fix the one existing test broken by the rule (logging_render l.105) and add the new tests below.
Total: 1 production file, ~25 production LOC, 1 doc, 3 test files. No toml, terraform, or CI change.

## Size gate
PASS: 1 prod file, ~25 LOC, 1 subsystem (server configuration phase), no mechanical refactor mixed with behavior, single git revert restores the old behavior. No decomposition; no size exception needed.

## TDD test matrix (write first; tests in app/tests)
- tests/unit/server/configuration/test_server_configuration_legacy_incident_google_rule.py (unit; GoogleWorkspaceSettings built with model_construct so env/.env cannot satisfy it; GoogleWorkspaceTenant via model_construct too):
  * transport off + no tenant -> no error (AC1 off case)
  * transport on + no tenant -> ConfigurationError matching GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID (AC1)
  * transport on + tenant present -> passes (AC1)
  * message carries no secret/customer-id/email value (failure case)
  * message names the legacy incident handlers? no (asserting prose is brittle); assert key name only.
- tests/integration/server/test_lifespan_google_requirement_boot.py (or extend test_lifespan_vendor_slice_validation.py using its _boot_fails_naming helper): transport on + Slack tenant/tokens set + no Google tenant -> boot fails naming GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID before the lifespan yields and before core services are built (AC1 end to end); transport on + both tenants -> boot reaches yield; transport on + no Slack tenant and no Google -> the Slack key is named (ordering: Slack rules first); transport on + half Google entry (customer id only) -> the existing SERVICE_ACCOUNT_KEY failure, not the new one (boundary).
- tests/integration/server/test_server_configuration_phase_logging_render.py: extend the existing production-phase test with a Google tenant; add a case that the new failure is logged as one CRITICAL configuration_invalid line without the key value.
- tests/unit/server/configuration/test_server_configuration_production_values.py (existing file): add test that production.toml and local.toml enable the transport and base.toml/ci.toml leave it off (documents which environments the rule bites; guards CI staying green without a Google tenant).

## AC traceability
- AC1 -> steps 1-2; unit tests (3 cases) + integration boot tests.
- AC2 -> step 1 (placement beside validate_slack_transport, comment naming legacy incident handlers) + step 3 (configuration.md; Tolerated entry already present at l.114, Changes line added). Verified by review of the diff, not a test.
- AC3 -> gates: cd app && uv run ruff check . ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' ; uv run pytest tests --ignore=tests/smoke ; make check-import-contracts ; make check-settings-key-ownership.
- Step 4 (fix existing test) is enabling work for AC1/AC3.

## Assumptions to verify at implementation
- No other test enables the transport and runs the phase with success (grep: SLACK_TRANSPORT__ENABLED, _transport_on, enabled = true under app/tests; done for tests/integration/server and unit/server, re-run repo-wide).
- tests/integration/legacy_surface/conftest.py builds the app without the configuration phase (it reads get_slack_transport_settings().command_prefix only); confirm by running it.
- The task definition injects the three GOOGLE_WORKSPACE__TENANT__* secrets (ssm.tf:28-30 lists them; confirm in terraform task definition secrets and with bin/deploy-checks.zsh pre).

## Blast radius and rollback
Merging to main deploys. If the three production SSM parameters are blank/placeholder (value_wo placeholders), production boot fails in the configuration phase and the ECS circuit breaker rolls back automatically; the failure names the key. Mitigation: human confirms the real values before merge. A single git revert restores prior behavior; no data, terraform or schema change. Local: Codespaces without GOOGLE_WORKSPACE__TENANT__* now fail boot (intended; add the Codespaces secrets or set [slack_transport] enabled=false via env SLACK_TRANSPORT__ENABLED=false in app/.env). CI/test run unaffected (transport off in ci).

## Overlap and ordering with TASK-172 (planned in parallel)
Different phases: 173 is the host configuration phase (host_configuration.py, one function + one call), 172 is plugin registration (typed required-dependency error, plugin_boot_failed event, per-plugin resolves, ci.toml switching plugins off). No shared code, no ordering dependency; either can merge first. Only conflict risk: both append a Changes line to decisions/configuration.md and may touch test_lifespan_vendor_slice_validation.py; resolve by rebase. 173 must NOT reuse 172's plugin error type (the legacy handlers are not plugins; ConfigurationError is correct and already used by the sibling transport rule). Both are deleted/absorbed by TASK-145.7 (172's mechanism stays; 173's rule is deleted).

## Human steps
1. Before merge: bin/deploy-checks.zsh pre (or put-parameter read-only check) confirming GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID, DELEGATED_USER_EMAIL, SERVICE_ACCOUNT_KEY hold real (non-placeholder) values and appear in the task definition secrets; capture rollback tag.
2. Ensure Codespaces secrets GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID / SERVICE_ACCOUNT_KEY / DELEGATED_USER_EMAIL exist (bin/env-checks.zsh); otherwise local boot fails.
3. After deploy: post check that the task is healthy (no configuration_invalid CRITICAL in logs).

## Open questions (recommendation each)
Q1 New function beside validate_slack_transport, or extra parameter on it? Recommend new function (keeps the 2-arg signature and tests; one clean deletion in 145.7).
Q2 Require only the customer id (the task AC) or the whole entry? Recommend customer id: the slice already makes a present entry complete (key and customer id go together), so tenant is not None implies all required parts; delegated_user_email stays optional per 111.10.2.
Q3 Message wording: key only, with a short reason? Recommend key plus "required when [slack_transport] enabled is true" in the same style as the siblings; the legacy-handler reason lives in the code comment (AC2), not in the operator message.
Q4 Add the check to env-checks/deploy-checks? Recommend no change; existing pre check covers Google parameters (verify), human runs it.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- 2026-10-29 (delivery session; open questions assessed against the ADRs and doc-11): Q1 new function, Q2 customer id only, Q3 key plus the reason, Q4 no new deploy or env check: each covered by lifecycle.md phase 1 and configuration.md (Tolerated; 2026-10-27 vendor slices never make their tenant required), no gap. Correction: the deletion point is TASK-145.13 (deletes app/modules/incident), not TASK-145.7: on_call, incident_alert, notify_stale_incident_channels, core, incident, schedule_retro, incident_conversation and incident_helper import Google, and 145.7 AC #1 removes only the declare and alert-button registrations. Plan step 3 and the Q1 rationale's 'clean deletion in 145.7' read 145.13. TASK-145.13 gains the deletion AC. Not subsumed by TASK-172 (the handlers are not plugins). Applied, pending plan approval.

- 2026-10-29: plan approved (human), with the 2026-10-29 rulings above.

2026-10-29 implemented in the working tree from main cd090014 (same tree as TASK-172, disjoint files), In Progress. host_configuration.py: validate_legacy_incident_google_tenant(transport, google) beside validate_slack_transport, called in _validate_slices on the Google slice (after the Slack rules; a half Google entry fails in the slice first), message 'GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID is required when [slack_transport] enabled is true', comment names the legacy incident handlers and TASK-145.13. Tests: unit test_server_configuration_legacy_incident_google_rule (off, on with tenant, on without: exact message); integration test_lifespan_vendor_slice_validation (+3: no Google tenant fails naming the key with no token value, half entry fails on SERVICE_ACCOUNT_KEY first, both tenants boot); logging_render production test given a Google tenant. configuration.md Tolerated item reworded (since TASK-173, function named), Changes line; blob line points at TASK-176. Gates on the combined 172+173 tree: ruff All checks passed, format clean; mypy 41 errors in 14 files (baseline, none in touched files); pytest tests --ignore=tests/smoke 5884 passed; make check-import-contracts 13 kept, 0 broken; make check-settings-key-ownership OK. ACs 1-3 checked. Production: the three GOOGLE_WORKSPACE__TENANT__* SSM parameters are in the task definition (terraform/ssm.tf) and hold the values 111.10.2 verified; a blank one would fail boot and the circuit breaker rolls back. Codespaces need the GOOGLE_WORKSPACE__TENANT__* secrets (local.toml enables the transport) or SLACK_TRANSPORT__ENABLED=false in app/.env.

2026-10-29 (human): no manual deploy or env check is required for this task. Since the SSM blob migration closed, those checks run only for a task that changes terraform, the task definition, IAM or SSM parameters, or adds, renames or removes an environment name or secret, and for the contract step that deletes what a running revision used. Every AC is checked; the human sets Done.
<!-- SECTION:NOTES:END -->
