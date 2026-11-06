---
id: TASK-171
title: >-
  Assess the Sentinel integration after the Azure HTTP Data Collector API
  retirement; rebuild it on the Logs Ingestion API or delete it
status: To Do
assignee: []
created_date: '2026-10-27T11:44:00Z'
updated_date: '2026-11-06T19:02:00Z'
labels:
  - integrations
  - security
dependencies: []
priority: high
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
- [ ] #5 Post-cutover production telemetry confirms zero requests to *.ods.opinsights.azure.com from sre-bot for at least 24h, with explicit positive evidence capture (queries/log extracts) recorded in notes.
- [ ] #6 After cutover, events are positively observed reaching the configured DCE/DCR stream for 24h with no 403 responses and SREBotSentinelSendFailed=0; evidence must include successful ingestion records so a no-traffic window cannot pass.
- [ ] #7 Sentinel Logs Ingestion settings (DCE endpoint, DCR immutable id, stream name, tenant/client/identity-federation inputs) are Terraform-managed; SENTINEL__SHARED_KEY remains in SSM/task definition until cutover is verified, then is removed in the cleanup slice.
- [ ] #8 Operational analytics/workbooks that depended on legacy Sentinel table outputs still return expected results after migration, or documented updates are applied to query the new table/stream outputs with verification evidence.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PENDING HUMAN APPROVAL — staged decomposition required before implementation

Scope guard
- TASK-171 remains an integration behavior migration (legacy HTTP Data Collector -> Logs Ingestion API) for existing Sentinel sends; it does NOT absorb TASK-25.7 architectural relocation of audit sink/client contract boundaries.

Grounded current-state inventory (from repo survey)
- Legacy sender: app/integrations/sentinel/client.py sends to https://{customer_id}.ods.opinsights.azure.com/api/logs?api-version=2016-04-01 using shared-key HMAC signing (send_event/post_data/build_signature).
- Current callers: app/api/v1/routes/webhooks.py; app/modules/provisioning/entities.py; app/modules/incident/{incident.py,incident_alert.py,incident_conversation.py,incident_helper.py,notify_stale_incident_channels.py}.
- Current settings contract: app/integrations/sentinel/settings.py + app/config/{base.toml,production.toml} + terraform/ssm.tf (SENTINEL__CUSTOMER_ID, SENTINEL__SHARED_KEY), with env-only secrets introduced in TASK-111.15.1.
- Related task constraints: TASK-111.15.1 is Done and explicitly keeps Sentinel shared-key slice pending TASK-171 ruling; TASK-25.7 is To Do and depends on TASK-171, so this migration must preserve behavior without folding in client-contract relocation.

External contract references to enforce
- Microsoft Logs Ingestion URI/headers require POST {endpoint}/dataCollectionRules/{dcrImmutableId}/streams/{streamName}?api-version=... with OAuth bearer token (scope audience monitor.azure.com) and JSON payload matching DCR stream expectations.
- Official migration guidance states HTTP Data Collector API is deprecated/end-of-support while ingestion may continue for TLS-compliant clients; continued apparent success cannot be treated as safe steady-state.
- cds-snc terraform-modules/sentinel_forwarder README shows org precedent for DCE/DCR + Entra token auth and hub-based secretless federation; it also records Cognito federation inputs as removed in that module path, so any Cognito-based assumption for sre-bot must be explicitly revalidated against current platform ownership decisions before implementation.

Single-PR size gate verdict
- Gate trips (non-negotiable): change spans app transport/auth logic + settings + terraform/SSM/ECS/IAM/federation + production observability and cutover evidence + cleanup/removal ordering where single revert is not a safe rollback (legacy API support is retired/unreliable).
- Therefore this task is a coordinator requiring expand/migrate/contract slices. Subtasks are NOT created yet; human approval required first.

Proposed slice breakdown (for approval before creating subtasks)
1) Slice A — Federation and Azure ingestion prerequisites (expand, infra-first)
   - Files (expected): terraform/ssm.tf, terraform/ecs.tf, terraform/templates/sre-bot.json.tpl, terraform/iam.tf (if role grants needed), plus decisions/runbook references touched only if contracts change.
   - Additive outputs: DCE_ENDPOINT, DCR_IMMUTABLE_ID, STREAM_NAME, ARM_TENANT_ID, ARM_CLIENT_ID, COGNITO_IDENTITY_POOL_ID, COGNITO_DEVELOPER_PROVIDER_NAME (or approved alternative federation inputs) injected without changing runtime behavior.
   - Estimated size: ~6-9 production files, ~140-260 LOC.

2) Slice B — Additive Logs Ingestion client path behind default-safe behavior (expand)
   - Files (expected): app/integrations/sentinel/client.py, app/integrations/sentinel/settings.py, app/config/base.toml, app/config/production.toml, and sentinel-related tests.
   - Behavior: implement token-based Logs Ingestion send path with async-safe caching/retry/error mapping while preserving current default behavior until explicit cutover flag/setting is enabled.
   - Estimated size: ~7-10 production files, ~220-360 LOC.

3) Slice C — Controlled cutover + 24h positive observation (migrate)
   - Files (expected): config/terraform wiring for enabling new path, observability checks/runbook/task-check scripts, and any dashboard/workbook query updates tracked as repository artifacts.
   - Behavior: enable Logs Ingestion path in production, record positive ingestion evidence for 24h (success proof + no 403 + SREBotSentinelSendFailed=0), confirm no *.ods.opinsights.azure.com calls.
   - Estimated size: ~5-8 production files, ~120-220 LOC.

4) Slice D — Contract cleanup/removal (contract)
   - Files (expected): app/integrations/sentinel/settings.py, terraform/ssm.tf, terraform/templates/sre-bot.json.tpl, related docs/runbook/task-check references.
   - Behavior: remove shared-key dependency and legacy endpoint path only after Slice C evidence is accepted; retire SENTINEL__SHARED_KEY from SSM/task definition in ordered cleanup.
   - Estimated size: ~6-10 production files, ~140-260 LOC.

Ordered implementation steps (file-specific)
1. Confirm platform-owned federation sequence and least-privilege trust contract (hub role/account, audience, provider, subject stability) and freeze required env/secret names before code changes.
2. Add Terraform-managed ingestion/federation settings in terraform/* and ECS template wiring; keep legacy SENTINEL__* intact.
3. Extend app/integrations/sentinel/settings.py with new ingestion config types; preserve existing fields for compatibility during expand/migrate.
4. Refactor app/integrations/sentinel/client.py to support dual-path sender (legacy + Logs Ingestion) with explicit runtime selection, token acquisition caching, retry/backoff policy, and structured failure telemetry.
5. Keep all existing caller interfaces unchanged at current call sites (webhooks/provisioning/incident modules) to avoid blast-radius expansion.
6. Add/adjust tests in sentinel client/settings + dependent call-site tests for both paths and failure families.
7. Execute cutover by configuration order only (infra first, then app deploy, then runtime switch), capture required positive telemetry for 24h.
8. After evidence acceptance, remove legacy shared-key path/config and cleanup docs/task checks.

AC -> step -> test matrix (planned; filenames exact)
- Existing AC2 (ruling + ADR update)
  - Steps: 1, 7, 8
  - Tests/evidence artifacts: app/tests/integrations/sentinel/test_sentinel_client.py (new logs-ingestion contract cases), backlog notes with production verification links/outputs.
- Existing AC3 (if rebuilt, events reach target with no shared key)
  - Steps: 4, 6, 7, 8
  - Tests: app/tests/integrations/sentinel/test_sentinel_client.py; app/tests/unit/integrations/sentinel/test_sentinel_settings_load.py; app/tests/api/v1/test_webhooks.py; app/tests/modules/provisioning/test_provisioning_entities.py; app/tests/modules/incident/test_incident_*.py (targeted call-path regressions).
- Existing AC4 (replace TASK-111.15.1 Sentinel slice contract)
  - Steps: 2, 3, 7, 8
  - Tests/evidence: settings load tests + task-check/runbook evidence for parameter/task-definition cleanup.
- New AC5 (no *.ods.opinsights.azure.com after cutover)
  - Steps: 7, 8
  - Evidence: production query/log proof recorded in notes; optional regression unit test ensures legacy URL path disabled when cutover flag enabled.
- New AC6 (24h DCE/DCR ingest, no 403, SREBotSentinelSendFailed=0, positive evidence)
  - Steps: 4, 7
  - Tests/evidence: client failure/success telemetry tests + production 24h ingestion evidence bundle.
- New AC7 (Terraform-managed settings; remove shared key only post-verify)
  - Steps: 2, 8
  - Tests/evidence: terraform plan/apply evidence + post-cutover task-definition/SSM proof.
- New AC8 (analytics/workbooks still return results or updated)
  - Steps: 7, 8
  - Tests/evidence: workbook/query validation outputs linked in notes.

Assumptions and doubts (must be resolved before implementation)
- Assumption: existing payload shape can be ingested by target DCR stream without caller payload/model changes; verify against actual DCR stream schema and sample events before cutover.
- Doubt: user-reported Cognito developer identity flow may conflict with current org module precedent (hub-role secretless flow, Cognito removed there); requires platform owner decision and documented contract.
- Doubt: exact ownership/source-of-truth for DCE/DCR/table/workbooks may be outside this repo; requires named human owners and explicit verification procedure.
- Assumption: existing event names consumed by analytics must be preserved; verify with workbook/query owners.

Blast radius, rollback, and ordering
- Blast radius: lost Sentinel audit/incident visibility, false negatives in security workflows, and broken analytics/workbooks.
- Rollback: retired Data Collector path is NOT a reliable rollback target. Safe rollback is staged: keep dual-path/legacy config until 24h evidence passes; if cutover fails, disable new path via config while keeping legacy path intact during migration window.
- Ordering constraints: infra prerequisites must land before app cutover; cleanup/removal only after accepted production evidence.

Domain-model evolution gate
- Not applicable unless migration forces changes to emitted event payload/domain models. Current plan preserves caller payload contracts and migrates transport/auth path only. If DCR mapping requires payload schema changes, domain-model gate must be added before implementation approval.

Human checkpoint requested
- Approve/revise slice boundaries and dependencies above before any subtask creation.
- After approval, create subtasks (A-D) with explicit --dep/--parent wiring and then plan only the first slice.

Planning review clarification (supersedes conflicting proposal details above; still pending human approval):
- Current upstream sentinel_forwarder README explicitly says Cognito federation was removed in v14.0.0. Its secretless path is ECS role equivalent -> sts:AssumeRole hub -> sts:GetWebIdentityToken (audience api://AzureADTokenExchange, duration <=300s) -> Entra client assertion for a user-assigned managed identity. Azure federated credential issuer is hub account issuer, subject is hub role ARN; Monitoring Metrics Publisher is required on each target DCR. Source verified 2026-11-06: https://raw.githubusercontent.com/cds-snc/terraform-modules/main/sentinel_forwarder/README.md (Auth / Hub setup). This is current public documentation, not proof of deployed forwarder versions or hub trust. Do not add Cognito inputs or silently choose an alternative until platform owner confirms deployed contract and exact hub role ARN in account 274536870005. No stored Entra client secret.
- Exact ingestion URL contract: POST {DCE_ENDPOINT}/dataCollectionRules/{DCR_IMMUTABLE_ID}/streams/{STREAM_NAME}?api-version=2023-01-01; scope https://monitor.azure.com/.default; JSON array must match DCR stream schema, including TimeGenerated transformation and existing analytics field names.
- Retained survey call-site evidence: app/integrations/sentinel/client.py:73-114; app/api/v1/routes/webhooks.py:148; app/modules/provisioning/entities.py:68-88; app/modules/incident/incident.py:192; incident_alert.py:64,105; incident_conversation.py:447,452,457; incident_helper.py:508; notify_stale_incident_channels.py:49 (all latter files under app/modules/incident). Preserve the existing synchronous caller interface; async-safe networking cannot mean changing send_event into an unawaited coroutine. Concrete auth runtime source, SDK availability/version, caller exception semantics, exact new-file paths and retry ownership must be resolved in the slice-specific plan, not assumed from this proposal.
- Proposed new tests, distinct from existing regression files: app/tests/unit/integrations/sentinel/test_sentinel_token_acquire.py (federation/Entra failure, expiry, cache concurrency, redacted logs); test_sentinel_ingestion_send.py in the same directory (2023-01-01 URL, bearer auth, JSON array/TimeGenerated, 429 Retry-After bounded retry, transient 5xx, permanent 400/403, timeouts/cancellation, no automatic legacy fallback); test_sentinel_transport_select.py (default preserved during expansion, explicit new-path selection); test_sentinel_settings_load.py (env-only credential identifiers and invalid/incomplete selected-path configuration). Verify exact repository test layout before authoring. Existing wildcard regression list above is an inventory category, not an exact executable selector.
- Confirm whether SREBotSentinelSendFailed is already provisioned; if absent add an explicit metric/alarm and tested failure event mapping. Record event volumes/IDs in Azure as positive 24h proof, CloudWatch failures and 403 counts, no legacy requests, and analytics/workbook query outputs. Inventory external Azure resource ownership and analytics consumers before slice approval; do not assume they are managed in this AWS-only Terraform root.
- Rollback correction: retaining legacy configuration supports reversing deployment mechanics, NOT restoring proven ingestion. No automatic fallback or claim that disabling the new path restores service. Failed cutover requires incident escalation and a forward fix; any pause must explicitly declare lost forwarding and use a separately verified replay/recovery procedure if one exists. Do not invent a buffering system within this fix. Keep shared-key deletion gated on human-accepted 24h evidence.
- Proposed A -> B -> C -> D dependency order is a breakdown proposal only. Slice A may need separate externally owned Azure/hub prerequisites. No executable implementation plan is approved, no subtasks created, and no production evidence has been verified in this session.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- 2026-10-28 production evidence (human, Logs Insights on /ecs/sre-bot-app, last 30 days = since 2026-09-28, the group's retention): sentinel_event_sent 41604, log_to_sentinel_error 1, sentinel_event_error 1. Sends through the HTTP Data Collector API still succeed after the announced 2026-09-14 retirement, so the integration is live and may stop without notice. Found in TASK-111.15.1 planning: the app reads SENTINEL_* only from the blob .env that entry.sh writes.

2026-10-28 (human, TASK-111.15.1 plan review): the reads move in 111.15.1, before this ruling, so stopping the blob fetch keeps sends working; this task stays at row Z2 (last) for the rebuild-or-delete ruling. AC #3 reworded: 111.12's Sentinel part is now 111.15.1's, and the ruling acts on that slice. The slice keeps slice-level credential fields rather than a [sentinel.tenant] entry (tolerated in configuration.md until this task).

2026-10-28 direction (human): the integration will be rebuilt on the Logs Ingestion API (DCE, DCR immutable id and stream), not deleted; not yet prioritised because the legacy API still accepts sends. AC #2's ruling records the target shape and credential model when planned.

2026-11-06 incident report (user-provided, not independently verified in this planning session): urgent Sentinel production migration requested outside normal queue priority after reported operational risk with legacy Data Collector dependency. User-provided desired success conditions to encode in acceptance criteria: (a) no calls to *.ods.opinsights.azure.com after cutover; (b) positive 24h ingestion evidence into DCE/DCR stream with zero 403 and SREBotSentinelSendFailed=0 (silence alone is insufficient); (c) DCE/DCR/stream/federation settings Terraform-managed and SENTINEL__SHARED_KEY removed from SSM/task definition only after verified cutover; (d) existing analytics/workbooks continue returning expected results or are updated for the new table. Attribution: user incident direction at planning kickoff, 2026-11-06.

2026-11-06 human planning checkpoint: keep the four-slice decomposition proposal pending; do not create subtasks. Authentication direction remains blocked until the platform owner confirms the deployed reference/version and federation contract (Cognito versus current IAM outbound federation). Task remains To Do at High priority. No production code, Terraform, ADR, deployment or feature work-queue changes authorized or made.
<!-- SECTION:NOTES:END -->
