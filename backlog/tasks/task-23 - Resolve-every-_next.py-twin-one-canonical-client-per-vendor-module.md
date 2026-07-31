---
id: TASK-23
title: 'Resolve every _next.py twin: one canonical client per vendor module'
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-31 18:49'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.4
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - 'https://github.com/cds-snc/sre-bot/issues/1277'
priority: high
ordinal: 23000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/outbound-clients.md (Migration: "_next.py twins resolve into this shape"). Today app/integrations/ contains a fourth client generation: _next.py twins beside originals (aws/client_next.py, aws/dynamodb_next.py, aws/identity_store_next.py, google_workspace/google_directory_next.py, google_workspace/gmail_next.py, google_workspace/google_service_next.py).

Steps:
1. For each twin pair, diff the original vs _next and pick the survivor per the decided contract (clients raise typed SDK exceptions, SDK-native retry configured at construction, no hand-rolled retry, no OperationResult in clients).
2. Rename the survivor to the canonical name (no _next suffix), migrate its consumers, delete the loser. One vendor per PR.
3. Where neither twin matches the contract, converge on the closer one and fix it in the same PR (contract enforcement itself completes in task-25).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 find app/integrations -name "*_next.py" returns zero files
- [ ] #2 Each vendor module has exactly one client construction path (get_aws_client for AWS, the Google Directory factory for Google); the _next-suffixed generation's execute_aws_api_call / execute_google_api_call string-dispatchers and the get_google_api_command_parameters docstring scraper no longer exist in app/integrations/ (decisions/sdk-typing.md dispatcher/scraper checks pass for the _next generation). NOTE: a separate, non-_next execute_aws_api_call (integrations/aws/client.py) and execute_google_api_call (integrations/google_workspace/google_service.py) generation also exists with many live consumers - deleting those is TASK-25.2 (AWS) and TASK-25.1 (Google) scope, not this task's; sdk-typing.md's repo-wide dispatcher checks only pass fully once TASK-25.1 and TASK-25.2 are also Done
- [ ] #3 The remaining _next consumers (idempotency store, resilience retry store, and any others found by grep) are converged onto the shared get_aws_client + classify_aws_error primitive from TASK-22.2 with behavior-neutral OperationResult outcomes; all consumers import the canonical modules and tests pass per vendor PR
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 No behavior change observable from feature code (existing tests green)
- [ ] #2 PR series references decisions/outbound-clients.md and decisions/sdk-typing.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
RESEQUENCED (2026-07-31, decisions/sdk-typing.md): this task is no longer "pick the survivor twin and rename it" - the consumer surfaces (storage, access-sync, directory) already migrated DIRECTLY to canonical factory+classify in TASK-22.2/22.3/22.4, and the canonical AWS/Google primitives already exist. This task now DELETES the residual _next dispatcher generation and converges its remaining (non-facade) consumers onto those primitives. It is the task that makes decisions/sdk-typing.md's "find *_next.py == 0" and "no generic dispatcher" checks pass.

PREREQUISITE: TASK-22.4 Done (so get_aws_client + classify_aws_error from TASK-22.2 and the Google Directory factory + classify_google_error from TASK-22.4 all exist and are proven by the migrated consumers).

TWIN/DISPATCHER INVENTORY (re-grep at implementation): integrations/aws/{client_next.py (the execute_aws_api_call dispatcher + time.sleep retry), dynamodb_next.py, identity_store_next.py}; integrations/google_workspace/{google_service_next.py (execute_google_api_call + retry), gmail_next.py, google_directory_next.py}. After TASK-22.x their FACADE-migrated consumers are gone; the REMAINING consumers to converge are the non-facade ones - notably the idempotency store and the resilience retry store on dynamodb_next (grep-confirm the full set before editing; also check identity_store_next and the google _next modules for stragglers).

SCOPE:
1. Converge every remaining dynamodb_next / identity_store_next consumer onto get_aws_client + classify_aws_error (TASK-22.2's primitive): idempotency store and resilience retry store call the typed boto3 client directly inside try/except+classify, behavior-neutral (same OperationResult outcomes, same ConditionalCheckFailedException handling their claim/lease/dedup primitives depend on).
2. Converge any remaining google_service_next / google_directory_next / gmail_next consumer onto the Google factory + classify_google_error (TASK-22.4). gmail_next with zero consumers is simply deleted.
3. Delete every integrations *_next.py file and the generic dispatchers they contained (execute_aws_api_call, execute_google_api_call) plus the get_google_api_command_parameters docstring scraper if it survives outside the directory path.
4. Ensure exactly one construction path per vendor remains (get_aws_client; the Google Directory factory). Do NOT delete integrations/aws/shield.py here - AWSShield feeds remaining AWS services and is retired in TASK-25.

PR SLICES (one vendor per PR, behavior-neutral):
- PR A - AWS: converge idempotency + resilience stores onto get_aws_client/classify_aws_error; delete dynamodb_next.py, identity_store_next.py, client_next.py; grep both old names to zero.
- PR B - Google: converge any residual google _next consumer onto the TASK-22.4 factory/classify; delete google_service_next.py, google_directory_next.py, gmail_next.py.

TEST MIGRATION: touched vendor tests relocate into tests/unit/integrations/<vendor>; legacy trees only shrink. Add convergence coverage for the idempotency/resilience stores (behavior-neutral: same claim/lease/dedup outcomes).

AC-TO-STEP: AC#1 -> Steps 3 (find *_next.py == 0). AC#2 -> Steps 3-4 (dispatchers/scraper deleted; one path per vendor; sdk-typing.md checks pass). AC#3 -> Steps 1-2 (idempotency/resilience + any residual consumers converged, behavior-neutral). DoD -> per-vendor PR green + import-linter (TASK-18) + PR cites outbound-clients.md/sdk-typing.md.

SIZE GATE: mechanical deletion + converging ~2-3 infra consumers onto an existing primitive, no new logic - two per-vendor PRs, each within the ~400 LOC / ~10 file gate.

RISKS / DOUBTS (verify at impl): (a) the idempotency + resilience stores rely on ConditionalCheckFailedException as their contention signal - classify_aws_error must preserve that error_code exactly (TASK-22.2 already requires this; re-assert here); (b) grep BOTH the *_next names AND execute_aws_api_call/execute_google_api_call after each PR to catch stragglers (DI, providers, __init__ re-exports, tests); (c) confirm no integration module OTHER than the _next files imports client_next's execute_aws_api_call before deleting it.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-29 21:12
---
Upstream dependency repointed from TASK-22 to its final subtask TASK-22.5 (the slice that actually deletes infrastructure/clients/). TASK-22's subtasks (22.1-22.5) wire consumers to the integrations/ modules AS THEY EXIST TODAY, including the _next.py twins. This task then renames those survivors to canonical names and re-migrates the same consumers — an intentional, conflict-free second touch in a later PR of the same sprint. Note the MaxMind handoff: TASK-22.1 leaves an OperationResult client coexisting beside the legacy tuple geolocate()/healthcheck() in integrations/maxmind; unifying those two shapes is TASK-25, not this task.
---

created: 2026-07-31 17:07
---
RESEQUENCED per decisions/sdk-typing.md (2026-07-31). Previously this task renamed the surviving _next twin to a canonical name after TASK-22.x wired consumers onto it - a second touch of every consumer. Under the resequenced plan, TASK-22.2/22.3/22.4 migrate their consumers DIRECTLY to canonical factory+classify, so there is no twin to rename. This task is now the DELETION of the _next dispatcher generation plus convergence of its remaining non-facade consumers (idempotency store, resilience retry store) onto the get_aws_client/classify_aws_error primitive established in TASK-22.2.

Dependency changed from TASK-22.5 to TASK-22.4 (the AWS + Google primitives exist after 22.4; deleting integrations/*_next does not require the facade-tree deletion in 22.5, so this can run in parallel with 22.5). AC#2 retargeted from "each vendor has exactly one client construction path" to also assert the generic dispatchers + docstring scraper are gone. AC#3 retargeted from "all consumers import the canonical module" to explicitly name the idempotency/resilience convergence. AWSShield deletion stays in TASK-25 (it feeds the remaining AWS services).
---

created: 2026-07-31 18:49
---
Correction (2026-07-31): AC#2's wording was over-broad - it implied ALL execute_aws_api_call/execute_google_api_call occurrences disappear once this task is Done, but this task's own inventory only ever covered the _next-suffixed generation. Repo-wide grep (done while verifying AWS/Google client-migration task coverage) found a separate, non-_next execute_aws_api_call (integrations/aws/client.py, ~9 services/14 consumer files) and execute_google_api_call (integrations/google_workspace/google_service.py, 6 surfaces/16 consumer files) generation, each with far more live consumers than the _next twins. Those are now tracked as TASK-25.2 (AWS remainder) and TASK-25.1 (Google remainder) respectively. AC#2 reworded to scope explicitly to the _next generation and cross-reference the sibling tasks rather than silently over-promising.
---
<!-- COMMENTS:END -->
