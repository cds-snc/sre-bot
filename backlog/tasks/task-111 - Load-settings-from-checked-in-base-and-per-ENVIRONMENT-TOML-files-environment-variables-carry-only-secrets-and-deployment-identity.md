---
id: TASK-111
title: >-
  Load settings from checked-in base and per-ENVIRONMENT TOML files; environment
  variables carry only secrets and deployment identity
status: To Do
assignee: []
created_date: '2026-09-24 19:59'
updated_date: '2026-10-21 16:23'
labels:
  - plugin-architecture
  - configuration
milestone: m-7
dependencies:
  - TASK-24
references:
  - decisions/configuration.md
  - decisions/lifecycle.md
  - 'https://github.com/cds-snc/sre-bot/issues/1654'
priority: medium
type: feature
ordinal: 253000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/configuration.md: values come from checked-in TOML configuration files (a base file plus one file per ENVIRONMENT value, each slice reading its own table); environment variables carry only secrets, named <SLICE>__<FIELD>, and the platform-provided names; every slice validates at boot and an invalid file fails boot naming the key.

Decomposed on 2026-10-20 into TASK-111.1 to TASK-111.15 (size gate: app, terraform, CI and SSM; mechanical renames apart from behaviour changes). This task coordinates them and closes when the last one merges. The 2026-10-20 planning decisions are recorded in decisions/configuration.md by TASK-111.1.

Scope: the loader and file layout; the CI checks; every slice production configures today (host, security, vendor, hosting and the feature values production sets) moved onto the files, with the remaining secrets renamed and delivered as SSM SecureString parameters through the task definition; retiring entry.sh's SSM fetch (absorbs TASK-54's AC3) and the two SSM parameters.

Not in scope: renaming feature-slice fields and prefixes (each package move does it); splitting GOOGLE_RESOURCES into the owning feature tables (TASK-145.6, 145.7, 145.10, 145.12, 39, 88; the interim [google_resources] table is TASK-111.10); plugin enablement and the Slack transport key (TASK-112); the startup configuration summary (TASK-156); deleting infrastructure/configuration/.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 base.toml and one file per ENVIRONMENT value (local, ci, production) load in the order base, environment file, then environment variables (TASK-111.2)
- [ ] #2 Every value production sets that is neither a secret nor a platform-provided name is read from the files, and the deployment config no longer sets it (TASK-111.7 to 111.15)
- [ ] #3 Boot fails naming the key for an invalid file, an unknown key or a missing required secret; CI fails on a table no slice owns (TASK-111.2, 111.3)
- [ ] #4 CI checks: each key and table is owned by exactly one settings slice, and a configuration-file slice reads only its own names or a platform-provided name; secret leaks are left to GitHub secret scanning (TASK-111.3)
- [ ] #5 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass on every subtask
- [ ] #6 The production SSM inventory, by key with no values and mapped to slice and destination, is recorded as a backlog doc (TASK-111.1)
- [ ] #7 Every remaining environment variable is a secret named <SLICE>__<FIELD> or a platform-provided name; no per-field aliases; renamed secrets were published beside the old names and the old names removed once the deploy was verified (TASK-111.4, 111.7 to 111.15)
- [ ] #8 Every slice TASK-111 migrates has lower snake_case fields and TOML keys, case_sensitive=False and extra=forbid; the feature slices of TASK-111.14 keep their field names until their package move (TASK-111.5 to 111.14)
- [ ] #9 app/bin/entry.sh fetches no SSM parameter and both SSM parameters are deleted (TASK-111.15)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Deployment env files (SSM parameters, terraform task definitions, CI workflow, Makefile) updated for the renamed variables; the renames are listed in the PR description
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Approved 2026-10-20: delivered through the subtasks, worked in order in the doc-11 Work queue. 111.1 decisions, inventory and environment set; 111.2 loader; 111.3 checks; 111.4 terraform secrets (human: set values, apply); 111.5 and 111.6 mechanical field lower-casing; 111.7 host; 111.8 security (deploys alone); 111.9 Slack; 111.10 Google; 111.11 AWS and OpenAI; 111.12 Notify, Trello, OpsGenie, MaxMind, Sentinel; 111.13 hosting slices; 111.14 feature values; 111.15 contract (human: delete both SSM parameters after the deploy is verified). 111.7 to 111.14 depend only on 111.2 to 111.6 and can be worked while a sibling is in review.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-20 (TASK-24.5): the vendor tenant entries are derived today: SlackSettings.tenant (SlackTenant) and GoogleWorkspaceSettings.tenant (GoogleWorkspaceTenant), frozen sub-models built from the flat fields, read by every consumer. The renames here make each a nested field read as <SLICE>__TENANT__<FIELD> and drop the flat fields (SLACK_TEAM_ID, GOOGLE_WORKSPACE_CUSTOMER_ID, GCP_SRE_SERVICE_ACCOUNT_KEY_FILE); consumers do not change.

2026-10-20 (TASK-24.6 planning): bin/check_settings_key_ownership.py (make check-settings-key-ownership, run in CI) records each key a slice reads as (source kind, key, owning class). Extend it with a config-file claim source for AC #4. It claims literal validation_alias and AliasChoices names, so AC7's one-release old names are checked for collisions too, whichever migration form this task picks; it fails on an AliasPath or a non-literal alias. It compares names case-insensitively across slices. It also fails on os.environ reads outside settings classes (bin/ and tests/ excluded).

2026-10-20 (planning, AC6 input; keys only, read by the human). sre-bot-config: ACCESS_TOKEN_EXPIRE_MINUTES, APP_TOKEN, ATIP_ANNOUNCE_CHANNEL, AWS_AUDIT_ACCOUNT_ROLE_ARN, AWS_LOGGING_ACCOUNT_ROLE_ARN, AWS_ORG_ACCOUNT_ROLE_ARN, AWS_SRE_ACCOUNT_ROLE_ARN, AWS_SSO_INSTANCE_ARN, AWS_SSO_INSTANCE_ID, AWS_SSO_ROLE_ARN, AWS_SSO_SYSTEM_ADMIN_PERMISSIONS, AWS_SSO_VIEW_ONLY_PERMISSIONS, COMMAND_PROVIDERS, ENVIRONMENT, FRONTEND_URL, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_DELEGATED_ADMIN_EMAIL, GOOGLE_RESOURCES, GOOGLE_WORKSPACE_CUSTOMER_ID, GROUP_DOMAIN, GROUP_PROVIDERS, INCIDENT_CHANNEL, ISSUER_CONFIG, MAXMIND_KEY, NOTIFY_API_URL, NOTIFY_OPS_CHANNEL_ID, NOTIFY_SRE_CLIENT_SECRET, NOTIFY_SRE_USER_NAME, NOTIFY_TEST_KEY, OPSGENIE_INTEGRATIONS_KEY, OPSGENIE_KEY, SENTINEL_CUSTOMER_ID, SENTINEL_LOG_TYPE, SENTINEL_SHARED_KEY, SESSION_SECRET_KEY, SLACK_APP_TOKEN, SLACK_BOT_TOKEN, SLACK_ENABLED, SLACK_SECURITY_USER_GROUP_ID, SLACK_TOKEN, SRE_BOT_EMAIL, SRE_OPS_CHANNEL_ID, TRELLO_APP_KEY, TRELLO_ATIP_BOARD, TRELLO_TOKEN (28 continuation lines of multi-line values; ends with a newline). sre-bot-config-infrastructure: NOTIFY_ONCALL_GROUP_ID, OPENAI_API_KEY, SLACK_NOTIFY_MGMT_USER_GROUP_ID, SLACK_TEAM_ID, SLACK_USER_TOKEN, SRE_TEST_CHANNEL_ID. Task definition env: BACKEND_URL, ENVIRONMENT, CORS_ALLOWED_ORIGINS (var default [], unset), FORWARDED_ALLOW_IPS, SLACK__COMMAND_PREFIX; secrets: GCP_SRE_SERVICE_ACCOUNT_KEY_FILE. Not set in production: ACCESS_SYNC_ENABLED, DIRECTORY_REQUIRE_STARTUP_WARMUP, SLACK_SIGNING_SECRET, any ACCESS_* key. No reader in code (delete, not migrate): APP_TOKEN, SLACK_TOKEN, OPSGENIE_KEY, MAXMIND_KEY, AWS_SRE_ACCOUNT_ROLE_ARN, AWS_SSO_ROLE_ARN, COMMAND_PROVIDERS, FRONTEND_URL, NOTIFY_TEST_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SESSION_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES. Verified: pydantic-settings 2.13.1 has no TOML table selector (toml_table_header arrived in 2.15.0, 2026-08-07); on 2.16.1, lower-case fields and TOML keys with case_sensitive=False read upper-case SLACK__TENANT__BOT_TOKEN into a nested model, deep-merge base and environment files, and reject an unknown key by name; upper-case fields with lower-case keys fail on nested tables.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-19 17:19
---
2026-10-19 (TASK-24 planning, human): the environment renames move here from TASK-24 step 3, with TASK-24's DoD 'deployment env files updated for renamed variables'. Rename once, after the inventory (AC #6) shows which variables remain as secrets; the rule is in decisions/configuration.md (TASK-24.1). This task now waits on TASK-24.6, the last TASK-24 slice.
---

created: 2026-10-20 12:32
---
2026-10-20: AC7 reads old env names through AliasChoices for one release, which conflicts with decisions/configuration.md's no-per-field-alias rule (lines 38, 93). Settle it when this task is planned: either a one-release migration without per-field aliases (for example a temporary settings source mapping old names) or a dated ADR exception.
---

created: 2026-10-20 23:27
---
2026-10-20 (planning, human): comment #2 settled. No AliasChoices and no compatibility code: renamed secrets are published on the deployment side beside the old names (TASK-111.4), the app reads only the new names, and the old names leave once the deploy is verified (TASK-111.15). decisions/configuration.md records the rename protocol (TASK-111.1).
---
<!-- COMMENTS:END -->
