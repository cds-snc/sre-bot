---
id: doc-14
title: Production configuration inventory
type: specification
created_date: '2026-10-20 23:50'
---

# Production configuration inventory

Every key production sets on 2026-10-20, by name only (no values), with its owning settings slice and its destination under decisions/configuration.md. Sources: the two SSM parameters `sre-bot-config` and `sre-bot-config-infrastructure` (read by the maintainer, keys only; the first ends with a newline and has 28 continuation lines of multi-line values) and the terraform task definition (`terraform/templates/sre-bot.json.tpl`).

This is the rename map: TASK-111.4 creates one SSM SecureString parameter per row whose destination is a secret, under the new name shown, and the slice subtasks read the new names. Each slice subtask lower-cases its fields to match the TOML keys and secret names below.

Destinations:
- `file [table] key`: a value in `app/config/production.toml` (or `base.toml` when it equals the default everywhere).
- `secret NAME`: an SSM SecureString parameter injected under `NAME` through task-definition `secrets:`.
- `secret NAME (non-public value)`: not a credential, but kept out of the public repository (decisions/configuration.md, non-public values); supplied exactly like a secret.
- `platform`: a platform-provided name, left as a task-definition environment variable.
- `delete`: no reader in code; removed with the SSM parameters, never migrated.

## Facts recorded for TASK-111 AC6

- Production sets `AWS_ORG_ACCOUNT_ROLE_ARN` and `ISSUER_CONFIG`.
- Production does not set `ACCESS_SYNC_ENABLED`, `DIRECTORY_REQUIRE_STARTUP_WARMUP`, `SLACK__SIGNING_SECRET` (formerly `SLACK_SIGNING_SECRET`) or any `ACCESS_*` key; those run on their code defaults.
- Production `CORS_ALLOWED_ORIGINS` is the terraform variable default, an empty list.

## sre-bot-config

| Key | Owning slice | Destination | Subtask |
| --- | --- | --- | --- |
| ACCESS_TOKEN_EXPIRE_MINUTES | ServerSettings (unused field) | delete | 111.7 |
| APP_TOKEN | none | delete | 111.15 |
| ATIP_ANNOUNCE_CHANNEL | AtipSettings (dead slice) | delete | 111.14 |
| AWS_AUDIT_ACCOUNT_ROLE_ARN | AWSSettings | file [aws] audit_role_arn | 111.11 |
| AWS_LOGGING_ACCOUNT_ROLE_ARN | AWSSettings | file [aws] logging_role_arn | 111.11 |
| AWS_ORG_ACCOUNT_ROLE_ARN | AWSSettings | file [aws] org_role_arn | 111.11 |
| AWS_SRE_ACCOUNT_ROLE_ARN | none | delete | 111.15 |
| AWS_SSO_INSTANCE_ARN | AWSSettings | file [aws] instance_arn | 111.11 |
| AWS_SSO_INSTANCE_ID | AWSSettings | file [aws] instance_id | 111.11 |
| AWS_SSO_ROLE_ARN | none | delete | 111.15 |
| AWS_SSO_SYSTEM_ADMIN_PERMISSIONS | AWSSettings | file [aws] system_admin_permissions | 111.11 |
| AWS_SSO_VIEW_ONLY_PERMISSIONS | AWSSettings | file [aws] view_only_permissions | 111.11 |
| COMMAND_PROVIDERS | none | delete | 111.15 |
| ENVIRONMENT | AppSettings (identity) | platform (task definition already sets it) | 111.15 |
| FRONTEND_URL | none | delete | 111.15 |
| GOOGLE_CLIENT_ID | ServerSettings (unused field) | delete | 111.7 |
| GOOGLE_CLIENT_SECRET | ServerSettings (unused field) | delete | 111.7 |
| GOOGLE_DELEGATED_ADMIN_EMAIL | no longer read (TASK-111.10.2, 2026-10-26); the field is deleted | delete; the blob line stays inert until 111.15 removes the blob | 111.10.2 |
| GOOGLE_RESOURCES | GoogleResourcesConfig (interim) | one key per id, never one JSON; Drive item ids are non-public values (never in the files), supplied as TASK-167 rules for document ids | 111.10.3 |
| GOOGLE_WORKSPACE_CUSTOMER_ID | no longer read (TASK-111.10.2, 2026-10-26) | secret GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID (non-public value: Google shows it only to domain-settings admins; parameter added by a terraform-only PR before 111.10.2, decided 2026-10-26); the blob line stays inert until 111.15 removes the blob | 111.10.2 |
| GROUP_DOMAIN | GroupsFeatureSettings (dead slice) | delete | 111.14 |
| GROUP_PROVIDERS | GroupsFeatureSettings (dead slice) | delete | 111.14 |
| INCIDENT_CHANNEL | IncidentFeatureSettings (infrastructure/configuration/features/incident.py) | file, the slice's table | 111.14 |
| ISSUER_CONFIG | SecuritySettings | file [security] issuer_config (structured table) | 111.8 |
| MAXMIND_KEY | none (MaxMindSettings reads only the database path) | delete | 111.15 |
| NOTIFY_API_URL | NotifySettings | file [notify] api_url | 111.12 |
| NOTIFY_OPS_CHANNEL_ID | NotifyApiKeyLeakSettings (moved from ServerSettings in 111.7) | file [notify_api_key_leak] channel_id | 111.7 |
| NOTIFY_SRE_CLIENT_SECRET | NotifySettings | secret NOTIFY__SRE_CLIENT_SECRET | 111.4, 111.12 |
| NOTIFY_SRE_USER_NAME | NotifySettings (credential id) | secret NOTIFY__SRE_USER_NAME | 111.4, 111.12 |
| NOTIFY_TEST_KEY | none (one test reads it with a default) | delete | 111.15 |
| OPSGENIE_INTEGRATIONS_KEY | OpsGenieSettings | secret OPSGENIE__INTEGRATIONS_KEY | 111.4, 111.12 |
| OPSGENIE_KEY | none | delete | 111.15 |
| SENTINEL_CUSTOMER_ID | SentinelSettings | file [sentinel] customer_id | 111.12 |
| SENTINEL_LOG_TYPE | SentinelSettings | file [sentinel] log_type | 111.12 |
| SENTINEL_SHARED_KEY | SentinelSettings | secret SENTINEL__SHARED_KEY | 111.4, 111.12 |
| SESSION_SECRET_KEY | ServerSettings (unused field) | delete | 111.7 |
| SLACK_APP_TOKEN | no longer read (TASK-111.9, 2026-10-23) | secret SLACK__APP_TOKEN, read by SlackSettings; the blob line stays inert until 111.15 removes the blob | 111.4, 111.9 |
| SLACK_BOT_TOKEN | no longer read (TASK-111.9, 2026-10-23) | secret SLACK__BOT_TOKEN, read by SlackSettings; the blob line stays inert until 111.15 removes the blob | 111.4, 111.9 |
| SLACK_ENABLED | no longer read (TASK-112.1, 2026-10-23) | production.toml [slack_transport] enabled = true; the blob line stays inert until 111.15 removes the blob | 112.1 |
| SLACK_SECURITY_USER_GROUP_ID | IncidentFeatureSettings | file, the slice's table | 111.14 |
| SLACK_TOKEN | none | delete | 111.15 |
| SRE_BOT_EMAIL | no longer read (TASK-111.10.2, 2026-10-26) | secret GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL (non-public value: the address of a domain-privileged account; parameter added in 111.10.1, read by GoogleWorkspaceSettings from 111.10.2); the blob line stays inert until 111.15 removes the blob | 111.10.1, 111.10.2 |
| SRE_OPS_CHANNEL_ID | SreOpsSettings (infrastructure/configuration/features/sre_ops.py) | file, the slice's table | 111.14 |
| TRELLO_APP_KEY | TrelloSettings | secret TRELLO__APP_KEY | 111.4, 111.12 |
| TRELLO_ATIP_BOARD | TrelloSettings | file [trello] atip_board | 111.12 |
| TRELLO_TOKEN | TrelloSettings | secret TRELLO__TOKEN | 111.4, 111.12 |

## sre-bot-config-infrastructure

| Key | Owning slice | Destination | Subtask |
| --- | --- | --- | --- |
| NOTIFY_ONCALL_GROUP_ID | NotifyApiKeyLeakSettings (moved from ServerSettings in 111.7) | file [notify_api_key_leak] oncall_group_id | 111.7 |
| OPENAI_API_KEY | OpenAISettings | secret OPENAI__API_KEY | 111.4, 111.11 |
| SLACK_NOTIFY_MGMT_USER_GROUP_ID | IncidentFeatureSettings | file, the slice's table | 111.14 |
| SLACK_TEAM_ID | no longer read (TASK-111.9, 2026-10-23) | production.toml [slack.tenant] team_id = "T2G2S06PM"; the blob line stays inert until 111.15 removes the blob | 111.9 |
| SLACK_USER_TOKEN | no longer read (TASK-111.9, 2026-10-23) | secret SLACK__USER_TOKEN, read by SlackSettings; the blob line stays inert until 111.15 removes the blob | 111.4, 111.9 |
| SRE_TEST_CHANNEL_ID | ServerSettings | file [server] sre_test_channel_id | 111.7 |

## Task definition

| Name | Kind today | Owning slice | Destination | Subtask |
| --- | --- | --- | --- | --- |
| BACKEND_URL | environment (from the route53 zone) | ServerSettings | file [server] backend_url | 111.7, removed from the task definition in 111.15 |
| ENVIRONMENT | environment | AppSettings (identity) | platform | - |
| CORS_ALLOWED_ORIGINS | environment (terraform variable, empty) | SecuritySettings | file [security] cors_allowed_origins | 111.8, removed in 111.15 |
| FORWARDED_ALLOW_IPS | environment (VPC public subnet CIDRs) | none (uvicorn) | platform | - |
| SLACK__COMMAND_PREFIX | environment (empty string) | SlackTransportSettings | file [slack_transport] command_prefix (the transport's table; TASK-112 adds its enablement key beside it) | 111.7, removed in 111.15 |
| GCP_SRE_SERVICE_ACCOUNT_KEY_FILE | secrets: (SSM parameter, value from a terraform variable) | no longer read (TASK-111.10.2, 2026-10-26); still injected for the rollback image until 111.15.1 | secret GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY (new parameter whose value is set outside terraform) | 111.4, 111.10.2 |

## Secrets TASK-111.4 creates

`SLACK__BOT_TOKEN`, `SLACK__APP_TOKEN`, `SLACK__USER_TOKEN`, `GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY`, `OPENAI__API_KEY`, `NOTIFY__SRE_USER_NAME`, `NOTIFY__SRE_CLIENT_SECRET`, `OPSGENIE__INTEGRATIONS_KEY`, `TRELLO__APP_KEY`, `TRELLO__TOKEN`, `SENTINEL__SHARED_KEY`: eleven parameters, each named `/sre-bot/<NAME>` and injected as `<NAME>`. Terraform creates them with a placeholder; each real value is set outside terraform from its source key above (`GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY` takes the value of the `gcp_sre_service_account_key` parameter). `SECURITY__DEV_BYPASS_TOKEN` and `SLACK__SIGNING_SECRET` are not set in production and get no parameter.

TASK-111.10.1 adds a twelfth parameter the same way, `GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL`, a non-public value (decided 2026-10-26); its value is the `SRE_BOT_EMAIL` blob line, set by the human with put-parameter after the apply. A terraform-only PR before TASK-111.10.2 adds a thirteenth, `GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID` (non-public value, decided 2026-10-26); its value is the `GOOGLE_WORKSPACE_CUSTOMER_ID` blob line.
