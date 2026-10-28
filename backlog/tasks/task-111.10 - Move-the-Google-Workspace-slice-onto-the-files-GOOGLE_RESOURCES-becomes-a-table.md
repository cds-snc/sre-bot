---
id: TASK-111.10
title: >-
  Move the Google Workspace slice onto the files; GOOGLE_RESOURCES becomes a
  table
status: To Do
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-28T19:47:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.3
  - TASK-111.4
  - TASK-111.6.1
  - TASK-111.16
  - TASK-111.17
references:
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1743
parent_task_id: TASK-111
type: feature
ordinal: 416000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Google Workspace vendor slice (integrations/google_workspace/settings.py) moves onto the configuration files. Non-secret values are read from [google_workspace] (delegated_admin_email, sre_bot_email, api retries and timeout); the fields lose their google_ prefix to match the doc-14 rename map. The tenant entry becomes a nested field read from [google_workspace.tenant]: customer_id in production.toml (the production tenant) and local.toml (the shared development environment), none in ci.toml. The service-account key is read as GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY (the production SecureString exists, no terraform change). A tenant entry missing the key, or the key set without a tenant entry, fails boot naming the missing key, and the customer id is never blank or the my_customer alias. extra=forbid. GOOGLE_RESOURCES becomes a [google_resources] table, production ids in production.toml, read by the interim GoogleResourcesConfig until its owners split it (TASK-158 deletes it); the unread incident_drive_id is deleted. GCP_SRE_SERVICE_ACCOUNT_KEY_FILE and the sre-bot-config values stay deployed for the rollback image until TASK-111.15.1 and 111.15.2 remove them.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The Google slice reads its non-secret values, the tenant customer_id included, from the files and its key only as GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY
- [x] #2 A tenant entry missing the key, or the key set without a tenant entry, fails boot naming the missing key; a blank or my_customer customer_id fails boot
- [ ] #3 Each Google document, folder, sheet and calendar id has its own key, a non-public value supplied only from the environment (decisions/configuration.md, TASK-167 ruling; TASK-111.10.3); GOOGLE_RESOURCES is no longer read; incident_drive_id is deleted
- [x] #4 production.toml values equal the sre-bot-config values they replace, and the GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY SecureString equals the gcp_sre_service_account_key parameter
- [ ] #5 The old names (GOOGLE_DELEGATED_ADMIN_EMAIL, SRE_BOT_EMAIL, GOOGLE_WORKSPACE_CUSTOMER_ID, GCP_SRE_SERVICE_ACCOUNT_KEY_FILE, GOOGLE_RESOURCES) are no longer read from the environment or .env
- [x] #6 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
COORDINATOR. Split 2026-10-26 (human approved): TASK-111.10.1 reads the Google settings at use, not at import, and adds the unread /sre-bot/GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL parameter (expand step; carries the configuration.md non-public value rule and the doc-14 rows); TASK-111.10.2 moves the Google Workspace slice onto the files (customer_id in the files; key and delegated user from the environment; google_delegated_admin_email, Authlib and google-auth-oauthlib deleted); TASK-111.10.3 gives each GOOGLE_RESOURCES id its own key as TASK-167 rules on document ids (never in the public files). The credential model (principals, scopes, keyless authentication) is TASK-169. This task's ACs are checked as the subtasks verify them: #1, #2, #4, #5 by 111.10.2 (AC #1's delegated user now an environment value, not a file value; AC #4 compares the delegated user too), #3 by 111.10.3 (incident_drive_id deleted there; the [google_resources] table name follows TASK-167).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- 2026-10-28: ACs #1, #2, #4 and #6 checked from TASK-111.10.2 (Done 2026-10-27: post google PASS on sre-bot-task:58, pre google MATCH, gates green). AC #3 reworded to the TASK-167 ruling (the ids never go in the files); #3 and #5 close with TASK-111.10.3.
<!-- SECTION:NOTES:END -->
