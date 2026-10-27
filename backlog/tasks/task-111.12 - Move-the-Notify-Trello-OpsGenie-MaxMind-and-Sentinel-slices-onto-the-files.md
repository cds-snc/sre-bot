---
id: TASK-111.12
title: Move the Notify, Trello, OpsGenie, MaxMind and Sentinel slices onto the files
status: To Do
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-27T11:45:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.3
  - TASK-111.4
  - TASK-111.6.2
  - TASK-111.16
  - TASK-111.17
references:
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1745
parent_task_id: TASK-111
type: feature
ordinal: 418000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Notify, Trello, OpsGenie, MaxMind and Sentinel slices (integrations/<vendor>/settings.py) move onto the files, one table each ([notify], [trello], [opsgenie], [maxmind], [sentinel]). The fields lose their vendor prefix to match the doc-14 rename map (notify_api_url -> api_url). Non-secret values (Notify API URL, Trello ATIP board, Sentinel customer id and log type) go in production.toml, the MaxMind database path default in base.toml. Credentials are read only under the published SecureString names: NOTIFY__SRE_USER_NAME, NOTIFY__SRE_CLIENT_SECRET, TRELLO__APP_KEY, TRELLO__TOKEN, OPSGENIE__INTEGRATIONS_KEY, SENTINEL__SHARED_KEY (no terraform change). extra=forbid. The unread OPSGENIE_KEY and MAXMIND_KEY names are not migrated. Ride-along (2026-10-23, TASK-112 AC #3 scoping): integrations/notify/client.py:115 skips the revoke call when ENVIRONMENT is not production; once api_url is set only in production.toml the existing 'api_url missing' branch already stops the call elsewhere, so the ENVIRONMENT check is deleted (decisions/configuration.md: ENVIRONMENT is identity only).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each of the five slices reads its non-secret values from the files and its credentials from <SLICE>__<FIELD> names
- [ ] #2 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [ ] #3 integrations/opsgenie/ no longer has create_alert (no caller since the Notify key-revocation change): the function, its export and its tests are deleted
- [ ] #4 Every reader of these slices builds them at use, not at import (found 2026-10-26 in TASK-111.10.1: integrations/trello/client.py:7, opsgenie/client.py:10, sentinel/client.py:15, notify/client.py:15 read at import, and a slice on the files fails closed before the app factory installs them); a fresh-interpreter import test proves the provider caches stay empty, as tests/unit/server/test_server_app_import_google_settings_lazy.py does
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-27T11:26:00Z

---

2026-10-27 (TASK-111.11.1 session, human: create every parameter ahead of its reader): SENTINEL_CUSTOMER_ID and TRELLO_ATIP_BOARD are non-public values (decisions/configuration.md 2026-10-27). They are read as SENTINEL__CUSTOMER_ID and TRELLO__ATIP_BOARD from the environment only, never production.toml, so the description's 'Trello ATIP board, Sentinel customer id ... go in production.toml' is superseded. Their /sre-bot parameters are created by the standalone ssm PR before 111.11.1, with values put from the blob lines. Finding to assess in planning: Microsoft retired the Azure Monitor HTTP Data Collector API (customer id plus shared key) on 2026-09-14 (https://azure.microsoft.com/en-us/updates/azure-monitor-data-collection-api-retirement/); the replacement is the DCR-based Logs Ingestion API with Entra token auth. Check whether production Sentinel sends still succeed (the sentinel client's log events since 2026-09-14). If they fail, the slice is rebuilt on the Logs Ingestion API or deleted rather than moved, and SENTINEL__CUSTOMER_ID and SENTINEL__SHARED_KEY are removed in the contract.

---

created: 2026-10-27T11:45:00Z

---

2026-10-27: the Sentinel retirement finding is TASK-171 (doc-11 row Z2). This task's Sentinel part follows its ruling: rebuild on the Logs Ingestion API, or delete.

---
<!-- COMMENTS:END -->
