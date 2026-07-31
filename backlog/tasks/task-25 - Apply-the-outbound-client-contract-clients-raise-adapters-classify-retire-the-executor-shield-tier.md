---
id: TASK-25
title: >-
  Apply the outbound-client contract: clients raise, adapters classify; retire
  the executor/shield tier
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-31 18:50'
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
  - decisions/sdk-typing.md
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
- [ ] #2 PR references decisions/outbound-clients.md and decisions/sdk-typing.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
RESEQUENCED (2026-07-31, decisions/sdk-typing.md). This task NO LONGER converts AWS DynamoDB/IdentityStore or Google Directory (the infrastructure/directory Provider path) - those surfaces were migrated directly to the raise/classify contract in TASK-22.2/22.3/22.4, and the shared integrations/aws get_aws_client + classify_aws_error primitive plus the Google Directory factory + classify_google_error already exist. The _next dispatcher generation is deleted in TASK-23. This task finishes the REMAINDER of the outbound-client contract and retires the last of the old tiers.

PREREQUISITE: TASK-22.5 (facade tree deleted) + TASK-23 (_next generation deleted) Done for the MaxMind/Slack remainder below. The Google remainder (TASK-25.1) and AWS remainder (TASK-25.2) do NOT share this prerequisite - each depends only on the TASK-22.x primitive it reuses (TASK-22.4 for Google; TASK-22.2/22.3 for AWS), since neither touches the deprecated facade tree (TASK-22.5's scope) or the _next twins (TASK-23's scope).

REMAINING SCOPE (decompose into per-vendor subtasks before coding - each one reviewable PR):
- Google remainder - DECOMPOSED 2026-07-31 into a real subtask, TASK-25.1 (was sketched here as "25.2"; the actual assigned ID is TASK-25.1 since no other REMAINING SCOPE bullet had been created as a real backlog task yet). Finding that drove the decomposition: this was NOT a small residual - a repo-wide grep confirmed ALL 11 files in integrations/google_workspace/ still route through the execute_google_api_call dispatcher (google_service.py/google_service_next.py), consumed by 16 distinct legacy production files across 6 live surfaces (directory/drive/docs/calendar/sheets/meet) plus gmail.py/gmail_next.py with zero consumers (delete candidates). TASK-25.1 is a coordinator further decomposed into TASK-25.1.1 (Calendar+Meet, smallest, first + gmail deletion), TASK-25.1.2 (Docs), TASK-25.1.3 (Sheets), TASK-25.1.4 (legacy modules/ Directory consumers - a separate path from TASK-22.4's Provider abstraction), TASK-25.1.5 (Drive, largest, done last), each chained --dep on the prior sibling, the first depending on TASK-22.4 directly.
- AWS remainder + AWSShield retirement - DECOMPOSED 2026-07-31 into a real subtask, TASK-25.2. Finding that drove the decomposition (mirrors the Google one exactly): the original "organizations, sso_admin, config, guardduty, cost_explorer, security_hub, lambdas, sqs" list undercounted the scope in TWO ways - (1) it omitted that integrations/aws/identity_store.py and dynamodb.py (the NON-_next originals, a THIRD AWS generation predating even _next) ALSO route through the same dispatcher with their OWN separate consumer sets, distinct from TASK-22.2/22.3's infrastructure/storage and packages/access/sync scopes; (2) the underlying dispatcher itself - integrations/aws/client.py's execute_aws_api_call/handle_aws_api_errors - was never named anywhere as needing deletion (TASK-23's inventory only covers client_next.py). handle_aws_api_errors is worse than its Google counterpart: it SWALLOWS every exception and returns False, never re-raising - migration is NOT zero-diff, each consumer's new error-path behavior needs explicit human review. Total: 9 services (of the original 8 named + identity_store + dynamodb, minus sqs which has zero consumers and is just deleted), 14 distinct production consumer files (all app/modules/ or app/jobs/, none in packages/). TASK-25.2 is a coordinator further decomposed into TASK-25.2.1 (Config/CostExplorer/GuardDuty/SecurityHub account-health cluster, smallest/most isolated, first), TASK-25.2.2 (legacy non-_next DynamoDB, reusing TASK-22.2's primitive directly, dep TASK-22.2), TASK-25.2.3 (Lambdas + delete zero-consumer sqs.py), TASK-25.2.4 (Organizations+SSO-Admin+legacy non-_next IdentityStore, largest/most consumer-overlap, done last, reusing TASK-22.3's identitystore primitive, dep TASK-22.3), each chained --dep on the prior sibling. integrations/aws/client.py itself is deleted as TASK-25.2.4's final step once it has zero remaining callers. AWSShield (app/integrations/aws/shield.py) retirement (AC#4) is NOT yet folded into TASK-25.2 - it is a SEPARATE remaining concern (shield.py is a different, closer-to-target AWS generation per prior planning notes) and stays tracked at this umbrella level until its own consumers are inventoried.
- MaxMind unification (not yet decomposed into a real subtask): collapse the two coexisting shapes TASK-22.1 left (legacy tuple geolocate()/healthcheck() + the OperationResult client) into one factory + classify_maxmind_error (AddressNotFoundError/ValueError/GeoIP2Error); MIGRATE the two legacy tuple consumers api/v1/routes/geolocate.py and jobs/scheduled_tasks.py to the classify boundary; delete the tuple client. Will be created as a real subtask when scheduled.
- Slack (not yet decomposed into a real subtask): classify_slack_error(SlackApiError -> status/error_code/retry_after honoring Retry-After) + factory; adapters classify. (Slack is untouched by 22.x/23.) Will be created as a real subtask when scheduled.
- AWSShield retirement (not yet decomposed into a real subtask): refactor app/integrations/aws/shield.py into factory config + classify_aws_error, delete the standing wrapper class; inventory its actual consumers (distinct from the client.py generation TASK-25.2 covers) before decomposing. grep -rn "shield" app/integrations -> zero (AC#4).
- Final sweep: grep shows no time.sleep/tenacity/backoff retry loops in app/integrations/ (AC#5), no execute_*_api_call dispatcher, no get_google_api_command_parameters; each vendor exports exactly factories + classify_<vendor>_error + settings (AC#1); no client returns OperationResult (AC#2, spot-check + import-linter TASK-18).

WHY THE OLD TIERS GO (unchanged): boto3 built-in retry via botocore Config(retries={mode: standard}) replaces the hand-rolled loops; google-api-python-client offers request.execute(num_retries=); blocking SDK calls from async are offloaded via asyncio.to_thread.

TEST MIGRATION: touched vendor tests relocate into tests/unit/integrations/<vendor>; add per-vendor classification unit tests; legacy trees only shrink.

SIZE GATE - decompose before implementation into real subtasks (Google done: TASK-25.1 + TASK-25.1.1-.5; AWS done: TASK-25.2 + TASK-25.2.1-.4; AWSShield/MaxMind/Slack + final sweep still pending), one vendor per reviewable PR. This high-level plan is the umbrella; detailed per-subtask implementation planning (the --plan field on each TASK-25.1.x/TASK-25.2.x) happens when each is scheduled.

NOTE vs prior plan: the earlier plan listed "canonical dynamodb/identity_store hold the boto3 client directly ... move try/except+classify into infrastructure/storage/service.py and the access-sync adapter" and "extract classify_google_error ... the directory factory/google adapter owns classify" - those are now DONE in TASK-22.2/22.3/22.4 and are removed from this task's scope. A SECOND correction (2026-07-31, same day): the original "25.2 Google remainder... this is residual only" line understated the scope by an order of magnitude - see the Google decomposition above. A THIRD correction (2026-07-31, same day): the "AWS remainder" list similarly undercounted its scope (missing identity_store.py/dynamodb.py's separate consumers and the client.py dispatcher itself) - see the AWS decomposition above. TASK-23's AC#2 was also corrected (it had over-broadly implied both non-_next dispatchers would already be gone) to explicitly cross-reference TASK-25.1/TASK-25.2.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-29 21:12
---
Upstream dependency repointed from TASK-22 to TASK-22.5. Inherited from the TASK-22 sprint: (1) integrations/maxmind/client.py will contain BOTH a legacy tuple|str geolocate()/bool healthcheck() (used by api/v1/routes/geolocate.py and jobs/scheduled_tasks.py) AND a ported OperationResult client (used by packages/geolocate) — this task's classify contract + unification must reconcile the two and migrate the two legacy tuple consumers; (2) storage/access-sync/directory adapters will already be on the _next module functions returning OperationResult — this task moves the raise/classify boundary into those adapters and strips OperationResult out of the clients.
---

created: 2026-07-31 17:09
---
RESEQUENCED per decisions/sdk-typing.md (2026-07-31). Scope reduced: AWS DynamoDB + IdentityStore and Google Directory raise/classify conversion moved FORWARD into TASK-22.2/22.3/22.4 (consumers migrate once, directly to target), and the _next dispatcher deletion moved into TASK-23. What remains here: the AWS services NOT touched by 22.x (organizations/sso_admin/config/guardduty/cost_explorer/security_hub/lambdas/sqs) + AWSShield/executor deletion, residual Google surfaces, MaxMind unification (+ its two legacy tuple consumers), Slack, and the final grep sweep. Dependencies unchanged (TASK-22.5 + TASK-23); the get_aws_client/classify_aws_error primitive this task extends is the one established in TASK-22.2. DoD gains a decisions/sdk-typing.md reference.
---

created: 2026-07-31 17:51
---
CLARIFICATION (2026-07-31, same-day follow-up after TASK-70/TASK-22.4 were updated for the Google-stub revision). 25.2's "ensure one Google construction path (the factory from TASK-22.4)" now also means: whichever construction pattern TASK-22.4 lands for the Directory Resource (build() with cache_discovery=False/static_discovery=True + an explicit return-type annotation using the google-api-python-client-stubs-provided type, e.g. AdminDirectoryResource) should be reused, per-service, for the non-directory surfaces still in use here (gmail_v1, drive_v3, docs_v1, sheets_v4, etc. - annotate each build() call site with its own stub-provided Resource type, e.g. GmailResource, DriveResource). This was not previously possible to state explicitly (the original sdk-typing.md accepted the discovery Resource as permanently untyped); no AC change needed since AC#1 ("each vendor package exports exactly: factories, classify_<vendor>_error, settings") already covers this generically - flagging here so the per-vendor sub-decomposition (25.1-25.4 + sweep) inherits the stub-typing detail when TASK-25 is scheduled and broken down, rather than rediscovering it from scratch.
---

created: 2026-07-31 18:33
---
Google remainder decomposed into a real subtask TASK-25.1 (coordinator) + TASK-25.1.1-.5 (per-surface slices: Calendar+Meet, Docs, Sheets, legacy-Directory-consumers, Drive). It was NOT the small residual this task's plan originally sketched as "25.2" - repo-wide grep confirmed all 11 integrations/google_workspace/ files and 16 legacy production consumer files across 6 live surfaces still route through execute_google_api_call. See TASK-25.1's own description for the full grounding. AWS remainder/MaxMind/Slack are still prose-only in this task's plan, pending their own decomposition pass.
---

created: 2026-07-31 18:50
---
AWS remainder decomposed into a real subtask TASK-25.2 (coordinator) + TASK-25.2.1-.4 (account-health cluster, legacy DynamoDB, Lambda+sqs-deletion, Organizations/SSO-Admin/legacy-IdentityStore). Mirrors the Google finding exactly: the original AWS-remainder list undercounted scope by omitting identity_store.py/dynamodb.py's own separate consumer sets and the underlying integrations/aws/client.py dispatcher itself (never named in any task before now). TASK-23's AC#2 also corrected to stop over-promising full dispatcher removal before TASK-25.1/25.2 land. AWSShield retirement is intentionally kept separate/undecomposed for now (shield.py is a distinct, closer-to-target generation - needs its own consumer inventory before slicing).
---
<!-- COMMENTS:END -->
