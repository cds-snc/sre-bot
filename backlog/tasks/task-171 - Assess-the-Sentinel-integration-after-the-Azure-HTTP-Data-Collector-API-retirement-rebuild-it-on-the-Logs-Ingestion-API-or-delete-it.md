---
id: TASK-171
title: >-
  Assess the Sentinel integration after the Azure HTTP Data Collector API
  retirement; rebuild it on the Logs Ingestion API or delete it
status: To Do
assignee: []
created_date: '2026-10-27T11:44:00Z'
updated_date: '2026-10-28T23:17:00Z'
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
- [x] #1 Production evidence recorded: whether Sentinel sends succeed or fail since 2026-09-14, from the sentinel client's log events
- [ ] #2 A ruling recorded in the task and the affected ADR (outbound-clients.md or a new integration section): rebuild on the Logs Ingestion API (endpoint, DCR immutable id and stream, credential model) or delete the integration
- [ ] #3 If rebuilt: events reach the target table through the Logs Ingestion API, with no shared key; if deleted: no code sends to Sentinel and the sentinel settings and parameters are removed
- [ ] #4 The Sentinel slice TASK-111.15.1 moved onto the files ([sentinel] log_type, SENTINEL__CUSTOMER_ID and SENTINEL__SHARED_KEY as env_only fields) is replaced or deleted per the ruling, with its /sre-bot/SENTINEL__* parameters, the configuration.md tolerated item and the doc-14 rows
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- 2026-10-28 production evidence (human, Logs Insights on /ecs/sre-bot-app, last 30 days = since 2026-09-28, the group's retention): sentinel_event_sent 41604, log_to_sentinel_error 1, sentinel_event_error 1. Sends through the HTTP Data Collector API still succeed after the announced 2026-09-14 retirement, so the integration is live and may stop without notice. Found in TASK-111.15.1 planning: the app reads SENTINEL_* only from the blob .env that entry.sh writes.

2026-10-28 (human, TASK-111.15.1 plan review): the reads move in 111.15.1, before this ruling, so stopping the blob fetch keeps sends working; this task stays at row Z2 (last) for the rebuild-or-delete ruling. AC #3 reworded: 111.12's Sentinel part is now 111.15.1's, and the ruling acts on that slice. The slice keeps slice-level credential fields rather than a [sentinel.tenant] entry (tolerated in configuration.md until this task).

2026-10-28 direction (human): the integration will be rebuilt on the Logs Ingestion API (DCE, DCR immutable id and stream), not deleted; not yet prioritised because the legacy API still accepts sends. AC #2's ruling records the target shape and credential model when planned.
<!-- SECTION:NOTES:END -->
