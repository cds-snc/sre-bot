---
id: TASK-25
title: >-
  Apply the outbound-client contract: clients raise, adapters classify; retire
  the executor/shield tier
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-09-02 15:06'
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

PREREQUISITE: TASK-22.5 (facade tree deleted) + TASK-23 (_next generation deleted) Done for the MaxMind/Slack remainder below. The Google remainder (TASK-25.1) and AWS remainder (TASK-25.2) do NOT share this prerequisite - each depends only on the TASK-22.x primitive it reuses (TASK-22.4 for Google; TASK-22.2/22.3 for AWS), since neither touches the deprecated facade tree (TASK-22.5's scope) or the _next twins (TASK-23's scope). TASK-25.5 (AWSShield deletion) also does NOT share this prerequisite - see below, it is independent of everything.

REMAINING SCOPE - FULLY DECOMPOSED 2026-08-05 (all five remainder surfaces now have real backlog subtasks; nothing left as umbrella-only prose):
- Google remainder - TASK-25.1 (coordinator) + TASK-25.1.1 (Calendar+Meet, smallest, first + gmail deletion), TASK-25.1.2 (Docs), TASK-25.1.3 (Sheets), TASK-25.1.4 (legacy modules/ Directory consumers), TASK-25.1.5 (Drive, largest, last), each chained --dep on the prior sibling, the first depending on TASK-22.4 directly. (Decomposed 2026-07-31; see TASK-25.1's own plan for the full 16-file/6-surface inventory.)
- AWS remainder - TASK-25.2 (coordinator) + TASK-25.2.1 (Config/CostExplorer/GuardDuty/SecurityHub account-health cluster, first), TASK-25.2.2 (legacy non-_next DynamoDB, dep TASK-22.2), TASK-25.2.3 (Lambda + delete zero-consumer sqs.py), TASK-25.2.4 (Organizations+SSO-Admin+legacy non-_next IdentityStore, largest, last, dep TASK-22.3), each chained --dep on the prior sibling. integrations/aws/client.py itself is deleted as TASK-25.2.4's final step. (Decomposed 2026-07-31; see TASK-25.2's own plan for the full 14-file/9-service inventory.)
- MaxMind unification - TASK-25.3 (created 2026-08-05, dep TASK-22.5+TASK-23). Collapses the two coexisting shapes TASK-22.1 left in integrations/maxmind/client.py (legacy tuple geolocate()/healthcheck() + the OperationResult MaxMindClient) into one factory + classify_maxmind_error (AddressNotFoundError/ValueError/GeoIP2Error); migrates the two legacy tuple consumers api/v1/routes/geolocate.py (`maxmind.geolocate(ip)` -> tuple|str) and jobs/scheduled_tasks.py (`maxmind.healthcheck` -> bool) onto the classify boundary; deletes the tuple functions. Independent of Slack/AWSShield (no shared files).
- Slack - TASK-25.4 (created 2026-08-05, dep TASK-22.5+TASK-23). classify_slack_error(SlackApiError -> status/error_code/retry_after honoring Retry-After) added to integrations/slack; adapters acting on Slack as a target (usergroup writes etc.) wrap SlackClientManager.get_client() call sites in try/except+classify. Slack was never part of TASK-22's infrastructure/clients/ facade migration (it always lived in integrations/slack/), so this is net-new contract application, not a facade migration. bootstrap.py's existing slack_sdk built-in RetryHandlers are SDK-native already and are preserved, not touched. Independent of MaxMind/AWSShield (no shared files).
- AWSShield retirement - TASK-25.5 (created 2026-08-05). CORRECTED FINDING (2026-08-05, supersedes the "AWSShield feeds remaining AWS services" assumption in this task's original Description/comment #1): repo-wide grep confirms integrations/aws/shield.py::AWSShield has ZERO production consumers today - it is referenced only by its own dedicated test files (tests/unit/integrations/aws/test_shield.py, test_executor.py, tests/smoke/integrations/aws/test_shield_smoke.py). It was never actually wired into any real AWS service factory despite being "the closest-to-target AWS generation" per prior planning notes. TASK-25.2's per-service migrations (organizations/sso-admin/config/guardduty/cost-explorer/security-hub/lambdas/identitystore/dynamodb) all route through integrations/aws/client.py's execute_aws_api_call dispatcher, NOT through AWSShield - the two AWS generations never actually converged. This makes TASK-25.5 a pure deletion (shield.py + its 3 test files), not a consumer migration - genuinely independent of every other subtask here, safe to schedule anytime. Kept as a TASK-25 child (not a sibling of TASK-22) since it directly satisfies THIS task's own AC#4 ("AWSShield class deleted; grep -rn 'shield' app/integrations returns zero code hits").
- Final sweep (this umbrella task's own remaining direct work, after all 5 children above are Done): grep shows no time.sleep/tenacity/backoff retry loops in app/integrations/ (AC#5), no execute_*_api_call dispatcher, no get_google_api_command_parameters (AC covered transitively by TASK-25.1/25.2's own final steps); each vendor exports exactly factories + classify_<vendor>_error + settings (AC#1, now provable across all 5 vendors: aws, google_workspace, maxmind, slack, plus the already-shipped identitystore/dynamodb/directory primitives from TASK-22.x); no client returns OperationResult (AC#2, spot-check + import-linter TASK-18).

WHY THE OLD TIERS GO (unchanged): boto3 built-in retry via botocore Config(retries={mode: standard}) replaces the hand-rolled loops; google-api-python-client offers request.execute(num_retries=); slack_sdk ships its own RetryHandlers; blocking SDK calls from async are offloaded via asyncio.to_thread.

TEST MIGRATION: touched vendor tests relocate into tests/unit/integrations/<vendor>; add per-vendor classification unit tests; legacy trees only shrink.

SIZE GATE - fully decomposed 2026-08-05 (Google: TASK-25.1 + .1.1-.5; AWS: TASK-25.2 + .2.1-.4; MaxMind: TASK-25.3; Slack: TASK-25.4; AWSShield: TASK-25.5), one vendor/surface per reviewable PR, TASK-25.3/.4/.5 independent of each other and of the Google/AWS chains (no shared files - can run in parallel with 25.1.x/25.2.x, gated only by their own listed dependencies). This umbrella task's own remaining direct work after all children Done is the final grep sweep only. Detailed per-subtask implementation planning (the --plan field on each) happens when each is individually scheduled - TASK-25.3/.4/.5 do not yet have their own --plan written (only Description/AC), matching how TASK-25.1/.2's children were first created.

NOTE vs prior plan: the earlier plan listed "canonical dynamodb/identity_store hold the boto3 client directly ... move try/except+classify into infrastructure/storage/service.py and the access-sync adapter" and "extract classify_google_error ... the directory factory/google adapter owns classify" - those are now DONE in TASK-22.2/22.3/22.4 and are removed from this task's scope. A SECOND correction (2026-07-31, same day): the original "25.2 Google remainder... this is residual only" line understated the scope by an order of magnitude - see the Google decomposition above. A THIRD correction (2026-07-31, same day): the "AWS remainder" list similarly undercounted its scope (missing identity_store.py/dynamodb.py's separate consumers and the client.py dispatcher itself) - see the AWS decomposition above. TASK-23's AC#2 was also corrected (it had over-broadly implied both non-_next dispatchers would already be gone) to explicitly cross-reference TASK-25.1/TASK-25.2. A FOURTH correction (2026-08-05): MaxMind, Slack, and AWSShield retirement - previously left as umbrella-only prose bullets pending future decomposition - are now real subtasks (TASK-25.3/.4/.5); the AWSShield "feeds remaining AWS services" assumption was found to be stale/wrong (zero production consumers, confirmed by repo-wide grep) and corrected in TASK-25.5's own framing above.
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

created: 2026-08-05 16:15
---
DECOMPOSED 2026-08-05 (full-coverage pass, prompted by re-verifying TASK-22.3 downstream). Created the three remaining subtasks that were only umbrella-level prose before: TASK-25.3 (MaxMind unification + 2 legacy tuple consumers), TASK-25.4 (Slack classify_slack_error + factory), TASK-25.5 (AWSShield deletion). KEY CORRECTION found while grounding TASK-25.5: integrations/aws/shield.py::AWSShield has ZERO production consumers (repo-wide grep) - only its own dedicated test files reference it. This contradicts the 'AWSShield feeds remaining AWS services' framing in this task's original Description and comment #2 - the AWS remainder (TASK-25.2.x) actually routes entirely through integrations/aws/client.py's execute_aws_api_call dispatcher, never through AWSShield. TASK-25.5 is therefore a straight deletion (shield.py + 3 test files), not a consumer migration, and is independent of every other subtask (no shared files) - safe to schedule anytime, no dependency added. TASK-25.3/25.4 kept dependent on TASK-22.5+TASK-23 per this task's existing prerequisite framing. Full REMAINING SCOPE section rewritten via --plan to reference the real IDs instead of 'not yet decomposed' placeholders.
---

created: 2026-09-02 15:06
---
GOOGLE REMAINDER - ENDSTATE RESTATED AND TASK-25.1.6 DECOMPOSED (2026-09-02, human-directed, after assessing the shipped TASK-25.1.1/.2/.3/.4/.5 slices against decisions/outbound-clients.md and decisions/sdk-typing.md).

FINDING: those slices removed the execute_google_api_call dispatcher but kept the per-method wrapper module per Google surface. decisions/sdk-typing.md item 1 retires BOTH ("the generic dispatcher and the per-method wrapper module"), so this umbrella's AC#1 ("each vendor package exports exactly: factories, classify_<vendor>_error, settings") is currently NOT satisfiable for google_workspace, which still has six mirror modules plus google_service.py. AC#2 ("no client returns OperationResult") is also open for that vendor: client.py::execute_batch_request returns OperationResult from inside the vendor package. AC#5 ("no hand-rolled retry in app/integrations/") is open too: integrations/utils/api.py::retry_request is a time.sleep loop called from google_directory.py. This umbrella cannot close on the current state - which is the correct outcome; the gate worked.

NOT A PLANNING FAILURE IN SEQUENCING: 16 legacy app/modules/* consumers have no adapter tier, so inlining classification would have meant building six feature adapters inside a dispatcher-removal PR. The slices were correctly sized. What was missing is that nothing marked the mirror modules themselves as temporary. TASK-25.1's Description now carries an explicit ENDSTATE section saying integrations/google_workspace/ ends as client.py + settings and that the six modules are a strangler seam, not the destination.

ACTIONS TAKEN: TASK-25.1.6 retitled to "Retire the Google Workspace vendor mirror layer", raised to high priority, converted to a coordinator with no direct implementation, and decomposed into eleven children (characterization-test gate, pure-helper relocation, three Directory slices, the incident_draft adapter Docs half, four legacy-incident adapter slices, and a final helper-deletion + CI-guardrail slice). The last of those adds a machine check so app/integrations/<vendor>/ cannot regrow non-factory/non-classification modules - this convention proved too expensive to re-establish by memory.

DIRECTORY DECISION (human): infrastructure/directory's DirectoryProvider / GoogleDirectoryProvider survives; integrations/google_workspace/google_directory.py is deleted; the four legacy consumers migrate onto the Protocol. That also retires retry_request and satisfies AC#5 for the Google vendor.

APPLIES TO THE OTHER VENDORS TOO: TASK-25.2.x (AWS) is migrating the same way - off execute_aws_api_call and onto integrations/aws primitives - and risks landing the same per-method mirror layer under integrations/aws/. Read TASK-25.1's ENDSTATE section before planning any remaining TASK-25.2.x slice, and state per slice whether the vendor module survives or the call sites move into adapters. TASK-25.4 (Slack) is net-new contract application and should be written to the endstate directly rather than through an intermediate mirror.
---
<!-- COMMENTS:END -->
