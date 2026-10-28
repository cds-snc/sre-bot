---
id: doc-14
title: Production configuration inventory
type: specification
created_date: '2026-10-20 23:50'
---

# Production configuration inventory

Every key production sets on 2026-10-20, by name only (no values), with its owning settings slice and its destination under decisions/configuration.md. Sources: the two SSM parameters `sre-bot-config` and `sre-bot-config-infrastructure` (read by the maintainer, keys only; the first ends with a newline and has 28 continuation lines of multi-line values) and the terraform task definition (`terraform/templates/sre-bot.json.tpl`).

This is the rename map: TASK-111.4 creates one SSM SecureString parameter per row whose destination is a secret, under the new name shown, and the slice subtasks read the new names. Each slice subtask lower-cases its fields to match the TOML keys and secret names below.

From TASK-111.15.1 the container no longer fetches the two SSM parameters: it starts uvicorn directly, and the task definition sets only `ENVIRONMENT` and `FORWARDED_ALLOW_IPS` with the `/sre-bot/*` secrets. Every blob line below is inert from then on; the IAM read stays until TASK-111.15.2 so an earlier revision can still roll back.

Destinations:
- `file [table] key`: a value in `app/config/production.toml` (or `base.toml` when it equals the default everywhere).
- `secret NAME`: an SSM SecureString parameter injected under `NAME` through task-definition `secrets:`.
- `secret NAME (non-public value)`: not a credential, but kept out of the public repository (decisions/configuration.md, non-public values); supplied exactly like a secret.
- `platform`: a platform-provided name, left as a task-definition environment variable.
- `delete`: no reader in code; removed with the SSM parameters, never migrated.

## Facts recorded for TASK-111 AC6

- Production sets `AWS_ORG_ACCOUNT_ROLE_ARN` and `ISSUER_CONFIG`.
- Production does not set `ACCESS_SYNC_ENABLED`, `DIRECTORY_REQUIRE_STARTUP_WARMUP` (now `[directory] require_startup_warmup`, default false), `SLACK__SIGNING_SECRET` (formerly `SLACK_SIGNING_SECRET`) or any `ACCESS_*` key; those run on their code defaults. Nor does it set `IDEMPOTENCY_TTL_SECONDS`, `IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS` or `AUDIT_TABLE_NAME` (now `[coordination] record_ttl_seconds` and `in_progress_ttl_seconds`, and `[audit] table_name`, TASK-111.13.3): the table names and TTLs come from `base.toml`, equal to the former defaults. Nor does it set `AWS_ADMIN_GROUPS` or `AWS_OPS_GROUP_NAME` (pre features confirms): production ran on the code default `["sre-ifs@cds-snc.ca"]`, now `[cloud_operations] aws_admin_groups` in `production.toml`, and the ops group assignment the empty group name disabled is deleted (TASK-111.14); the groups slice's other names (`RECONCILIATION_*`, `CIRCUIT_BREAKER_*`, `REQUIRE_JUSTIFICATION`, `MIN_JUSTIFICATION_LENGTH`) were never set and are deleted with it.
- Production `CORS_ALLOWED_ORIGINS` is the terraform variable default, an empty list.

## sre-bot-config

| Key | Owning slice | Destination | Subtask |
| --- | --- | --- | --- |
| ACCESS_TOKEN_EXPIRE_MINUTES | ServerSettings (unused field) | delete | 111.7 |
| APP_TOKEN | none | delete | 111.15 |
| ATIP_ANNOUNCE_CHANNEL | no longer read (TASK-111.14, 2026-10-28; the legacy AtipSettings was never wired: modules/atip/atip.py posted to C033L7RGCT0 written in code) | production.toml [atip] announce_channel_id (public Slack id; pre features compares it with this blob line; local and ci keep the test channel); the blob line stays inert until 111.15 removes the blobs | 111.14 |
| AWS_AUDIT_ACCOUNT_ROLE_ARN | no longer read (TASK-111.11.1, 2026-10-26) | secret AWS__TENANT__AUDIT_ROLE_ARN (non-public value, travels with the tenant entry); production sets it (pre aws 2026-10-27; first recorded wrongly as unset in production); parameter added by a second terraform-only PR before 111.11.1, value set with put-parameter from this blob line; the blob line stays inert until 111.15 removes the blob | 111.11.1 |
| AWS_LOGGING_ACCOUNT_ROLE_ARN | no longer read (TASK-111.11.1, 2026-10-26) | secret AWS__TENANT__LOGGING_ROLE_ARN (non-public value, travels with the tenant entry); production sets it (pre aws 2026-10-27; first recorded wrongly as unset in production); parameter added by a second terraform-only PR before 111.11.1, value set with put-parameter from this blob line; the blob line stays inert until 111.15 removes the blob | 111.11.1 |
| AWS_ORG_ACCOUNT_ROLE_ARN | no longer read (TASK-111.11.1, 2026-10-26) | secret AWS__TENANT__ORG_ROLE_ARN (non-public value); parameter added by a terraform-only PR before 111.11.1, value set with put-parameter from this blob line; the blob line stays inert until 111.15 removes the blobs | 111.11.1 |
| AWS_SRE_ACCOUNT_ROLE_ARN | none | delete | 111.15 |
| AWS_SSO_INSTANCE_ARN | no longer read (TASK-111.11.1, 2026-10-26) | secret AWS__TENANT__INSTANCE_ARN (non-public value: an internal tenant identifier only Identity Center administrators see); parameter added by a terraform-only PR before 111.11.1, value set with put-parameter from this blob line; the blob line stays inert until 111.15 removes the blobs | 111.11.1 |
| AWS_SSO_INSTANCE_ID | no longer read (TASK-111.11.1, 2026-10-26) | secret AWS__TENANT__INSTANCE_ID (non-public value: the identity store id is also the default access-portal subdomain); parameter added by a terraform-only PR before 111.11.1, value set with put-parameter from this blob line; the blob line stays inert until 111.15 removes the blobs | 111.11.1 |
| AWS_SSO_ROLE_ARN | none | delete | 111.15 |
| AWS_SSO_SYSTEM_ADMIN_PERMISSIONS | no longer read (TASK-111.11.1, 2026-10-26) | secret ACCESS_PERMISSION_SETS__SYSTEM_ADMIN_PERMISSIONS (non-public value: the ARN embeds the instance id); parameter added by a terraform-only PR before 111.11.1, value set with put-parameter from this blob line; the blob line stays inert until 111.15 removes the blobs | 111.11.1 |
| AWS_SSO_VIEW_ONLY_PERMISSIONS | no longer read (TASK-111.11.1, 2026-10-26) | secret ACCESS_PERMISSION_SETS__VIEW_ONLY_PERMISSIONS (non-public value: the ARN embeds the instance id); parameter added by a terraform-only PR before 111.11.1, value set with put-parameter from this blob line; the blob line stays inert until 111.15 removes the blobs | 111.11.1 |
| COMMAND_PROVIDERS | none | delete | 111.15 |
| ENVIRONMENT | AppSettings (identity) | platform (task definition already sets it) | 111.15 |
| FRONTEND_URL | none | delete | 111.15 |
| GOOGLE_CLIENT_ID | ServerSettings (unused field) | delete | 111.7 |
| GOOGLE_CLIENT_SECRET | ServerSettings (unused field) | delete | 111.7 |
| GOOGLE_DELEGATED_ADMIN_EMAIL | no longer read (TASK-111.10.2, 2026-10-26); the field is deleted | delete; the blob line stays inert until 111.15 removes the blob | 111.10.2 |
| GOOGLE_RESOURCES | GoogleResourcesConfig (interim, deleted by 111.10.3) | one key per id on its end-state slice, never one JSON; each id a non-public value from the environment (configuration.md, TASK-167): see GOOGLE_RESOURCES ids below; the blob line stays inert until 111.15 removes the blobs | 111.10.3 |
| GOOGLE_WORKSPACE_CUSTOMER_ID | no longer read (TASK-111.10.2, 2026-10-26) | secret GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID (non-public value: Google shows it only to domain-settings admins; parameter added by a terraform-only PR before 111.10.2, decided 2026-10-26); the blob line stays inert until 111.15 removes the blob | 111.10.2 |
| GROUP_DOMAIN | no longer read (TASK-111.14, 2026-10-28; GroupsFeatureSettings deleted) | delete; the blob line stays inert until 111.15 removes the blobs | 111.14 |
| GROUP_PROVIDERS | no longer read (TASK-111.14, 2026-10-28; GroupsFeatureSettings deleted) | delete; the blob line stays inert until 111.15 removes the blobs | 111.14 |
| INCIDENT_CHANNEL | no longer read (TASK-111.14, 2026-10-28) | production.toml [incident_response] announcement_channel_id (moved from [incident] incident_channel in TASK-111.15.1; public Slack id; pre features compares it with this blob line); the blob line stays inert until 111.15 removes the blobs | 111.14, 111.15.1 |
| ISSUER_CONFIG | SecuritySettings | file [security] issuer_config (structured table) | 111.8 |
| MAXMIND_KEY | none (MaxMindSettings reads only the database path) | delete | 111.15 |
| NOTIFY_API_URL | no longer read (TASK-111.12, 2026-10-28) | production.toml [notify.tenant] api_url (public; pre vendors compares it with this blob line); the blob line stays inert until 111.15 removes the blobs | 111.12 |
| NOTIFY_OPS_CHANNEL_ID | NotifyApiKeyLeakSettings (moved from ServerSettings in 111.7) | file [notify_api_key_leak] channel_id | 111.7 |
| NOTIFY_SRE_CLIENT_SECRET | no longer read (TASK-111.12, 2026-10-28) | secret NOTIFY__SRE_CLIENT_SECRET; the blob line stays inert until 111.15 removes the blobs | 111.4, 111.12 |
| NOTIFY_SRE_USER_NAME | no longer read (TASK-111.12, 2026-10-28) | secret NOTIFY__SRE_USER_NAME; the blob line stays inert until 111.15 removes the blobs | 111.4, 111.12 |
| NOTIFY_TEST_KEY | none (read by no test; ci_code.yml stops passing it in TASK-111.12) | delete (Actions secret, after 111.12) | 111.15 |
| OPSGENIE_INTEGRATIONS_KEY | no longer read (TASK-111.12, 2026-10-28) | secret OPSGENIE__INTEGRATIONS_KEY beside production.toml [opsgenie.tenant] api_url; the blob line stays inert until 111.15 removes the blobs | 111.4, 111.12 |
| OPSGENIE_KEY | none | delete | 111.15 |
| SENTINEL_CUSTOMER_ID | no longer read (TASK-111.15.1, 2026-10-28) | secret SENTINEL__CUSTOMER_ID (non-public value: the Log Analytics workspace id, a tenant identifier only Azure administrators see, paired with the shared key); parameter added by the terraform-only PR before 111.11.1 (2026-10-27), value set with put-parameter from this blob line; read as an env_only field from TASK-111.15.1 (pre sentinel compares the hashes) | 111.15.1 |
| SENTINEL_LOG_TYPE | no longer read (TASK-111.15.1, 2026-10-28) | production.toml [sentinel] log_type (a public table name; pre sentinel compares it with this blob line) | 111.15.1 |
| SENTINEL_SHARED_KEY | no longer read (TASK-111.15.1, 2026-10-28) | secret SENTINEL__SHARED_KEY, read as an env_only field from TASK-111.15.1 (pre sentinel compares the hashes); TASK-171 rules rebuild or delete | 111.4, 111.15.1 |
| SESSION_SECRET_KEY | ServerSettings (unused field) | delete | 111.7 |
| SLACK_APP_TOKEN | no longer read (TASK-111.9, 2026-10-23) | secret SLACK__APP_TOKEN, read by SlackSettings; the blob line stays inert until 111.15 removes the blob | 111.4, 111.9 |
| SLACK_BOT_TOKEN | no longer read (TASK-111.9, 2026-10-23) | secret SLACK__BOT_TOKEN, read by SlackSettings; the blob line stays inert until 111.15 removes the blob | 111.4, 111.9 |
| SLACK_ENABLED | no longer read (TASK-112.1, 2026-10-23) | production.toml [slack_transport] enabled = true; the blob line stays inert until 111.15 removes the blob | 112.1 |
| SLACK_SECURITY_USER_GROUP_ID | no longer read (TASK-111.14, 2026-10-28) | production.toml [incident_response] security_group_id (moved from [incident] slack_security_user_group_id in TASK-111.15.1; public Slack id; pre features compares it with this blob line); the blob line stays inert until 111.15 removes the blobs | 111.14, 111.15.1 |
| SLACK_TOKEN | none | delete | 111.15 |
| SRE_BOT_EMAIL | no longer read (TASK-111.10.2, 2026-10-26) | secret GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL (non-public value: the address of a domain-privileged account; parameter added in 111.10.1, read by GoogleWorkspaceSettings from 111.10.2); the blob line stays inert until 111.15 removes the blob | 111.10.1, 111.10.2 |
| SRE_OPS_CHANNEL_ID | no longer read (TASK-111.14, 2026-10-28) | production.toml [sre_ops] sre_ops_channel_id (public Slack id; pre features compares it with this blob line); the blob line stays inert until 111.15 removes the blobs | 111.14 |
| TRELLO_APP_KEY | no longer read (TASK-111.12, 2026-10-28) | secret TRELLO__TENANT__APP_KEY (the credentials are Trello's tenant entry: the SDK fixes the host, so nothing else identifies the tenant, decisions/configuration.md 2026-10-27); parameter added by the terraform-only PR before 111.12, value set with put-parameter from this blob line; the blob line stays inert until 111.15 removes the blobs | 111.12 |
| TRELLO_ATIP_BOARD | no longer read (TASK-111.12, 2026-10-28) | secret TRELLO__ATIP_BOARD (non-public value: a board set to Public opens to anyone with its link, as a Drive item does); parameter added by the terraform-only PR before 111.11.1 (2026-10-27), value set with put-parameter from this blob line; the blob line stays inert until 111.15 removes the blobs | 111.12 |
| TRELLO_TOKEN | no longer read (TASK-111.12, 2026-10-28) | secret TRELLO__TENANT__TOKEN (Trello's tenant entry, as TRELLO__TENANT__APP_KEY); parameter added by the terraform-only PR before 111.12, value set with put-parameter from this blob line; the blob line stays inert until 111.15 removes the blobs | 111.12 |
| TRELLO__APP_KEY | none (parameter created by 111.4, never read; superseded by TRELLO__TENANT__APP_KEY) | secret TRELLO__APP_KEY until the task definition drops it (111.15.1); parameter removed in 111.15.2 after Verify | 111.15.1, 111.15.2 |
| TRELLO__TOKEN | none (parameter created by 111.4, never read; superseded by TRELLO__TENANT__TOKEN) | secret TRELLO__TOKEN until the task definition drops it (111.15.1); parameter removed in 111.15.2 after Verify | 111.15.1, 111.15.2 |

## GOOGLE_RESOURCES ids

One row per id in the sre-bot-config `GOOGLE_RESOURCES` JSON, keyed `GOOGLE_RESOURCES <path>`. The terraform-only PR of TASK-111.10.3 creates each parameter; the human sets it with put-parameter from that path, and `zsh bin/deploy-checks.zsh pre google_ids` compares them without printing a value. `inc.d` (`incident_drive_id`) and `rep.g` have no reader and are not carried.

| Key | Owning slice | Destination | Subtask |
| --- | --- | --- | --- |
| GOOGLE_RESOURCES inc.f | [incident_core] folder_id | secret INCIDENT_CORE__FOLDER_ID (non-public value: a Drive or calendar item id) | 111.10.3 |
| GOOGLE_RESOURCES inc.t | [incident_core] report_template_id | secret INCIDENT_CORE__REPORT_TEMPLATE_ID (non-public value: a Drive or calendar item id) | 111.10.3 |
| GOOGLE_RESOURCES inc.l | [incident_core] list_sheet_id | secret INCIDENT_CORE__LIST_SHEET_ID (non-public value: a Drive or calendar item id) | 111.10.3 |
| GOOGLE_RESOURCES inc.h | [incident_response] handbook_id | secret INCIDENT_RESPONSE__HANDBOOK_ID (non-public value: a Drive or calendar item id) | 111.10.3 |
| GOOGLE_RESOURCES cal.sre | [incident_postmortem] calendar_id | secret INCIDENT_POSTMORTEM__CALENDAR_ID (non-public value: a Drive or calendar item id) | 111.10.3 |
| GOOGLE_RESOURCES aws.s | [cloud_operations_spending] sheet_id | secret CLOUD_OPERATIONS_SPENDING__SHEET_ID (non-public value: a Drive or calendar item id) | 111.10.3 |
| GOOGLE_RESOURCES tal.i | [talent] internal_folder_id | secret TALENT__INTERNAL_FOLDER_ID (non-public value: a Drive or calendar item id) | 111.10.3 |
| GOOGLE_RESOURCES tal.t | [talent] templates_folder_id | secret TALENT__TEMPLATES_FOLDER_ID (non-public value: a Drive or calendar item id) | 111.10.3 |
| GOOGLE_RESOURCES tal.s | [talent] scoring_guide_template_id | secret TALENT__SCORING_GUIDE_TEMPLATE_ID (non-public value: a Drive or calendar item id) | 111.10.3 |
| GOOGLE_RESOURCES tal.c | [talent] core_values_interview_notes_id | secret TALENT__CORE_VALUES_INTERVIEW_NOTES_ID (non-public value: a Drive or calendar item id) | 111.10.3 |
| GOOGLE_RESOURCES tal.tech | [talent] technical_interview_notes_id | secret TALENT__TECHNICAL_INTERVIEW_NOTES_ID (non-public value: a Drive or calendar item id) | 111.10.3 |
| GOOGLE_RESOURCES tal.int | [talent] intake_form_template_id | secret TALENT__INTAKE_FORM_TEMPLATE_ID (non-public value: a Drive or calendar item id) | 111.10.3 |
| GOOGLE_RESOURCES tal.ph | [talent] phone_screen_template_id | secret TALENT__PHONE_SCREEN_TEMPLATE_ID (non-public value: a Drive or calendar item id) | 111.10.3 |
| GOOGLE_RESOURCES tal.rec | [talent] recruitment_feedback_template_id | secret TALENT__RECRUITMENT_FEEDBACK_TEMPLATE_ID (non-public value: a Drive or calendar item id) | 111.10.3 |
| GOOGLE_RESOURCES tal.pan | [talent] panelist_guidebook_template_id | secret TALENT__PANELIST_GUIDEBOOK_TEMPLATE_ID (non-public value: a Drive or calendar item id) | 111.10.3 |
| GOOGLE_RESOURCES inc.d | none (incident_drive_id, unread) | not carried | 111.10.3 |
| GOOGLE_RESOURCES rep.g | none (unread) | not carried | 111.10.3 |

## sre-bot-config-infrastructure

| Key | Owning slice | Destination | Subtask |
| --- | --- | --- | --- |
| NOTIFY_ONCALL_GROUP_ID | NotifyApiKeyLeakSettings (moved from ServerSettings in 111.7) | file [notify_api_key_leak] oncall_group_id | 111.7 |
| OPENAI_API_KEY | no longer read (TASK-111.11.2, 2026-10-27) | secret OPENAI__API_KEY, read by OpenAISettings beside production.toml [openai.tenant] (base_url, model); the blob line stays inert until 111.15 removes the blob | 111.4, 111.11.2 |
| SLACK_NOTIFY_MGMT_USER_GROUP_ID | no longer read (TASK-111.14, 2026-10-28) | production.toml [incident_response] notify_management_group_id (moved from [incident] slack_notify_mgmt_user_group_id in TASK-111.15.1; public Slack id; pre features compares it with this blob line); the blob line stays inert until 111.15 removes the blobs | 111.14, 111.15.1 |
| SLACK_TEAM_ID | no longer read (TASK-111.9, 2026-10-23) | production.toml [slack.tenant] team_id = "T2G2S06PM"; the blob line stays inert until 111.15 removes the blob | 111.9 |
| SLACK_USER_TOKEN | no longer read (TASK-111.9, 2026-10-23) | secret SLACK__USER_TOKEN, read by SlackSettings; the blob line stays inert until 111.15 removes the blob | 111.4, 111.9 |
| SRE_TEST_CHANNEL_ID | ServerSettings | file [server] sre_test_channel_id | 111.7 |

## Task definition

| Name | Kind today | Owning slice | Destination | Subtask |
| --- | --- | --- | --- | --- |
| BACKEND_URL | removed (TASK-111.15.1) | ServerSettings | file [server] backend_url | 111.7, removed from the task definition in 111.15.1 |
| ENVIRONMENT | environment | AppSettings (identity) | platform | - |
| CORS_ALLOWED_ORIGINS | removed with its terraform variable (TASK-111.15.1) | SecuritySettings | file [security] cors_allowed_origins | 111.8, removed in 111.15.1 |
| FORWARDED_ALLOW_IPS | environment (VPC public subnet CIDRs) | none (uvicorn) | platform | - |
| SLACK__COMMAND_PREFIX | removed (TASK-111.15.1) | SlackTransportSettings | file [slack_transport] command_prefix (the transport's table; TASK-112 adds its enablement key beside it) | 111.7, removed in 111.15.1 |
| GCP_SRE_SERVICE_ACCOUNT_KEY_FILE | secrets: (SSM parameter, value from a terraform variable) | no longer read (TASK-111.10.2, 2026-10-26); no longer injected (TASK-111.15.1); the parameter and its terraform variable go in 111.15.2 | secret GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY (new parameter whose value is set outside terraform) | 111.4, 111.10.2 |

## Secrets TASK-111.4 creates

`SLACK__BOT_TOKEN`, `SLACK__APP_TOKEN`, `SLACK__USER_TOKEN`, `GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY`, `OPENAI__API_KEY`, `NOTIFY__SRE_USER_NAME`, `NOTIFY__SRE_CLIENT_SECRET`, `OPSGENIE__INTEGRATIONS_KEY`, `TRELLO__APP_KEY`, `TRELLO__TOKEN`, `SENTINEL__SHARED_KEY`: eleven parameters, each named `/sre-bot/<NAME>` and injected as `<NAME>`. Terraform creates them with a placeholder; each real value is set outside terraform from its source key above (`GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY` takes the value of the `gcp_sre_service_account_key` parameter). `SECURITY__DEV_BYPASS_TOKEN` and `SLACK__SIGNING_SECRET` are not set in production and get no parameter.

TASK-111.10.1 adds a twelfth parameter the same way, `GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL`, a non-public value (decided 2026-10-26); its value is the `SRE_BOT_EMAIL` blob line, set by the human with put-parameter after the apply. A terraform-only PR before TASK-111.10.2 adds a thirteenth, `GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID` (non-public value, decided 2026-10-26); its value is the `GOOGLE_WORKSPACE_CUSTOMER_ID` blob line.
