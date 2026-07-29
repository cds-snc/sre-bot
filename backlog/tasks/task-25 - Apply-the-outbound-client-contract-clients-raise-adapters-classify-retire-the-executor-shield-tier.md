---
id: TASK-25
title: >-
  Apply the outbound-client contract: clients raise, adapters classify; retire
  the executor/shield tier
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-29 21:29'
labels:
  - clients
  - phase-3
  - architecture
milestone: m-3
dependencies:
  - TASK-22.5
  - TASK-23
references:
  - decisions/outbound-clients.md
  - decisions/operation-result.md
  - 'https://github.com/cds-snc/sre-bot/issues/1279'
priority: high
ordinal: 25000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/outbound-clients.md. One adaptation tier: integrations/<vendor>/ provides (1) authenticated client factories with SDK-native retry/timeouts configured once and (2) classify_<vendor>_error(exc) -> (OperationStatus, error_code, retry_after). Clients raise typed SDK exceptions - they never return OperationResult. The Protocol implementation (Path A composed service or Path B feature adapter) is the single boundary: try/except around the client call, classify, return OperationResult.

Steps:
1. Per vendor (aws, google_workspace, maxmind, slack): write classify_<vendor>_error mapping EXPECTED SDK exception families to status/error_code/retry_after. Unexpected exceptions (KeyError etc.) are NOT classified - they propagate.
2. Refactor AWSShield (app/integrations/aws/shield.py) into factory config + classification function; delete the standing wrapper class and the executor middle tier. Blocking SDK calls invoked from async code get asyncio.to_thread offload.
3. Update adapters/composed services to the try/except-classify pattern; remove pass-through secondary adaptation.
4. grep-verify: no time.sleep/tenacity/backoff retry loops in app/integrations/.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each vendor package exports exactly: factories, classify_<vendor>_error, settings
- [ ] #2 No client returns OperationResult; adapters/composed services produce it via the classification function (spot-check per vendor + import-linter contract from task-18)
- [ ] #3 Classification tests per vendor: each mapped exception family -> expected status/error_code/retry_after; one unmapped exception propagates
- [ ] #4 AWSShield class deleted; grep -rn "shield" app/integrations returns zero code hits
- [ ] #5 grep: no hand-rolled retry (time.sleep/tenacity/backoff) in app/integrations/
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 All tests pass; import-linter contracts still green
- [ ] #2 PR references decisions/outbound-clients.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PREREQUISITE: TASK-23 Done (one canonical module per vendor, no _next suffix) and TASK-22.5 Done. This task changes the ADAPTATION SHAPE, not just names.

TARGET CONTRACT (decisions/outbound-clients.md, Accepted, applies:target): integrations/<vendor>/ exposes exactly (1) authenticated client factories with SDK-native retry/timeouts configured once, and (2) classify_<vendor>_error(exc) -> (OperationStatus, error_code, retry_after), plus settings. Clients RAISE typed SDK exceptions and never return OperationResult. The single try/except+classify boundary lives in the Protocol implementation (composed service or feature adapter), which returns OperationResult (decisions/operation-result.md).

WHY THE FACADE/EXECUTOR GO (validated against vendor SDK guidance): boto3 provides built-in retry via botocore Config(retries={mode: standard|adaptive, total_max_attempts}) - exponential backoff base 2, circuit breaking, and an expanded transient/throttling error set - which fully replaces execute_aws_api_call._calculate_retry_delay + time.sleep. google-api-python-client offers request.execute(num_retries=). Hand-rolled sync retry loops also block the event loop; blocking SDK calls invoked from async are offloaded via asyncio.to_thread.

PER-VENDOR WORK:
- AWS: extract AWSShield._classify_client_error into a standalone classify_aws_error using the AWSSettings NOT_FOUND/UNAUTHORIZED/TRANSIENT catalogues; turn shield client construction (Config retries + connect/read timeouts + per-service caching) into a get_aws_client(service) factory; DELETE the AWSShield class and the execute_aws_api_call executor tier; canonical dynamodb/identity_store modules hold the boto3 client directly and raise; move try/except+classify into infrastructure/storage/service.py and the access-sync aws_identity_center adapter.
- Google: extract classify_google_error from google_service._handle_final_error; provide a factory on the canonical google_service module; delete the executor; the directory factory/google adapter owns classify.
- MaxMind: collapse the two coexisting shapes (legacy tuple geolocate()/healthcheck() + the ported OperationResult client from TASK-22.1) into one factory + classify_maxmind_error (AddressNotFoundError/ValueError/GeoIP2Error); MIGRATE the two legacy tuple consumers api/v1/routes/geolocate.py and jobs/scheduled_tasks.py to the classify boundary; delete the tuple client.
- Slack: classify_slack_error(SlackApiError -> status/error_code/retry_after, honoring Retry-After); factory; adapters classify.

SWEEP + VERIFY: delete residual hand-rolled retry loops (integrations/utils/api.py time.sleep, google_service time.sleep); grep shows no time.sleep/tenacity/backoff in app/integrations/ (AC#5); grep -rn shield app/integrations returns zero (AC#4); each vendor exports factories + classify + settings only (AC#1); no client returns OperationResult, verified by import-linter TASK-18 + spot-check (AC#2); classification tests per vendor map each expected exception family and prove one unmapped exception propagates (AC#3).

TEST MIGRATION: touched vendor tests relocate into tests/unit/integrations/<vendor>; add per-vendor classification unit tests; legacy trees only shrink.

SIZE GATE - REQUIRED DECOMPOSITION BEFORE IMPLEMENTATION: this task spans 4 vendors + adapter rewrites + MaxMind consumer migration + shield/executor deletion, far exceeding the single-PR gate. Before any code, decompose into per-vendor subtasks (proposed: 25.1 aws shield->factory+classify, 25.2 google, 25.3 maxmind incl. legacy tuple-consumer migration, 25.4 slack) plus a final sweep slice (delete utils/api.py retry, run grep/import-linter gates). One vendor per reviewable PR. This high-level plan is the umbrella; detailed per-subtask planning happens when TASK-25 is scheduled.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-29 21:12
---
Upstream dependency repointed from TASK-22 to TASK-22.5. Inherited from the TASK-22 sprint: (1) integrations/maxmind/client.py will contain BOTH a legacy tuple|str geolocate()/bool healthcheck() (used by api/v1/routes/geolocate.py and jobs/scheduled_tasks.py) AND a ported OperationResult client (used by packages/geolocate) — this task's classify contract + unification must reconcile the two and migrate the two legacy tuple consumers; (2) storage/access-sync/directory adapters will already be on the _next module functions returning OperationResult — this task moves the raise/classify boundary into those adapters and strips OperationResult out of the clients.
---
<!-- COMMENTS:END -->
