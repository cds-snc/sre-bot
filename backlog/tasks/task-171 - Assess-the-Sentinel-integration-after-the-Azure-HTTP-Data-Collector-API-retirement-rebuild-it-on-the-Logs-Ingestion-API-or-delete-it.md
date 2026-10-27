---
id: TASK-171
title: >-
  Assess the Sentinel integration after the Azure HTTP Data Collector API
  retirement; rebuild it on the Logs Ingestion API or delete it
status: To Do
assignee: []
created_date: '2026-10-27T11:44:00Z'
labels:
  - integrations
  - security
dependencies: []
priority: low
ordinal: 452000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Microsoft retired the Azure Monitor HTTP Data Collector API (workspace id as customer id, plus shared key) on 2026-09-14 (https://azure.microsoft.com/en-us/updates/azure-monitor-data-collection-api-retirement/). The replacement is the DCR-based Logs Ingestion API: a data collection endpoint, a data collection rule's immutable id and stream, and Entra token authentication instead of the shared key. integrations/sentinel/client.py still sends through the old API (SENTINEL_CUSTOMER_ID, SENTINEL_LOG_TYPE, SENTINEL_SHARED_KEY, read at import). Its callers are api/v1/routes/webhooks.py, modules/provisioning/entities.py and the modules/incident files (incident, incident_alert, incident_conversation, incident_helper, notify_stale_incident_channels). Other repositories that write to the same tables have already moved (human, 2026-10-27), so the destination tables and DCRs may already exist.

Found 2026-10-27 in TASK-111.11.1 (doc-11). Not the most critical row: it runs as a standalone row in the doc-11 Work queue.

To decide when planned:
- Whether production sends have failed since 2026-09-14 (the sentinel client's log events).
- Whether the bot still needs to write to Sentinel, and which events.
- If it does: the target shape on the Logs Ingestion API, using a DCR the other repositories already use or a new one, and the Entra credential (a federated credential from the ECS task role, no stored secret, if the platform allows it; decisions/service-accounts.md one credential per role).
- If it doesn't: delete the client and its callers' sends.
- TASK-111.12's Sentinel part follows this task's ruling. SENTINEL__CUSTOMER_ID and SENTINEL__SHARED_KEY are removed in the 111.15 contract if they are no longer read.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Production evidence recorded: whether Sentinel sends succeed or fail since 2026-09-14, from the sentinel client's log events
- [ ] #2 A ruling recorded in the task and the affected ADR (outbound-clients.md or a new integration section): rebuild on the Logs Ingestion API (endpoint, DCR immutable id and stream, credential model) or delete the integration
- [ ] #3 TASK-111.12's Sentinel scope and the 111.15 contract are updated to follow the ruling
- [ ] #4 If rebuilt: events reach the target table through the Logs Ingestion API, with no shared key; if deleted: no code sends to Sentinel and the sentinel settings and parameters are removed
<!-- AC:END -->
