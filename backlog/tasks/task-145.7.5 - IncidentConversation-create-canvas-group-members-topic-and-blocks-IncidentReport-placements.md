---
id: TASK-145.7.5
title: >-
  IncidentConversation create, canvas, group members, topic and blocks;
  IncidentReport placements
status: In Progress
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-10T20:34:00Z'
labels:
  - incident
  - features
dependencies: []
references:
  - decisions/incident-management.md
  - decisions/outbound-clients.md
parent_task_id: TASK-145.7
priority: medium
type: feature
ordinal: 502000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L4a (approved program in TASK-145.7's plan, section 2; outline in the parent plan). IncidentConversation gains create(name) (the TASK-145.6.3 ruling: create arrives with the first binding), create_canvas, group_members, set_topic and post with blocks (Slack adapter, fake, parity suite). IncidentReport gains list_placements() and create_from_template(title, placement=None) (Google adapter over list_child_folders, fake). Inert: no caller until L7b and L9a.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each new IncidentConversation method has Slack adapter, fake and parity tests, with not-writable and name_taken errors classified (outbound-clients.md)
- [x] #2 list_placements and create_from_template(title, placement) have Google adapter and fake tests; placement None keeps today's folder
- [x] #3 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
APPROVED 2026-11-10 (human): this plan, OQ1 revised (suffix -2..-5), OQ1b rules I1-I5, OQ2, OQ3.
Full plan 2026-11-10, revised the same day after the program-scope assessment of OQ1-OQ3 (comment on this task) (L4a, side PR task-145.7.5-conversation-report-additions from main e9bcdcbc). Inert: no production caller until L7b (recreate) and L9a (declare). Grounded in a read-only survey of main; line numbers are main e9bcdcbc.

## 0. Current state
- IncidentConversation (features/incident/core/api.py:158-200, async, per reference): post(conversation, text) :173, set_purpose :177, add_bookmark :181, invite :185, archive :193, is_writable :197. Docstring :159-170 says create is not part of the interface yet. conversation_is_writable helper :358-368.
- SlackIncidentConversation (core/adapters/slack.py:284-373): reads = async bot client (conversations.info), writes = rate-limit-only write handle (integrations/slack/client.py:73-80). Every method checks system first (_conversation_unsupported :380); errors go through _conversation_failure :387 -> classify_slack_error (integrations/slack/client.py:83-107; unknown codes propagate); not_writable_errors map to ErrorCode.CONVERSATION_NOT_WRITABLE; idempotent done codes _INVITE_DONE / _ARCHIVE_DONE :279-281. No tenant in the ctor today; built by build_incident_conversation :375.
- InMemoryIncidentConversation (core/adapters/in_memory.py:377-512); parity suite tests/unit/features/incident/core/test_incident_core_conversation_protocol_parity.py with StubSlack in that directory's conftest.py:17-90 (no conversations_create stub).
- IncidentReport (api.py:202-251, sync): create_from_template(title) :213. GoogleDocsIncidentReport.create_from_template google_docs.py:631-660 copies the template into incident_core.folder_id. Module helpers _drive_call/_list_all :220-242 (classified OperationResult) and list_child_folders :276-281 (returns [] on failure, drops names containing "Templates"; the legacy picker's seam, test_seams_legacy.txt:18, # TASK-145.13; left untouched). Fake InMemoryIncidentReport in_memory.py:254-306.
- Legacy behaviour mirrored (modules/incident, frozen): conversations.create with an unbounded "-i" suffix loop on name_taken (incident_conversation.py:42-65); conversations.setTopic core.py:437; conversations.canvases.create with markdown core.py:468; usergroups.users.list core.py:566/578 (bot token); chat.postMessage with blocks core.py:483; folder picker incident_folder.py:36-39 (sorted, capped at 25 for the modal).
- No ErrorCode for a taken name (contracts/operations/codes.py). tests/unit/features/incident/core/test_incident_core_api_surface.py:116-122 asserts IncidentConversation has no create.

## 1. Design
a. create(name: str, *, private: bool) -> OperationResult[ConversationReference]: one conversations.create on the write handle (non-idempotent write, outbound-clients.md:26); is_private is sent only when true, so the call shape stays {"name": ...} as the declare pin asserts (legacy_surface/test_incident_declare_surface.py:254). name_taken is an expected outcome, not a failure: PERMANENT_ERROR with the new ErrorCode.CONVERSATION_NAME_TAKEN, logged once at info (incident_conversation_name_taken), never a warning. The adapter never loops and never decides convergence: two incidents declared the same day under the same title share a name and the bot belongs to both channels, so only the store (bindings) can tell a replay from a second incident. The reference's tenant comes from the Slack tenant setting, passed to the ctor by build_incident_conversation.
a2. find_own(name: str) -> OperationResult[ConversationReference | None]: the bot's own non-archived conversation with exactly that name (users.conversations on the reads client, types public_channel,private_channel, exclude_archived, paged by cursor), or None. This is the lookup Slack prescribes after a create that may have partly succeeded (internal_error, fatal_error: "check for an existing channel before creating a new one", conversations.create docs).
a3. core/conversation_names.py (pure, new): incident_conversation_names(title, opened_on: date, environment) -> Iterator[str], the pinned legacy format kept: "incident-" (production) or "incident-dev-" + YYYY-MM-DD + "-" + slug, cut to Slack's 80 characters; then the base cut to fit "-2", "-3", ... "-5" (CONVERSATION_NAME_ATTEMPTS = 5 names in all; the bare name counts as the first). Legacy starts at "-1" and loops without a bound (incident_conversation.py:42); "-2" reads as "the second one" and five bound the Slack calls in a pathological case (OneUptime #4847 does exactly this; FireHydrant appends a hash instead, unreadable). The slug lowercases and turns spaces into "-" as today and also replaces any other character outside [a-z0-9_-] with "-" (collapsed), which legacy sends to Slack and fails on with invalid_name_specials; names the pin uses are unchanged.
a4. One channel per incident (human, 2026-11-10). The loop is declare's and recreate's (scope for TASK-145.7.9 and TASK-145.8.6); its rules go into incident-management.md in this PR:
  I1 An incident whose record names a conversation never calls create; attach_conversation already refuses a second primary (store.py:178-190, 369-378).
  I2 Before create, the candidate name is claimed for this incident through the IdempotencyStore (reliability.md:18), key incident:conversation_name:<tenant>:<name>, outcome {incident_id, conversation_id}; a name claimed by another incident is skipped.
  I3 After any create result other than success (name_taken, a transient error, an unclassified exception or timeout), find_own(name) runs before anything else. The bot's own channel of that name is this incident's when it is bound to this incident, or unbound while this incident holds the name's claim: it is bound and reused, never recreated.
  I4 Retrying the same name is always safe (Slack refuses a duplicate name). The next suffix is tried only when the existing channel is proven not this incident's: not the bot's own, bound to another incident, or claimed by another incident.
  I5 An unknown outcome with nothing found reports the error (one warning, the pinned invoker message) and does not move to the next suffix; recreate retries the same name later.
L4a delivers what the loop needs from the adapter: create (quiet name_taken), find_own (public and private, paged), and the names function.
b. set_topic(conversation, text) -> OperationResult[None]: conversations.setTopic on the write handle (naturally idempotent, same pattern as set_purpose).
c. create_canvas(conversation, markdown: str) -> OperationResult[None]: conversations.canvases.create with document_content {type: markdown}; channel_canvas_already_exists is done (success), like _INVITE_DONE, so recreate can call it again.
d. group_members(conversation, group_id: str) -> OperationResult[tuple[str, ...]]: usergroups.users.list on the reads client; returns chat account ids in the conversation's tenant (people-and-accounts.md), ready for invite. The conversation argument carries system and tenant, keeping the per-reference rule of the Protocol. no_such_subteam -> NOT_FOUND through the existing table.
e. post(conversation, text, *, blocks: Sequence[Mapping[str, object]] = ()) -> unchanged result; blocks sent only when non-empty, text stays as the notification fallback.
f. IncidentReport.list_placements() -> OperationResult[tuple[ReportPlacement, ...]]: the child folders of incident_core.folder_id through _list_all (classified, not the swallowing list_child_folders), "Templates" names dropped as today, sorted by label. No 25 cap in the adapter: the modal limit belongs to the L9a view. Empty folder_id -> the existing not-configured result.
g. create_from_template(title, placement: ReportPlacement | None = None): None keeps incident_core.folder_id; a placement copies into placement.vendor_id; a placement of another system -> UNSUPPORTED_OPERATION.
h. Domain: ReportPlacement(ResourceReference) in core/domain.py with a required kw-only label (non-blank). It is a value object of report configuration (the 2026-11-04 option C ruling: a labelled report-folder choice, never a product), not persisted on the record.
i. Unknown Slack codes keep propagating (outbound-clients.md:31); e.g. a canvas disabled for the workspace raises, and L9a decides how a raised resource step is contained.

## 2. Steps (TDD: failing tests first per step)
1. contracts/operations/codes.py: CONVERSATION_NAME_TAKEN.
1b. core/conversation_names.py: incident_conversation_names and CONVERSATION_NAME_ATTEMPTS.
2. core/domain.py: ReportPlacement.
3. core/api.py: the five new IncidentConversation methods (create, find_own, set_topic, create_canvas, group_members) and the post blocks kwarg with docstrings; class docstring updated (create converges by name); IncidentReport list_placements and the placement parameter.
4. core/adapters/slack.py: ctor gains tenant; create (name_taken at info), find_own (users.conversations pager), set_topic, create_canvas, group_members, post blocks; build_incident_conversation passes the Slack tenant id.
5. core/adapters/in_memory.py: fake conversation gains created (name -> reference; any existing own or foreign_names ctor name -> CONVERSATION_NAME_TAKEN; private flag), find_own over its own names, topic_of, canvases_of, groups ctor arg, posts record blocks; fake report gains placements ctor arg, list_placements, and filed_in records the chosen folder.
6. core/adapters/google_docs.py: list_placements and placement-aware create_from_template.
7. decisions/incident-management.md: one 2026-11-10 Changes line (conversation names: the legacy format kept, Slack-safe slug, suffixes -2 to -5; create reports a taken name as CONVERSATION_NAME_TAKEN at info; find_own; reuse of an own conversation only when no binding names it, decided by declare and recreate; placements are the report folder's labelled child folders; canvas and topic writes; group_members). Plan text rides with this PR.
8. Tests (step 0 of each step above), then gates.

## 3. Tests (tests/unit/features/incident/core/, strict zone; Slack stubbed at the AsyncWebClient edge in conftest.py, Drive through the existing report parity fixture)
- test_incident_core_conversation_protocol_parity.py (extended, slack and in_memory): set_topic, create_canvas, group_members, post with blocks succeed; each new write on an archived / non-member channel -> CONVERSATION_NOT_WRITABLE; canvas already exists -> success; unknown group -> NOT_FOUND; non-Slack reference -> UNSUPPORTED_OPERATION; create returns a reference in the tenant.
- test_incident_core_conversation_create.py (new): create on the write handle, never the reads client, called with {"name"} only when public and is_private=True when private; name_taken -> CONVERSATION_NAME_TAKEN with no warning event (structlog capture) and no extra Slack call; restricted_action -> CONVERSATION_NOT_WRITABLE; ratelimited -> TRANSIENT_ERROR with retry_after; find_own: match on the second users.conversations page, no match -> None, non-Slack tenant unsupported.
- test_incident_core_conversation_names.py (new): production and dev prefixes; the pinned case (date slug of a plain title) equals the declare pin's expected name; 59- and 100-character titles cut to 80 with every suffixed candidate within 80 and ending -2..-5; punctuation and accents become single dashes; exactly CONVERSATION_NAME_ATTEMPTS (5) candidates, the bare name first; a title of punctuation only still yields a valid base.
- test_incident_core_api_surface.py: the no-create assertion replaced: create is async and keyword-only private; every other method still takes the reference first.
- test_incident_core_report_protocol_parity.py (extended, google and fake): list_placements returns labelled placements sorted, Templates dropped; create_from_template(title) files in the configured folder; create_from_template(title, placement) files in the placement.
- test_incident_core_report_placements.py (new): Drive error -> classified result (not an empty list); empty folder_id -> not configured; placement of another system -> UNSUPPORTED_OPERATION; ReportPlacement rejects a blank label.
- Seams: no new baseline entries (the report parity fixture already passes make check-test-seams on main).

## 4. AC traceability
#1 steps 1, 1b, 3-5; parity suite + test_incident_core_conversation_create.py + test_incident_core_conversation_names.py (not-writable and name_taken classified; name_taken handled quietly). #2 steps 2, 3, 5, 6; report parity + test_incident_core_report_placements.py (placement None keeps today's folder). #3 gates: ruff, lint-imports, make check-package-shape, make check-test-seams and targeted tests during work; full mypy then full pytest once each at the end.

## 5. Size gate
Production: codes.py +1, conversation_names.py ~40 (new), domain.py ~15, api.py ~60, slack.py ~125, in_memory.py ~90, google_docs.py ~35: ~365 LOC / 7 files, plus one ADR line. One subsystem (incident core) and one enum line in contracts. Additive only; no refactor mixed in. Within the gate.

## 6. Domain-model gate
ReportPlacement: cardinality 0..n per configured report folder, read live from Drive, never stored (the record keeps only the ReportReference). Scenarios: no placements (empty tuple, declare uses the default folder), one, many, a renamed folder (label read live), a deleted folder between list and create (copy fails, classified NOT_FOUND). Future: TASK-165.1 keys placement configuration by product id; ReportPlacement stays the report adapter's choice and a product mapping is additive. ConversationReference unchanged; no record or binding shape change, so no compatibility cascade.

## 7. Assumptions (verify during implementation)
1. The bot token has channels:manage/groups:write, canvases:write, usergroups:read, channels:read/groups:read: the legacy path makes each call with the same bot token today (core.py:437-578).
2. users.conversations lists private channels the bot belongs to (Slack docs; checked in the stubbed test only; production evidence comes at L9a).
3. Slack's error for an existing channel canvas is channel_canvas_already_exists (verify against the Slack method docs before coding the done set).
4. get_slack_settings() exposes the tenant entry's tenant_id (integrations/slack/settings.py:70); check the attribute path.

## 8. Blast radius and rollback
No caller: production behaviour unchanged. build_incident_conversation now reads the Slack tenant setting, already required at boot (settings.py:65). One git revert removes everything; no config, terraform, IAM or SSM change, so no deploy-checks run.

## 9. Decisions (assessment comment 2026-11-10)
OQ1 revised: no convergence in the adapter; create reports a taken name quietly, find_own supports the store-checked reuse in declare and recreate; legacy name format kept with a Slack-safe slug and suffixes -2 to -5 (practice check in the second assessment comment). Approved by the human 2026-11-10 (suffix -2..-5 included).
OQ1b one channel per incident: rules I1-I5 in 1.a4 (human requirement 2026-11-10); approved 2026-11-10.
OQ2 accepted by the human (2026-11-10) with the condition that a taken name is handled, not logged as an error: CONVERSATION_NAME_TAKEN at info.
OQ3 accepted by the human (2026-11-10): group_members(conversation, group_id).

Comments:
--------------------------------------------------
#1 - 2026-11-10 19:59 (UTC)
2026-11-10 program-scope assessment of the plan's OQ1-OQ3 (ADRs, doc-11, doc-15, prior and upcoming tasks, web practice).

OQ1 channel name and name_taken. ADR: GAP. No decision names the channel format or collision handling; incident-management.md:173 says only "create is added by TASK-145.7 with the first binding, converging on retry"; outbound-clients.md:26 requires a non-idempotent write to name its idempotency mechanism. doc-11 row 18 and doc-15: nothing on names. Prior: TASK-145.6.3 deferred create (name_taken re-raises today); TASK-145.7 OQ6 recorded "name_taken converges a retry"; TASK-36.1.1 pinned the format (incident-/incident-dev- + date slug, cut to 80; legacy_surface/test_incident_declare_surface.py:109-116, :254). Legacy: modules/incident/incident_conversation.py:23-71 tries -1, -2, ... with no bound and sends unsanitized titles (invalid_name_specials on punctuation). Upcoming: TASK-145.7.9 (declare) and TASK-145.8.6 (recreate) call create. Practice: Slack names are lowercase letters, digits, hyphens and underscores, at most 80 characters; on internal_error or fatal_error part of the create may have succeeded, so check for an existing channel before creating another (docs.slack.dev/reference/methods/conversations.create). Vendors key the name on a unique incident number: FireHydrant defaults to incident-{{ number }} and truncates to 80 (docs.firehydrant.com/docs/runbook-step-create-incident-channel); Datadog's default is incident-{public_id} (docs.datadoghq.com incident settings); Rootly uses incident-{{ incident.sequential_id }}-{{ incident.title }} or incident-YYYYMMDD-title (docs.rootly.com/integrations/create-slack-channel). Finding: the first recommendation (reuse the bot's own channel of that name) is unsafe: two incidents declared the same day under one title collide and the bot is a member of both. Only the bindings can tell a replay from a second incident. REVISED: the adapter makes one attempt and returns CONVERSATION_NAME_TAKEN quietly; find_own(name) is added; core/conversation_names.py keeps the pinned format with a Slack-safe slug and bounded suffixes (20); declare and recreate run the loop and reuse an own channel only when no binding names it. A unique incident number in the name (the vendor norm) needs a counter the record does not have; not proposed now (a user-visible change to a pinned format; candidate for the catalogue/coordination work in doc-15).

OQ2 ErrorCode. ADR: COVERED. operation-result.md:44 keeps the ErrorCode registry in contracts/operations; adding a member is the normal path. Human: accepted, with a taken name handled rather than logged as an error: logged at info, never warning; the warning comes only when every candidate is exhausted (declare).

OQ3 group_members(conversation, group_id). ADR: COVERED by people-and-accounts.md (account ids in the conversation's tenant) and the per-reference Protocol rule (incident-management.md:173). Human: accepted.

Scope adjustments proposed (applied once approved): TASK-145.7.9 plan gains the name loop (candidates, create, find_own plus binding check, exhausted warning with the pinned invoker message); TASK-145.8.6 reuses the same loop when it creates a conversation; incident-management.md gains the naming and convergence rule in this PR (Changes line); doc-11 row 18.L4a notes the rule.

Comments:
--------------------------------------------------
#1 - 2026-11-10 19:59 (UTC)
2026-11-10 program-scope assessment of the plan's OQ1-OQ3 (ADRs, doc-11, doc-15, prior and upcoming tasks, web practice).

OQ1 channel name and name_taken. ADR: GAP. No decision names the channel format or collision handling; incident-management.md:173 says only "create is added by TASK-145.7 with the first binding, converging on retry"; outbound-clients.md:26 requires a non-idempotent write to name its idempotency mechanism. doc-11 row 18 and doc-15: nothing on names. Prior: TASK-145.6.3 deferred create (name_taken re-raises today); TASK-145.7 OQ6 recorded "name_taken converges a retry"; TASK-36.1.1 pinned the format (incident-/incident-dev- + date slug, cut to 80; legacy_surface/test_incident_declare_surface.py:109-116, :254). Legacy: modules/incident/incident_conversation.py:23-71 tries -1, -2, ... with no bound and sends unsanitized titles (invalid_name_specials on punctuation). Upcoming: TASK-145.7.9 (declare) and TASK-145.8.6 (recreate) call create. Practice: Slack names are lowercase letters, digits, hyphens and underscores, at most 80 characters; on internal_error or fatal_error part of the create may have succeeded, so check for an existing channel before creating another (docs.slack.dev/reference/methods/conversations.create). Vendors key the name on a unique incident number: FireHydrant defaults to incident-{{ number }} and truncates to 80 (docs.firehydrant.com/docs/runbook-step-create-incident-channel); Datadog's default is incident-{public_id} (docs.datadoghq.com incident settings); Rootly uses incident-{{ incident.sequential_id }}-{{ incident.title }} or incident-YYYYMMDD-title (docs.rootly.com/integrations/create-slack-channel). Finding: the first recommendation (reuse the bot's own channel of that name) is unsafe: two incidents declared the same day under one title collide and the bot is a member of both. Only the bindings can tell a replay from a second incident. REVISED: the adapter makes one attempt and returns CONVERSATION_NAME_TAKEN quietly; find_own(name) is added; core/conversation_names.py keeps the pinned format with a Slack-safe slug and bounded suffixes (20); declare and recreate run the loop and reuse an own channel only when no binding names it. A unique incident number in the name (the vendor norm) needs a counter the record does not have; not proposed now (a user-visible change to a pinned format; candidate for the catalogue/coordination work in doc-15).

OQ2 ErrorCode. ADR: COVERED. operation-result.md:44 keeps the ErrorCode registry in contracts/operations; adding a member is the normal path. Human: accepted, with a taken name handled rather than logged as an error: logged at info, never warning; the warning comes only when every candidate is exhausted (declare).

OQ3 group_members(conversation, group_id). ADR: COVERED by people-and-accounts.md (account ids in the conversation's tenant) and the per-reference Protocol rule (incident-management.md:173). Human: accepted.

Scope adjustments proposed (applied once approved): TASK-145.7.9 plan gains the name loop (candidates, create, find_own plus binding check, exhausted warning with the pinned invoker message); TASK-145.8.6 reuses the same loop when it creates a conversation; incident-management.md gains the naming and convergence rule in this PR (Changes line); doc-11 row 18.L4a notes the rule.

#2 - 2026-11-10 20:05 (UTC)
2026-11-10 suffix practice check (human question: does a numeric suffix make sense?). Primary practice: tools avoid collisions with a short, human-readable incident number in the name, never a UUID: FireHydrant defaults to incident-{{ number }} (incident-42) (docs.firehydrant.com/docs/runbook-step-create-or-rename-incident-slack-channel); OneUptime names inc-123 (github.com/OneUptime/oneuptime/pull/4847); incident.io uses #inc-<number> channels with a configurable format (docs.incident.io/getting-started/installing, incident.io/changelog/2022-11-10). Collision fallback: OneUptime retries name_taken as inc-123-2, -3 ... up to -5, then logs the channel as not created; FireHydrant appends a dynamically calculated hash when a channel of that name exists. No source found for incident.io, PagerDuty, Grafana IRM or Dispatch collision handling. Conclusion: a numeric suffix is used and is the readable choice; start at -2 (the bare name is the first), bound at 5 names (date plus title collide only on same-day same-title declares). The incident number is the stronger fix and stays a doc-15 candidate (needs a counter on the record).

Comments:
--------------------------------------------------
#1 - 2026-11-10 19:59 (UTC)
2026-11-10 program-scope assessment of the plan's OQ1-OQ3 (ADRs, doc-11, doc-15, prior and upcoming tasks, web practice).

OQ1 channel name and name_taken. ADR: GAP. No decision names the channel format or collision handling; incident-management.md:173 says only "create is added by TASK-145.7 with the first binding, converging on retry"; outbound-clients.md:26 requires a non-idempotent write to name its idempotency mechanism. doc-11 row 18 and doc-15: nothing on names. Prior: TASK-145.6.3 deferred create (name_taken re-raises today); TASK-145.7 OQ6 recorded "name_taken converges a retry"; TASK-36.1.1 pinned the format (incident-/incident-dev- + date slug, cut to 80; legacy_surface/test_incident_declare_surface.py:109-116, :254). Legacy: modules/incident/incident_conversation.py:23-71 tries -1, -2, ... with no bound and sends unsanitized titles (invalid_name_specials on punctuation). Upcoming: TASK-145.7.9 (declare) and TASK-145.8.6 (recreate) call create. Practice: Slack names are lowercase letters, digits, hyphens and underscores, at most 80 characters; on internal_error or fatal_error part of the create may have succeeded, so check for an existing channel before creating another (docs.slack.dev/reference/methods/conversations.create). Vendors key the name on a unique incident number: FireHydrant defaults to incident-{{ number }} and truncates to 80 (docs.firehydrant.com/docs/runbook-step-create-incident-channel); Datadog's default is incident-{public_id} (docs.datadoghq.com incident settings); Rootly uses incident-{{ incident.sequential_id }}-{{ incident.title }} or incident-YYYYMMDD-title (docs.rootly.com/integrations/create-slack-channel). Finding: the first recommendation (reuse the bot's own channel of that name) is unsafe: two incidents declared the same day under one title collide and the bot is a member of both. Only the bindings can tell a replay from a second incident. REVISED: the adapter makes one attempt and returns CONVERSATION_NAME_TAKEN quietly; find_own(name) is added; core/conversation_names.py keeps the pinned format with a Slack-safe slug and bounded suffixes (20); declare and recreate run the loop and reuse an own channel only when no binding names it. A unique incident number in the name (the vendor norm) needs a counter the record does not have; not proposed now (a user-visible change to a pinned format; candidate for the catalogue/coordination work in doc-15).

OQ2 ErrorCode. ADR: COVERED. operation-result.md:44 keeps the ErrorCode registry in contracts/operations; adding a member is the normal path. Human: accepted, with a taken name handled rather than logged as an error: logged at info, never warning; the warning comes only when every candidate is exhausted (declare).

OQ3 group_members(conversation, group_id). ADR: COVERED by people-and-accounts.md (account ids in the conversation's tenant) and the per-reference Protocol rule (incident-management.md:173). Human: accepted.

Scope adjustments proposed (applied once approved): TASK-145.7.9 plan gains the name loop (candidates, create, find_own plus binding check, exhausted warning with the pinned invoker message); TASK-145.8.6 reuses the same loop when it creates a conversation; incident-management.md gains the naming and convergence rule in this PR (Changes line); doc-11 row 18.L4a notes the rule.

#2 - 2026-11-10 20:05 (UTC)
2026-11-10 suffix practice check (human question: does a numeric suffix make sense?). Primary practice: tools avoid collisions with a short, human-readable incident number in the name, never a UUID: FireHydrant defaults to incident-{{ number }} (incident-42) (docs.firehydrant.com/docs/runbook-step-create-or-rename-incident-slack-channel); OneUptime names inc-123 (github.com/OneUptime/oneuptime/pull/4847); incident.io uses #inc-<number> channels with a configurable format (docs.incident.io/getting-started/installing, incident.io/changelog/2022-11-10). Collision fallback: OneUptime retries name_taken as inc-123-2, -3 ... up to -5, then logs the channel as not created; FireHydrant appends a dynamically calculated hash when a channel of that name exists. No source found for incident.io, PagerDuty, Grafana IRM or Dispatch collision handling. Conclusion: a numeric suffix is used and is the readable choice; start at -2 (the bare name is the first), bound at 5 names (date plus title collide only on same-day same-title declares). The incident number is the stronger fix and stays a doc-15 candidate (needs a counter on the record).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10 implemented (L4a, side PR task-145.7.5-conversation-report-additions from main e9bcdcbc). Inert: no production caller until TASK-145.7.9 (declare) and TASK-145.8.6 (recreate).

What changed
- contracts/operations/codes.py: ErrorCode.CONVERSATION_NAME_TAKEN.
- core/domain.py: ReportPlacement(ResourceReference) with a required kw-only label; incident_conversation_names(title, opened_on, *, production) and CONVERSATION_NAME_ATTEMPTS = 5 (legacy format, accents dropped, refused characters one dash, cut to 80, then -2..-5). The plan's core/conversation_names.py became domain.py: the package-shape guard admits only layout-table names, and the baseline forbids new entries.
- core/api.py: IncidentConversation gains create(name, *, private), find_own(name), set_topic, create_canvas, group_members(conversation, group_id) and post(..., blocks); IncidentReport gains list_placements() and create_from_template(title, placement=None); the three new names exported.
- core/adapters/slack.py: the adapter takes the Slack tenant (build_incident_conversation reads [slack.tenant]); create is one call on the write handle (is_private only when private), name_taken returns CONVERSATION_NAME_TAKEN logged at info; find_own pages users.conversations (public and private, non-archived); canvas already existing counts as done; group_members reads usergroups.users.list on the read client; failures share one classifier helper.
- core/adapters/in_memory.py: the fake conversation and report gain the same behaviour (names, foreign_names, groups, placements ctor args; topic_of, canvas_of, is_private, blocks_in).
- core/adapters/google_docs.py: list_placements over the classified Drive listing (Templates left out, sorted by label, folder link); create_from_template files in the placement.
- decisions/incident-management.md: "One conversation per incident" paragraph (rules 1-5), a Checks test line, a 2026-11-10 Changes line.

Tests: conversation parity suite extended (create, taken names, find_own, topic, canvas, blocks, groups, not-writable, unsupported); new test_incident_core_conversation_create.py, test_incident_core_conversation_names.py, test_incident_core_report_placements.py; report parity extended; api surface pins updated; Slack stub in conftest extended.

Gates (cd app): ruff check . -> All checks passed; ruff format --check . -> 1173 files already formatted; make check-import-contracts -> 13 kept, 0 broken; make check-package-shape -> OK (3 baselined); make check-test-seams -> OK (47 strict, 12 legacy baselined); make check-fake-coverage -> OK; mypy . -> Found 41 errors in 14 files, none in touched files (the first full run found one new error at core/adapters/slack.py:344, fixed, then one rerun); pytest tests --ignore=tests/smoke -> 7109 passed.

For the human: no config, terraform, IAM or SSM change (no deploy-checks). The commit also carries the TASK-145.7.2 and TASK-145.8.2 Done task files and the TASK-176 note.

2026-11-10 follow-up (human review of the naming placement, fixed in this PR): the name rule mixed incident policy with Slack's rules, against incident-management.md (vendor behaviour once per system in core/adapters/; Slack today and Teams later: Teams allows 50 characters, keeps case, spaces and accents). Split: core/domain.py holds the platform-neutral ConversationName (title, opened_on, production, attempt 1-5; prefix and suffix) and incident_conversation_names returns five of them; core/adapters/slack.py renders one with slack_channel_name (accents dropped, refused characters one dash, cut to 80 before the suffix); IncidentConversation.create and find_own take a ConversationName; the fake renders with the Slack rule it stands in for. Tests: test_incident_core_conversation_names.py now covers the policy; new test_incident_core_conversation_slack_names.py covers Slack rendering; parity, create and api-surface tests take ConversationName. ADR paragraph and Changes line reworded.
Gates rerun after the change (cd app): ruff check . -> All checks passed; ruff format --check . -> 1174 files already formatted; check-import-contracts 13 kept 0 broken; package shape, test seams, fake coverage OK; mypy . -> Found 41 errors in 14 files, none in touched files; pytest tests --ignore=tests/smoke -> 7119 passed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-10T19:59:00Z

---

2026-11-10 program-scope assessment of the plan's OQ1-OQ3 (ADRs, doc-11, doc-15, prior and upcoming tasks, web practice).

OQ1 channel name and name_taken. ADR: GAP. No decision names the channel format or collision handling; incident-management.md:173 says only "create is added by TASK-145.7 with the first binding, converging on retry"; outbound-clients.md:26 requires a non-idempotent write to name its idempotency mechanism. doc-11 row 18 and doc-15: nothing on names. Prior: TASK-145.6.3 deferred create (name_taken re-raises today); TASK-145.7 OQ6 recorded "name_taken converges a retry"; TASK-36.1.1 pinned the format (incident-/incident-dev- + date slug, cut to 80; legacy_surface/test_incident_declare_surface.py:109-116, :254). Legacy: modules/incident/incident_conversation.py:23-71 tries -1, -2, ... with no bound and sends unsanitized titles (invalid_name_specials on punctuation). Upcoming: TASK-145.7.9 (declare) and TASK-145.8.6 (recreate) call create. Practice: Slack names are lowercase letters, digits, hyphens and underscores, at most 80 characters; on internal_error or fatal_error part of the create may have succeeded, so check for an existing channel before creating another (docs.slack.dev/reference/methods/conversations.create). Vendors key the name on a unique incident number: FireHydrant defaults to incident-{{ number }} and truncates to 80 (docs.firehydrant.com/docs/runbook-step-create-incident-channel); Datadog's default is incident-{public_id} (docs.datadoghq.com incident settings); Rootly uses incident-{{ incident.sequential_id }}-{{ incident.title }} or incident-YYYYMMDD-title (docs.rootly.com/integrations/create-slack-channel). Finding: the first recommendation (reuse the bot's own channel of that name) is unsafe: two incidents declared the same day under one title collide and the bot is a member of both. Only the bindings can tell a replay from a second incident. REVISED: the adapter makes one attempt and returns CONVERSATION_NAME_TAKEN quietly; find_own(name) is added; core/conversation_names.py keeps the pinned format with a Slack-safe slug and bounded suffixes (20); declare and recreate run the loop and reuse an own channel only when no binding names it. A unique incident number in the name (the vendor norm) needs a counter the record does not have; not proposed now (a user-visible change to a pinned format; candidate for the catalogue/coordination work in doc-15).

OQ2 ErrorCode. ADR: COVERED. operation-result.md:44 keeps the ErrorCode registry in contracts/operations; adding a member is the normal path. Human: accepted, with a taken name handled rather than logged as an error: logged at info, never warning; the warning comes only when every candidate is exhausted (declare).

OQ3 group_members(conversation, group_id). ADR: COVERED by people-and-accounts.md (account ids in the conversation's tenant) and the per-reference Protocol rule (incident-management.md:173). Human: accepted.

Scope adjustments proposed (applied once approved): TASK-145.7.9 plan gains the name loop (candidates, create, find_own plus binding check, exhausted warning with the pinned invoker message); TASK-145.8.6 reuses the same loop when it creates a conversation; incident-management.md gains the naming and convergence rule in this PR (Changes line); doc-11 row 18.L4a notes the rule.

---

created: 2026-11-10T20:05:00Z

---

2026-11-10 suffix practice check (human question: does a numeric suffix make sense?). Primary practice: tools avoid collisions with a short, human-readable incident number in the name, never a UUID: FireHydrant defaults to incident-{{ number }} (incident-42) (docs.firehydrant.com/docs/runbook-step-create-or-rename-incident-slack-channel); OneUptime names inc-123 (github.com/OneUptime/oneuptime/pull/4847); incident.io uses #inc-<number> channels with a configurable format (docs.incident.io/getting-started/installing, incident.io/changelog/2022-11-10). Collision fallback: OneUptime retries name_taken as inc-123-2, -3 ... up to -5, then logs the channel as not created; FireHydrant appends a dynamically calculated hash when a channel of that name exists. No source found for incident.io, PagerDuty, Grafana IRM or Dispatch collision handling. Conclusion: a numeric suffix is used and is the readable choice; start at -2 (the bare name is the first), bound at 5 names (date plus title collide only on same-day same-title declares). The incident number is the stronger fix and stays a doc-15 candidate (needs a counter on the record).

---

created: 2026-11-10T20:12:00Z

---

2026-11-10: plan approved by the human (OQ1 revised with suffixes -2..-5, OQ1b one-channel-per-incident rules I1-I5, OQ2 quiet CONVERSATION_NAME_TAKEN, OQ3 group_members(conversation, group_id)).

---
<!-- COMMENTS:END -->
