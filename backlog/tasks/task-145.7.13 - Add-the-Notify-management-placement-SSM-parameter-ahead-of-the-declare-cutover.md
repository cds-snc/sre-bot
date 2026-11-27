---
id: TASK-145.7.13
title: Add the Notify management placement SSM parameter ahead of the declare cutover
status: Done
assignee: []
created_date: '2026-11-26T19:32:00Z'
updated_date: '2026-11-27T17:39:00Z'
labels:
  - incident
  - terraform
dependencies: []
parent_task_id: TASK-145.7
ordinal: 541000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Terraform-only expand PR from main, merged before TASK-145.7.10 (layer A), so a revert of the cutover never touches SSM (TASK-145.7.10 OQ7, approved 2026-11-26; precedent INCIDENT_RESPONSE__HANDBOOK_ID, TASK-145.7.2). Adds INCIDENT_RESPONSE__NOTIFY_MANAGEMENT_PLACEMENT_ID to locals.sre_bot_secret_names in terraform/ssm.tf; the human sets the value (the Notify placement folder id) with put-parameter after the apply. Carries the deployment.md rule: a new SSM name lands in its own PR before its consumer; a revert never removes an ssm.tf name; removal goes through the RETIRED map and a removed block with lifecycle { destroy = false }.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 terraform/ssm.tf lists INCIDENT_RESPONSE__NOTIFY_MANAGEMENT_PLACEMENT_ID in sre_bot_secret_names (sorted); the terraform and settings name tests pass with it
- [x] #2 decisions/deployment.md states the SSM name rule (own PR before the consumer; never removed by a revert; removal through the RETIRED map and a removed block with destroy = false)
- [x] #3 bin/deploy-checks.zsh pre and post summary run around the merge (SSM and env-name change) and make env-checks shows the name registered and not retired; outputs recorded in the notes
- [x] #4 The human sets the value with put-parameter after the apply and confirms it with get-parameter (value not recorded anywhere); TASK-145.7.10 layer A merges only after this
- [x] #5 ruff and the targeted terraform/settings tests pass; mypy and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Approved 2026-11-26 with the TASK-145.7.10 OQ7 ruling. 1. terraform/ssm.tf: add the name after INCIDENT_RESPONSE__HANDBOOK_ID (:24; list sorted); ecs.tf:31-33 and iam.tf:28-31 derive from the set. 2. Tests: tests/integration/server/test_server_plugins_configuration_requirements.py:197 and tests/unit/infrastructure/configuration/test_configuration_settings_production_names.py:44, extended only if they enumerate names. 3. decisions/deployment.md: the SSM name rule (AC #2), with the HashiCorp removed-block source. 4. Human: deploy-checks pre summary, merge, apply, aws ssm put-parameter --name /sre-bot/INCIDENT_RESPONSE__NOTIFY_MANAGEMENT_PLACEMENT_ID --type SecureString --overwrite --value '<Notify placement folder id>' (core_services account, ca-central-1), get-parameter --with-decryption to confirm, deploy-checks post summary, make env-checks. Until set, the placeholder 'set-outside-terraform' is in SSM but no code reads it (the declare service is unregistered until layer A). Blast radius: one new ECS secret; an empty or placeholder value fails nothing at boot (settings.py:69-73 default empty; plugin.py requires only handbook_id). Rollback: never a plain revert (AC #2 rule).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-27 implementation. terraform/ssm.tf: INCIDENT_RESPONSE__NOTIFY_MANAGEMENT_PLACEMENT_ID added to sre_bot_secret_names after INCIDENT_RESPONSE__HANDBOOK_ID (sorted); ecs.tf and iam.tf derive from the set, so the PR adds one SSM parameter (placeholder 'set-outside-terraform'), one ECS secret and the matching read grant. Tests: test_configuration_settings_production_names.py enumerates names, so it gains the row (IncidentResponseSettings, notify_management_placement_id); it pins an existing field and passes on first run. test_server_plugins_configuration_requirements.py does not enumerate names (it derives supplied names from ssm.tf; nothing requires the Notify id), so it is unchanged. decisions/deployment.md: the Secret parameters paragraph and a Checks line (AC #2). Blast radius: the task definition gains one secret at the next deploy; settings default empty and only handbook_id is a boot requirement, so a placeholder fails nothing; the declare service that reads it stays unregistered until TASK-145.7.10. Rollback: never a plain revert (deployment.md rule). Open: AC #3 (human runs deploy-checks pre/post summary and make env-checks), AC #4 (human put-parameter/get-parameter), AC #5 full gates.

Gates 2026-11-27 (before the rebase onto origin/main; the change touches one tf list entry and one test row): ruff check . All checks passed; targeted (production names, plugin configuration requirements, audit_env_coverage, incident response settings load) 108 passed; check-import-contracts 15 kept 0 broken; settings-key-ownership OK; package-shape OK (2 baselined); test-seams OK (47/12); mypy Found 33 errors in 11 files (baseline, none in touched files); pytest tests --ignore=tests/smoke 8230 passed.

2026-11-27 (human): the task files 145.7.10, 145.7.10.1, 145.12.2 and 145.10.5 ride with this PR; decisions/migration.md stays with 18.L9b (TASK-145.7.10). Rebased onto origin/main ba7e479b; the stash pop conflicted only in decisions/migration.md Changes (W1's 2026-11-25 line and the 2026-11-26 step-5 line, both kept). The value is set in the console (no AWS CLI login in the Codespace).

2026-11-27 (human): value set in the console (Parameter Store, SecureString, the Notify placement folder id under the incident folder) replacing the placeholder; confirmed by the human in the console (the Codespace has no AWS CLI login, so the console stands in for put-parameter/get-parameter). Value not recorded. AC #4 checked. AC #3 open: the pre file tmp/deploy-checks/pre-20261127T161846Z.txt has no results (every AWS call failed with UnrecognizedClientException, invalid security token); post summary and make env-checks not yet run.

2026-11-27 AC #3 evidence. pre (tmp/deploy-checks/pre-20261127T161846Z.txt): failed, every AWS call refused with UnrecognizedClientException (invalid session token); it cannot be rerun before the merge, so recorded as skipped. The rollback target is the image built from ba7e479b (image_tag input of build_and_deploy). post summary (tmp/deploy-checks/post-summary-20261127T173633Z.txt, 17:36Z): task definition sre-bot-task:154 lists INCIDENT_RESPONSE__NOTIFY_MANAGEMENT_PLACEMENT_ID among the secrets; image tag 3c196467 (#1897); deploy run build, sbom, deploy success; rollout, boot_errors, runtime_errors, slack_up, summary_present, summary_instance_ids, summary_config_hash, summary_no_token_in_boot, version PASS; health 200; non_json_lines WARN 4 (the same import-time lines as 2026-11-04: two debug built_conditional_write_store lines and the starlette TestClient warning). make env-checks (tmp/env-checks/20261127T173724Z.txt, 17:37Z): INCIDENT_RESPONSE__NOTIFY_MANAGEMENT_PLACEMENT_ID is [terraform, ssm set] and has no delete row, so it is registered and not retired. One check row: no Codespaces secret supplies it although its settings metadata names Codespaces; in a Codespace it stays empty and the declare sends no Notify invite, so production is unaffected. Pre-existing and unrelated: the same check for GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL; CLAUDE_CONFIG_DIR (a personal user Codespaces secret). Org Codespaces and Actions secrets were skipped (admin). All ACs checked; Done 2026-11-27 (merged In Progress in #1897). The task file change rides with the 18.L9b PR.
<!-- SECTION:NOTES:END -->
