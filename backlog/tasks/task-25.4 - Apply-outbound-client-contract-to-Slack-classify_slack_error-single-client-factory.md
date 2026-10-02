---
id: TASK-25.4
title: >-
  Apply outbound-client contract to Slack: classify_slack_error + single client
  factory
status: Done
assignee: []
created_date: '2026-08-05 16:13'
updated_date: '2026-10-02 14:56'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.5
  - TASK-23
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/slack/client.py
  - app/integrations/slack/bootstrap.py
parent_task_id: TASK-25
priority: high
ordinal: 123000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Apply decisions/outbound-clients.md and decisions/sdk-typing.md to the Slack Web API client. Description added and scope corrected 2026-09-18 (human decision): the original AC#2 kept SlackClientManager and wrapped its callers, which would entrench a client facade that sdk-typing.md forbids.

TODAY (verified 2026-09-18). The Slack Web client is built in four places, and sdk-typing.md item 4 requires one construction path per vendor:
- app/integrations/slack/client.py: SlackClientManager, a class-level singleton that exposes get_client() -> WebClient (bot token). Its only production caller is app/integrations/slack/users.py:203.
- app/integrations/slack/bootstrap.py:48: AsyncWebClient for the Bolt AsyncApp (bot token, with slack_sdk RetryHandlers).
- app/integrations/slack/bootstrap.py:77: sync WebClient (bot token).
- app/packages/oncall_sync/providers.py:41: WebClient(token=settings.USER_TOKEN), the admin-scoped user token from TASK-71.
There is no classify_slack_error.

TARGET.
- app/integrations/slack/client.py exports factory functions for the Web client, covering bot and user tokens and sync and async as actually needed, with SDK-native RetryHandlers configured once in the factory, plus classify_slack_error.
- SlackClientManager is deleted.
- Every construction site above builds through the factory.
- Adapters that act on Slack as a target call the WebClient directly inside try/except + classify_slack_error.
- Whether a client is shared or built per use is decided and recorded (slack_sdk WebClient is safe to share across threads; say so explicitly or choose otherwise).

BOUNDARY WITH TASK-26. TASK-26 moves the transport (Bolt runtime, parser, formatter, help, commands) out of integrations/slack into infrastructure/slack and shrinks the vendor package to factory + classifier + settings. This task owns the factory and classifier that TASK-26 then relies on. The bootstrap may keep building its Bolt App where it lives today, but it gets its Web client from the factory. The planner checks the single-PR size gate and splits the work if needed (e.g. factory + classifier first, then call-site migration).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 integrations/slack/client.py exports Web client factory functions (bot/user token, sync/async as needed) with SDK-native RetryHandlers set once at construction, and classify_slack_error(exc) -> (OperationStatus, error_code, retry_after) for SlackApiError that honours Retry-After; no OperationResult in integrations/slack/client.py
- [x] #2 SlackClientManager is deleted, and no production code outside integrations/slack/client.py calls WebClient(...) or AsyncWebClient(...) directly: bootstrap.py, users.py and packages/oncall_sync build through the factory
- [x] #3 classify_slack_error has unit tests: each mapped SlackApiError family -> expected status/error_code/retry_after (Retry-After honoured); one unmapped exception propagates. Factory tests assert token selection and RetryHandler wiring
- [x] #4 No hand-rolled retry loop competes with slack_sdk's RetryHandlers (grep), and the client sharing/thread-safety choice is recorded
- [x] #5 decisions/sdk-typing.md no longer lists SlackClientManager or multiple Slack construction paths as a tolerated divergence
- [x] #6 Every feature adapter that acts on Slack as a target (e.g. oncall_sync usergroup writes) calls the Web client directly inside try/except SlackApiError and calls classify_slack_error; the adapter surfaces the classified status/error_code through its Protocol's existing error contract (OperationResult where the Protocol already returns it; the feature's own domain exception carrying the classified error_code where the Protocol is Path B-shaped by its system, e.g. oncall_sync's OnCallSyncError) per outbound-clients.md's allowance that a Path B adapter's shape follows its system
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Scope confirmed against current code (2026-09-28). Real construction sites (grep-verified, no others found):
1. app/integrations/slack/client.py:6-17 — SlackClientManager (bot token, sync, no retry handlers). Sole caller: app/integrations/slack/users.py:203.
2. app/integrations/slack/bootstrap.py:48 — AsyncWebClient in SlackBootstrap.__init__ (bot token, async, 3 AsyncRetryHandlers already configured).
3. app/integrations/slack/bootstrap.py:77 — WebClient in LegacySlackBootstrap.__init__ (bot token, sync, 3 RetryHandlers already configured).
4. app/packages/oncall_sync/providers.py:41 — WebClient(token=settings.USER_TOKEN) (user token, sync, no retry handlers), passed into SlackUserGroupTarget.
No other WebClient/AsyncWebClient construction exists; packages/rant, packages/user_rotations, packages/incident_draft, packages/incident_summary, oncall_sync/adapters/slack.py all receive a client as a parameter, they don't construct one.

Precedent to copy (uniformity, per outbound-clients.md/sdk-typing.md): app/integrations/aws/client.py's get_aws_client() + classify_aws_error(exc) -> tuple[OperationStatus, str | None, int | None], reading code catalogues off a settings object; app/integrations/maxmind/client.py and app/integrations/google_workspace/client.py's classify_<vendor>_error follow the same tuple shape. Slack's classify_slack_error must match this signature exactly.

Steps:

1. app/integrations/slack/settings.py — add classification catalogues mirroring AWSSettings: UNAUTHORIZED_ERRORS, NOT_FOUND_ERRORS, TRANSIENT_ERRORS (lists of slack_sdk short error codes, e.g. "not_authed"/"invalid_auth"/"token_revoked"/"missing_scope" for UNAUTHORIZED; "channel_not_found"/"user_not_found"/"usergroup_not_found" for NOT_FOUND; "ratelimited"/"internal_error"/"service_unavailable"/"fatal_error" for TRANSIENT) and TRANSIENT_RETRY_AFTER_SECONDS default (e.g. 30), all env-overridable Fields, same pattern as integrations/aws/settings.py.

2. app/integrations/slack/client.py — replace SlackClientManager with:
   - get_slack_web_client(*, actor: Literal["bot", "user"] = "bot") -> WebClient: builds sync RetryHandlers list (Connection/RateLimit/ServerError, max_retry_count=settings.RETRY_MAX_ATTEMPTS) once, selects BOT_TOKEN or USER_TOKEN, sets timeout=settings.REQUEST_TIMEOUT_SECONDS. Built per call, not cached (matches get_aws_client; callers that want sharing cache at their own call site, as packages/oncall_sync/providers.py already does with @lru_cache).
   - get_async_slack_web_client() -> AsyncWebClient: same shape with AsyncRetryHandlers, bot token only (no current async-user-token consumer).
   - classify_slack_error(exc: Exception) -> tuple[OperationStatus, str | None, int | None]: only classifies SlackApiError; anything else re-raised. Reads exc.response.get("error") as the code. Maps code against settings.UNAUTHORIZED_ERRORS -> UNAUTHORIZED, settings.NOT_FOUND_ERRORS -> NOT_FOUND, settings.TRANSIENT_ERRORS -> TRANSIENT_ERROR with retry_after honouring the Retry-After header (exc.response.headers.get("Retry-After") when present, else settings.TRANSIENT_RETRY_AFTER_SECONDS) — AC#1 requires Retry-After to be honoured specifically for rate limiting. Unmapped codes re-raise exc. Import OperationStatus from contracts.operations.status (same import AWS and Google use today). client.py imports only slack_sdk, structlog, integrations.slack.settings and contracts.operations.status, so it passes import-linter contract (d) without new ignore_imports entries. No OperationResult import in this module (AC#1).
   - Module docstring records the sharing/thread-safety decision (AC#4): slack_sdk clients are built per call and never cached inside the factory; a caller that wants one shared instance wraps the factory call in its own cached provider, exactly as packages/oncall_sync/providers.py already does.

3. app/integrations/slack/bootstrap.py — SlackBootstrap.__init__ calls self.web = get_async_slack_web_client() instead of constructing AsyncWebClient directly (drop the inline retry_handlers list, now built inside the factory). LegacySlackBootstrap.__init__ calls self.web = get_slack_web_client() instead of constructing WebClient directly. create_app() methods on both classes are unchanged — TASK-26 still owns moving the Bolt App construction itself. These two sites already had retry handlers before this change, so behaviour is unchanged here.

4. app/integrations/slack/users.py:203 — replace SlackClientManager.get_client() with get_slack_web_client(). No other change to this function; its existing broad except Exception around users_lookupByEmail is a pre-existing rough edge in a formatter/lookup helper, not an adapter acting on Slack as a target (AC#6 scope) — left alone here to keep this PR a mechanical factory-migration, not a mixed mechanical+behavior change. INTENDED BEHAVIOUR CHANGE: this call site currently has zero retry handlers (SlackClientManager built a bare WebClient); after this change it gains the factory's Connection/RateLimit/ServerError RetryHandlers. This is safe because users_lookupByEmail is a read-only, idempotent GET-style call — retrying it changes nothing but latency on transient failures, and the function already tolerates and logs a final failure via its except Exception.

5. app/packages/oncall_sync/providers.py:41 — replace WebClient(token=settings.USER_TOKEN) with get_slack_web_client(actor="user"). Keep the existing "if not settings.USER_TOKEN: raise ValueError(...)" guard and the @lru_cache(maxsize=1) wrapping at get_user_group_sync_target. This is the current construction site; TASK-124.2 later relocates it structurally into adapters/, it does not defer the factory adoption. INTENDED BEHAVIOUR CHANGE: this call site currently has zero retry handlers; after this change it gains the factory's RetryHandlers. Safe because every Slack call made through this client (usergroups_users_update, usergroups_create, usergroups_enable, usergroups_list, users_lookupByEmail — see adapters/slack.py) is either a read or an idempotent "set membership to exactly these users"/"ensure this usergroup exists" write: replaying usergroups_users_update after a transient failure re-sends the same full membership list, which converges to the same end state rather than duplicating anything.

6. app/packages/oncall_sync/adapters/slack.py — in sync_user_group_ids (line 65) and _resolve_user_id (line 78), keep the except SlackApiError as exc blocks but call classify_slack_error(exc) first and fold the classified error_code (and status where useful for logging) into the existing OnCallSyncError message / log fields, instead of only exc.response.get("error"). Protocol return types (OnCallSyncError-raising, not OperationResult) are unchanged per the corrected AC#6 — see task comment.

7. Delete SlackClientManager's test app/tests/integrations/slack/test_slack_client.py (tests a class that no longer exists; nothing to edit in place).

8. app/tests/unit/integrations/slack/test_slack_client.py (new) — factory tests: actor="bot" uses BOT_TOKEN, actor="user" uses USER_TOKEN and raises/validates as expected; sync and async retry handlers carry the configured max_retry_count; building a client opens no outbound connection (construction only, no assertion requires a live socket spy since WebClient.__init__ does no I/O — confirm during implementation, matching outbound-clients.md's Checks intent). classify_slack_error tests: one parametrized case per mapped family (unauthorized, not-found, transient with default retry_after, transient with Retry-After header honoured) plus one unmapped SlackApiError code and one non-SlackApiError exception (e.g. KeyError) that both propagate unchanged. Mocking technique: construct real SlackApiError(message, response=MagicMock(...)) objects, matching the existing convention in app/tests/unit/packages/oncall_sync/test_oncall_sync_slack_adapter.py (Slack tests mock at the response-object level, not via botocore-Stubber-style transport interception — slack_sdk has no equivalent test double, so this is the correct project-consistent choice, distinct from the AWS Stubber convention which is boto3-specific).

9. app/tests/unit/integrations/slack/test_slack_bootstrap.py (existing) — update assertions to check SlackBootstrap/LegacySlackBootstrap obtain .web via get_async_slack_web_client/get_slack_web_client (mock those factory functions) rather than asserting a raw AsyncWebClient/WebClient construction with an inline retry_handlers list.

10. app/tests/unit/packages/oncall_sync/test_oncall_sync_slack_adapter.py (existing) — extend coverage: sync_user_group_ids wraps a SlackApiError into OnCallSyncError whose message includes the classified error_code; an unmapped/non-Slack exception still propagates unchanged through the adapter. Verify and update app/packages/oncall_sync/providers.py's own test (if one asserts direct WebClient(...) construction) to mock get_slack_web_client instead, AND add an assertion there that the client returned by get_user_group_sync_target carries the factory's RetryHandlers (new behaviour at this call site — see step 5).

11. app/tests/unit/integrations/slack/test_slack_client.py or test_slack_users.py (whichever covers users.py) — add an assertion that the client used by replace_users_emails_with_mention now carries the factory's RetryHandlers (new behaviour at this call site — see step 4), e.g. by mocking get_slack_web_client and asserting it is called (not SlackClientManager), or by inspecting the retry_handlers attribute on the client the function acquires.

12. decisions/outbound-clients.md — remove the "Slack has no classify_slack_error and builds its Web client at four sites..." bullet from Migration; add a dated Changes entry.

13. decisions/sdk-typing.md — remove the "the SlackClientManager singleton, and four separate Slack Web-client construction sites instead of one factory" bullet from Migration; add a dated Changes entry. This closes AC#5. Both decision records are edited in this PR (outbound-clients.md's divergence list and sdk-typing.md's divergence list both name Slack and both must be closed together, even though only AC#5 names sdk-typing.md explicitly).

AC traceability (current numbering: #1 factory+classifier, #2 SlackClientManager deleted/no direct construction, #3 classifier/factory tests, #4 no competing retry loop + sharing choice recorded, #5 sdk-typing.md divergence removed, #6 adapter classification):
- AC#1 -> steps 1-2, tests in step 8.
- AC#2 -> steps 2-5, tests in steps 8-11 (grep-verify no remaining WebClient(/AsyncWebClient( outside client.py after the change).
- AC#3 -> step 8 (classifier + factory tests).
- AC#4 -> step 2 docstring (sharing decision) + grep confirms zero hand-rolled retry loops already exist in integrations/slack or packages/oncall_sync (verified during planning: no time.sleep/tenacity/backoff hits).
- AC#5 -> step 13 (sdk-typing.md); step 12 (outbound-clients.md) closes the same divergence recorded in the companion decision record and ships in the same PR even though AC#5 names only sdk-typing.md.
- AC#6 (corrected wording, see task comment) -> step 6, tests in step 10.

Size gate: production files touched = client.py, settings.py, bootstrap.py, users.py, providers.py, adapters/slack.py (6 files, one subsystem: outbound Slack client layer); estimated production diff ~150-250 LOC (client.py rewrite ~90-110 new lines replacing 17; small edits elsewhere). Test diff is separate and excluded from the gate. This is a single mechanical migration to one factory (with two identified, narrow, and justified retry-behaviour additions at previously-unretried call sites — not a broader behavior change), well under the ~400 LOC/~10 file/two-subsystem thresholds, and doc-2 designates TASK-25.4 as a required single PR (not a stack) — no decomposition into subtasks needed.

Blast radius / rollback: sites 2 and 3 (bootstrap.py) keep identical retry semantics — they already had RetryHandlers, only their construction path changes. Sites 1 (users.py, via SlackClientManager) and 4 (oncall_sync providers.py) are an intended, narrow behaviour change: both currently have zero retry handlers and gain the factory's Connection/RateLimit/ServerError RetryHandlers. This is safe because every call made through those two clients is either a read (users_lookupByEmail) or an idempotent "converge to this exact membership/state" write (usergroups_users_update, usergroups_create, usergroups_enable, usergroups_list) — see steps 4 and 5 for the per-site justification. A single git revert restores the four original construction sites and SlackClientManager, including the pre-change retry behaviour at all four sites. No deploy-ordering constraint: this PR changes no configuration keys and does not touch the Bolt runtime/transport.

Assumptions to verify during implementation:
- WebClient(...)/AsyncWebClient(...) construction performs no network I/O (matches slack_sdk's documented lazy-connection model) — verify empirically before writing a "no outbound connection" factory test in the AWS-Checks style; if slack_sdk does no eager I/O the test may just assert on the returned object's configured attributes instead of a socket spy.
- The exact set of slack_sdk short error codes to bucket under UNAUTHORIZED/NOT_FOUND/TRANSIENT is not authoritative from any decision record; verify against slack_sdk's documented error strings (https://api.slack.com/methods) during implementation and treat the settings catalogues as the single place to correct them later, same as AWS's settings-driven catalogues. (Accepted by reviewer as an implementation-time detail.)
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
integrations/slack/client.py now holds get_slack_web_client(*, actor="bot"|"user"), get_async_slack_web_client() and classify_slack_error(exc) -> tuple[OperationStatus, str | None, int | None] (same shape as the AWS/Google/MaxMind classifiers; no OperationResult). SlackClientManager is deleted. Factories attach slack_sdk's connection/rate-limit/server-error RetryHandlers once, with the per-call timeout, and build per call; the module docstring records the sharing choice (callers cache at their own provider). settings.py gained UNAUTHORIZED_ERRORS / NOT_FOUND_ERRORS / TRANSIENT_ERRORS catalogues (checked against Slack's documented error codes) and TRANSIENT_RETRY_AFTER_SECONDS (30). classify_slack_error honours Retry-After, matched case-insensitively like slack_sdk; an unparseable header falls back to the default.

Call sites: SlackBootstrap / LegacySlackBootstrap and integrations/slack/users.py build through the factory. Intended behaviour change: users.py (users_lookupByEmail, a read) and the oncall_sync user-token client (idempotent usergroup writes) gain the SDK retry handlers they lacked. Grep: WebClient(/AsyncWebClient( appear only in integrations/slack/client.py; there are no hand-rolled retry loops in integrations/slack or packages/oncall_sync.

Deviations from plan:
- The factory argument is `actor`, not `token_kind`: ruff S105-S107 flag any "token" name as a hardcoded password, and CLAUDE.md forbids suppressions.
- Import-linter contract (e) forbids packages.oncall_sync.providers -> integrations, and ignore lists are shrink-only. The USER_TOKEN guard and the factory call moved into packages/oncall_sync/adapters/slack.py::build_user_group_sync_target, and providers.py imports only the adapter. This also removed the existing ignore entry "packages.oncall_sync.providers -> integrations.slack.settings". TASK-124.2's description is updated accordingly.
- oncall_sync adapter: SlackApiError codes the catalogues don't name are still wrapped in OnCallSyncError, not re-raised. The service catches only OnCallSyncError, so letting them escape would abort sync_all for every remaining schedule. The message now carries the classified status ("missing_scope (unauthorized)"), and the lookup-failure log carries status. Non-Slack exceptions still propagate.
- Bootstrap tests were left unchanged: they already assert token, timeout and retry handlers on the built client, and now exercise the factory end to end.

Also fixed in touched files: removed deprecated `from __future__ import annotations` (slack settings.py, oncall_sync providers.py and adapters/slack.py, and the providers test), and the two mypy no-any-return errors in integrations/slack/users.py. Deleted the legacy tests/integrations/slack/test_slack_client.py (it tested SlackClientManager); tests/integrations/slack/test_users.py was edited in place to patch get_slack_web_client. decisions/sdk-typing.md and decisions/outbound-clients.md close the Slack divergence (Changes entries 2026-09-29).

Gates: ruff check clean; lint-imports 8 kept, 0 broken (contract (e) ignore list down by one); mypy 67 errors repo-wide (was 69), 0 in touched files; pytest tests --ignore=tests/smoke 3524 passed, 6 failed (known TASK-90 order leaks); make test 2772 + 758 passed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-18 16:47
---
2026-09-18 (human decision): scope corrected to match decisions/sdk-typing.md. The original AC#2 wrapped SlackClientManager.get_client() call sites, which would have kept a standing client facade. Now: delete SlackClientManager and bring all four Web-client construction sites (client.py, bootstrap.py x2, packages/oncall_sync/providers.py) onto one factory. sdk-typing.md lists this as a tolerated divergence owned by this task.
---

created: 2026-09-24 20:10
---
2026-09-24: the boundary with TASK-26 is unchanged in substance, but TASK-26 now moves the transport to app/server/slack/ (not app/infrastructure/slack/) in two slices (TASK-26.1 handler contract, TASK-26.2 runtime move), both depending on this task's factory and classifier. packages/oncall_sync's WebClient construction moves into its adapters/ in TASK-124.2.
---

created: 2026-09-28 14:21
---
2026-09-28 (planning correction): original AC#3 required the adapter to "return OperationResult," but packages/oncall_sync's UserGroupSyncTarget Protocol and service.py are built entirely around raising OnCallSyncError, not OperationResult (verified: ports.py, service.py call sites at lines ~57-149). Forcing OperationResult here would mean redesigning oncall_sync's whole error-handling Protocol, which is a separate, larger change outside a client-factory task and not requested by any other backlog task. outbound-clients.md explicitly allows a Path B adapter's Protocol to be "shaped by that system." AC#3 removed and re-added (now last in the list) with corrected wording: the adapter must still call classify_slack_error and surface its result, but through oncall_sync's existing OnCallSyncError contract rather than a literal OperationResult return. No other task depends on oncall_sync's error Protocol changing shape, so this narrows scope without blocking TASK-26.1 or any dependent.
---

created: 2026-09-28 14:55
---
2026-09-28: implementation plan approved by human (Guillaume Charest) for the doc-2 Stack A / Wave 0 realignment.
---
<!-- COMMENTS:END -->
