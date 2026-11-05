---
id: TASK-145.6.3
title: >-
  IncidentConversation with writability; the transcript reader takes a
  ConversationReference
status: In Progress
assignee: []
created_date: '2026-11-05T00:44:00Z'
updated_date: '2026-11-05T20:50:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.6.2
parent_task_id: TASK-145.6
priority: medium
ordinal: 483000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 12c of Stack K (TASK-145.6 plan, approved 2026-11-05). IncidentConversation Protocol on ConversationReference (post, set purpose, add bookmark, invite, archive, is_writable) with SlackIncidentConversation beside the transcript reader over the Slack client factory and classify_slack_error, an in-memory fake, and conversation_is_writable next to find_incident_for_conversation (decisions/incident-management.md: called only before a write to the conversation). No legacy caller is repointed; its consumers are TASK-145.7, 145.8 and 145.10. IncidentTranscriptReader.read_transcript and conversation_started_at take a ConversationReference; scribe and comms pass incident.conversation from the record that TASK-145.6.2 already resolves. The report link from the record and the deletion of scribe/adapters/slack.py, IncidentReportLinkLookup and its provider moved to TASK-145.6.2 (C3, approved 2026-11-05).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 IncidentConversation is an async Protocol in core/api.py (post, set_purpose, add_bookmark, invite, archive, is_writable; no create, which TASK-145.7 adds); SlackIncidentConversation implements it in core/adapters/slack.py and InMemoryIncidentConversation is its fake, with a parity test
- [x] #2 is_writable is false for an archived channel and when the bot is not a member, true for an open one; conversation_is_writable(conversations, conversation | None) is exported beside find_incident_for_conversation and answers false for None without a call
- [x] #3 read_transcript and conversation_started_at take a ConversationReference and return OperationResult; a reference of another system returns UNSUPPORTED_OPERATION without a Slack call; unknown Slack errors propagate
- [x] #4 No user-visible command or reply changes (a failed transcript read gives today's reply); existing log events are kept; the legacy_surface, scribe and comms suites pass
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports, make check-import-contracts, make check-settings-key-ownership and pytest tests --ignore=tests/smoke pass
- [x] #6 Non-idempotent Slack writes go through a handle that retries only rate-limited requests; the not-writable Slack codes are in the Slack classification table and map to CONVERSATION_NOT_WRITABLE
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Full plan 2026-11-05, grounded at 12b (8704abdd) on stack-k/task-145.6.3-incident-conversation; revised the same day after a program-scope assessment of OQ1-OQ6 against every ADR, doc-11 and doc-15 (replaces the first full plan; the outline was TASK-145.6 steps 11-13 narrowed by 145.6.2 C3). PROPOSED, awaiting human approval.

## Size gate: passes, at the limit
9 production files (core/api.py, core/adapters/slack.py, core/adapters/in_memory.py, scribe/service.py, scribe/entrypoints/slack.py, comms/service.py, integrations/slack/client.py, integrations/slack/settings.py, contracts/operations/codes.py one line), ~410 production LOC. Two subsystems: the incident umbrella and the Slack vendor package (the error-code registry line is the reviewed one-line change operation-result.md prescribes). No mechanical move. Docs: features/incident/README.md, scribe/README.md, comms/README.md, decisions (see Cascade). Tests: 5 new files, ~14 edited. If review prefers, steps 1-2 of the Slack vendor package (write handle, classification table) split out as a side PR before 12c.

## Discovered state (12b)
- core/api.py (255): IncidentTranscriptReader :97 (conversation_started_at(conversation_id: str) :106, read_transcript(conversation_id: str, *, since, limit, exclude_own_and_system_messages=False) :115; never raises, empty on failure, not an OperationResult); IncidentReport :141; get_incident_report lru_cache :235; get_incident_transcript_reader lru_cache :241; find_incident_for_conversation(store, conversation) :247. __all__ :58-93 exports ConversationReference and MessageReference.
- core/adapters/slack.py (318): SlackIncidentTranscriptReader(client) :42; conversations_info :56 (created only); history, replies, auth_test, users_info all keyed on the conversation id string; bare except with logs; build_incident_transcript_reader :242 over integrations.slack.client.get_slack_web_client (:37). Allowed by import contract (e) "**.adapters.** -> integrations.**".
- classify_slack_error (integrations/slack/client.py:67): UNAUTHORIZED, NOT_FOUND (channel_not_found, user_not_found, ...), TRANSIENT_ERROR (ratelimited, ... with retry-after); re-raises any other code, so not_in_channel, is_archived, already_in_channel, name_taken re-raise. No incident code uses it today.
- 12b pattern to copy: unsupported system -> OperationResult.permanent_error(..., ErrorCode.UNSUPPORTED_OPERATION) with incident_report_system_unsupported (google_docs.py:709); InMemoryIncidentReport (in_memory.py:155); parity suite test_incident_core_report_protocol_parity.py parametrized ["google", "in_memory"].
- domain.py: ConversationReference(ResourceReference) :181 {system, tenant, vendor_id, url}; Incident.conversation: ConversationReference | None :259; MessageReference :278 {system, tenant, conversation_id, message_id}.
- Reader callers: scribe/service.py draft path :260 (holds the record from find_incident_for_conversation), :280-281 read_transcript(conversation.vendor_id, ...), :553 conversation_started_at; summarize path summarize_incident_conversation(conversation_id: str) :899 (no lookup; :929, :1018), called from scribe/entrypoints/slack.py:243 with payload.channel_id (the draft entrypoint :185-186 builds the reference from systems.tenants()[SLACK]); comms/service.py :177/:193 and :360/:375 hold the record, _read_window(reader, conversation.vendor_id, ...) :508-530 (:523, :524).
- Legacy conversation writes (modules/incident, untouched here): core.py create/purpose/topic/bookmarks/invite/posts (:133-610), incident_conversation.py:51 conversations_create, incident_roles.py:54 setPurpose, incident_helper.py:451-501 join then post then archive, plus status, update, nudge, retro posts. Pre-write checks: is_archived and is_member in incident_conversation.py:93-96, incident_folder.py:488-494; none in close_incident. No feature code writes to a conversation.

## Steps
1. integrations/slack/client.py: get_async_slack_write_client() (cached, bot token, AsyncRateLimitErrorRetryHandler only: a 429 means Slack did not process the request; no connection or server-error replay, because Slack documents that after internal_error or fatal_error part of the operation may have succeeded). outbound-clients.md non-idempotent write rule; Google (TASK-87) and Opsgenie (TASK-25.6) already follow it, Slack had no write path in feature code until now.
2. integrations/slack/settings.py: the classification table gains not_writable_errors (is_archived, not_in_channel, restricted_action, restricted_action_read_only_channel, ekm_access_denied) mapped by classify_slack_error to PERMANENT_ERROR with the Slack code; unknown codes still propagate (outbound-clients.md: unexpected exceptions are not classified). Existing users (oncall_sync, tenant verification) call none of these methods: no change for them. contracts/operations/codes.py: ErrorCode.CONVERSATION_NOT_WRITABLE.
3. core/api.py: runtime_checkable Protocol IncidentConversation, async (transport-slack.md: an outbound-only Slack caller uses an AsyncWebClient), every method taking the ConversationReference:
   - post(conversation, text) -> OperationResult[MessageReference] (text only, no vendor blocks; the MessageReference serves the primary-message direction);
   - set_purpose(conversation, text), add_bookmark(conversation, title, link), invite(conversation, account_ids: Sequence[str]), archive(conversation) -> OperationResult[None];
   - is_writable(conversation) -> OperationResult[bool].
   No create (OQ1: 145.7 adds it with the first working-surface binding). conversation_is_writable(conversations, conversation: ConversationReference | None) -> OperationResult[bool] beside find_incident_for_conversation: None -> success False without a call (OQ4). get_incident_conversation() lru_cache provider. __all__ gains IncidentConversation, conversation_is_writable, get_incident_conversation.
4. core/adapters/slack.py: SlackIncidentConversation(reads: AsyncWebClient, writes: AsyncWebClient) and build_incident_conversation() over get_async_slack_web_client (reads) and get_async_slack_write_client (post, bookmark; purpose, invite, archive too, one write handle).
   - Every method: reference system not SLACK -> permanent_error UNSUPPORTED_OPERATION, event incident_conversation_system_unsupported, no call.
   - is_writable: conversations_info; is_archived -> False; is_member False -> False; open and member -> True; classified errors returned (channel_not_found NOT_FOUND).
   - Operation-level success equivalents handled before classification: already_in_channel and cant_invite_self (invite), already_archived (archive); empty invite list makes no call.
   - Other SlackApiError -> classify_slack_error; not_writable_errors -> PERMANENT_ERROR CONVERSATION_NOT_WRITABLE; unknown codes and non-Slack exceptions propagate. Events incident_conversation_<op>_failed with the Slack code.
5. core/adapters/slack.py, reader (OQ5): conversation_started_at(conversation) -> OperationResult[datetime | None] and read_transcript(conversation, *, since, limit, exclude_own_and_system_messages=False) -> OperationResult[Sequence[TranscriptMessage]]; another system -> UNSUPPORTED_OPERATION, no call; SlackApiError classified through classify_slack_error (a failed first page is the result; a failed later page or name lookup keeps today's partial result); the bare except goes, unknown errors propagate. Existing events kept.
6. core/adapters/in_memory.py: InMemoryIncidentConversation (async; tenant, seeded archived and non-member conversations; records posts with generated ts, purposes, bookmarks, invites, archives; same unsupported and not-writable results) and the reader fake used by scribe and comms tests if a shared one helps.
7. scribe/service.py: the draft path passes incident.conversation from the record found at :260 (None -> the empty-transcript reply, reader not called); a non-success read gives today's empty-transcript reply (same reply, so AC #4 holds). summarize_incident_conversation(conversation: ConversationReference, ...) and both window-start helpers take the reference and map a non-success started-at to today's fallback window. No incident lookup added to summarize here (OQ6).
8. scribe/entrypoints/slack.py: the summarize handler (:243) builds the ConversationReference from systems.tenants()[SLACK] as the draft handler does (:185-186); no channel -> today's error reply.
9. comms/service.py: :193 and :375 pass incident.conversation; _read_window takes the reference and maps a non-success to today's empty window.
10. Tests and docs: stubs and legacy_surface conftest follow the new signatures and results; test_incident_core_api_surface.py asserts the new names and annotations; READMEs updated; decisions per Cascade.

No legacy caller is repointed: legacy writes are rebuilt in 145.7 (declare), 145.8 (status, roles purpose, archive, recreate) and 145.10 (retro confirmation), each calling conversation_is_writable before a write. The port ships unused.

## AC traceability
| AC | Steps | Tests |
| --- | --- | --- |
| 1 Protocol, Slack adapter, fake, parity | 3, 4, 6 | test_incident_core_conversation_protocol_parity.py (slack over AsyncMock(spec=AsyncWebClient), in_memory) |
| 2 is_writable; helper exported | 3, 4 | test_incident_core_conversation_writable.py |
| 3 reader takes a reference; other system unsupported | 5, 7-9 | test_incident_core_transcript_read.py, test_incident_core_conversation_started_at.py (edited), test_incident_core_transcript_unsupported.py |
| 4 no visible change | 7-9 | legacy_surface, scribe and comms suites: reply asserts unchanged; a failed read gives the same reply as today |
| 5 gates | all | ruff, mypy, lint-imports, make check-import-contracts, make check-settings-key-ownership, pytest |
Proposed AC #6 (on approval): non-idempotent Slack writes go through a handle that retries only rate-limited requests (steps 1, 4; test_slack_client_write_handle.py: handler list is the rate-limit handler only).

## Test matrix
- Write handle and table (test_slack_client_write_handle.py, test_slack_client_classify_error.py): write handle has only the rate-limit handler; not_writable codes -> PERMANENT_ERROR with the code; unknown code still raises.
- Operations (test_incident_core_conversation_operations.py): post returns MessageReference (channel, ts); purpose; bookmark type link; invite several, already_in_channel and cant_invite_self success, empty list no call; archive, already_archived success.
- Writability (test_incident_core_conversation_writable.py): open member True; archived False; not a member False; channel_not_found NOT_FOUND; ratelimited TRANSIENT with retry-after; conversation_is_writable(None) False without a call; another system UNSUPPORTED.
- Errors (test_incident_core_conversation_errors.py): post to is_archived / not_in_channel / restricted_action_read_only_channel -> CONVERSATION_NOT_WRITABLE; an unknown Slack code raises.
- Parity: both implement the Protocol; observable results equal; another system UNSUPPORTED in both.
- Reader: by reference; failed first page -> classified non-success; GOOGLE reference -> UNSUPPORTED, no call; unknown code raises.
- Scribe: draft passes the record's conversation; record without conversation and failed read -> today's empty-transcript reply; summarize builds the reference; no channel -> unchanged error. Comms: _read_window gets incident.conversation; failed read -> empty window as today.

## Domain-model evolution gate
No stored entity changes; no new reference type. Target shape checked: the coordinated-incidents analysis (6.3) makes the record surface-free, with IncidentSurfaceBinding child records (kind chat_conversation or backstage_page, exactly one primary that receives the bot's posts, at least one while active, commands found through any bound conversation); doc-11 row 18 re-plans 145.7 with E1.1/E1.2 after the A1 amendment (row 17a). incident.io's streams (2024) give each workstream its own channel with updates flowing both ways, the same per-conversation shape.
Cardinality, conversations per incident: 0 (declare failed after the record; a backstage_page-only incident), 1 (today), many (E1 bindings, E7 workstreams as child incidents with their own first binding).
| Scenario | Holds because |
| --- | --- |
| Single-team outage (happy path) | command channel = incident.conversation; same reads and writes as today |
| Archived channel, status update (145.8) | conversation_is_writable False skips only the post; the record update succeeds |
| Bot removed from a private channel | is_member False or not_in_channel -> not writable, a classified result, never a crash |
| Command in a secondary bound channel (E1, the case most likely to break) | the port is per reference and conversation_is_writable takes a reference, so the caller passes the primary binding's reference after E1 and incident.conversation before it; neither the port nor the helper changes |
| Backstage-only incident (analysis 6.3) | no chat binding -> conversation_is_writable(None) False; posts skipped |
| Embargoed security incident (private channel) | the adapter acts as the bot; visibility unchanged by the port; private creation is 145.7's |
| Retry after a Slack 5xx on post | no replay on the write handle: one message, a classified TRANSIENT result for the caller to decide |
| Second suite (Teams) | another system's reference -> UNSUPPORTED until a Teams adapter is selected by the reference's system |
Rejected: create on the port now (declare's first binding is a durable, retry-converging operation designed with E1 in 145.7); conversation_is_writable taking the Incident (the record loses its conversation field under E1, so the signature would change); passing the command's channel to the reader (wrong once several channels bind one incident); Slack blocks in the Protocol; join inside is_writable (a check must not mutate); an adapter-local error table (outbound-clients.md: one table per vendor).

## Assumptions and doubts (how verified)
- conversations.info reports is_member for the bot; a private channel the bot left answers channel_not_found. Verify in the Slack reference at implementation; pin with tests.
- The async port is called from today's sync Bolt handlers through asyncio.run, as scribe's entrypoints already do; the reader stays synchronous on WebClient in this layer (its callers in comms are synchronous), recorded as a tolerated divergence in transport-slack.md's sense (Cascade).
- MessageReference.message_id carries the Slack ts.
- Tenant: the adapter checks only the system; a (system, tenant) pair waits for an instance with several tenants.

## Blast radius and rollback
Production paths changed: /sre incident draft and summarize and comms status-update drafts read transcripts by reference with classified results; a bug empties or breaks those commands, not declare, status, roles or archive. Unknown Slack errors in the reader now raise into the handlers' error boundary (generic error reply) instead of an empty transcript. The Slack table change affects only codes no existing caller receives. One git revert. No terraform, IAM, SSM or env-name change: no deploy-checks.

## Cascade (applied on approval)
- decisions/incident-management.md: tolerated line "IncidentTranscriptReader taking a conversation id string" deleted; the IncidentConversation list notes create arrives with declare's first working-surface binding (145.7, after A1); a log line.
- decisions/outbound-clients.md: Slack writes follow the non-idempotent rule through the rate-limit-only write handle (change line); legacy modules/incident Slack writes on the retrying handle listed as tolerated until TASK-145.13.
- decisions/transport-slack.md: the reader on the synchronous WebClient listed as tolerated, closing when its last caller moves (TASK-145.11 for draft, 145.9.2 for summarize, comms with its next rebuild); the write handle named.
- TASK-145.7: adds create(name, *, private) to IncidentConversation, retry-converging with the first binding (E1.1/E1.2), on the write handle; note.
- TASK-145.9: AC added: /sre incident summarize resolves its incident through find_incident_for_conversation (a channel that is not an incident gets the not-an-incident reply) and reads the incident's conversation; layer chosen at its split approval (not in the mechanical 145.9.2).
- TASK-135.1's empty-on-failure reader decision (human, 2026-10-02) is superseded by OQ5; comment on TASK-145.6.3.
## Open questions, assessed at program scope (recommendation first)
- OQ1 create on IncidentConversation. ADR: incident-management.md lists post, purpose, bookmark, invite, archive, writability, no create (gap). Target: analysis 6.3, declare creates the record and its first working-surface binding as one durable operation; doc-11 row 18 re-plans 145.7 with E1.1/E1.2 after A1 (row 17a); Slack create is not idempotent (name_taken on replay). Prior: IncidentReport.create_from_template (12b). Rec: not in 12c; 145.7 adds create with the binding and its retry convergence; the ADR list notes it. (Reverses the first plan's rec.)
- OQ2 Slack error mapping. ADR: outbound-clients.md decides it: one classification table per vendor in integrations/<vendor>/, adapters classify, unexpected exceptions propagate. The first plan's adapter-local table and never-raise conflicted. Rec: not-writable codes join the Slack table (PERMANENT_ERROR), operation-level success equivalents stay in the adapter, unknown codes propagate.
- OQ3 invite arguments. ADR: people-and-accounts.md decides it: a platform account is (platform, tenant, account_id); records store person ids; resolving a person to a chat account is the people capability's (TASK-83.x), on-call people come from the on-call capability (oncall.md, TASK-146.3) and declare resolves them (145.7). Rec: invite(conversation, account_ids) with ids in the conversation's (system, tenant); no gap.
- OQ4 which reference the writability check and the readers use. ADR: incident-management.md, resources are reached through stored references; target: the record knows no surface, the primary binding receives the bot's posts (analysis 6.3, row 18). Prior: 145.5.5 passes a ConversationReference to comms; 145.6.2 C3 reads the report from the record. Rec: conversation_is_writable(conversations, conversation | None) and callers pass incident.conversation today, the primary binding after E1 (145.7); the helper survives E1 unchanged. (Revises the first plan's Incident argument.)
- OQ5 the reader's empty-on-failure contract. ADR: operation-result.md, OperationResult flows adapter -> service, and outbound-clients.md, unexpected errors propagate; the reader's bare except and empty value conflict (unrecorded divergence from TASK-135.1, a behaviour-preserving human choice). Upcoming: none changes it; 12c already changes every caller and stub. Rec: the reader returns OperationResult in 12c, callers map non-success to today's reply (no visible change for classified failures; unknown errors reach the error boundary). Alternative: keep it and record the divergence.
- OQ6 summarize and the command check. ADR: incident-management.md Checks, every incident command resolves through find_incident_for_conversation; summarize is a response command ("a responder catching up"). Upcoming: 145.9.2 moves summarize mechanically, so no task adds the check (gap). Rec: 12c keeps behaviour (reference from the command's channel); 145.9 gains the AC (Cascade). Alternative: add it in 12c (visible change against AC #4).
- G1 (new) non-idempotent Slack writes. ADR: outbound-clients.md requires an idempotency mechanism or a retries-disabled handle; the shared Slack clients retry connection and server errors on every call, and Slack documents that internal_error or fatal_error may follow partial success. Prior: TASK-87 (Google), TASK-25.6 (Opsgenie); none for Slack. Rec: the rate-limit-only write handle in 12c (steps 1, 4; proposed AC #6).
- G2 (new) async. ADR: transport-slack.md, an outbound-only Slack caller uses an AsyncWebClient. Rec: IncidentConversation async now (its consumers are not built yet); the reader stays sync this layer and is recorded as tolerated (Cascade).

Sources: outbound-clients.md, operation-result.md, transport-slack.md, people-and-accounts.md, incident-management.md; large-scale-incident-analysis.md 6.3; Slack chat.postMessage reference (errors, internal_error retry note) https://docs.slack.dev/reference/methods/chat.postMessage ; Python Slack SDK retry handlers https://docs.slack.dev/tools/python-slack-sdk/web/ ; incident.io multiple streams https://incident.io/changelog/multiple-streams
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-05 (human): TASK-145.6.2 C3 approved; the report-link AC (old #4: no IncidentReportLinkLookup or scribe/adapters/slack.py; report from the record) moved to TASK-145.6.2 and was removed here; title and description narrowed.

2026-11-05 (12c session): implemented with TDD on stack-k/task-145.6.3-incident-conversation above the plan commits (94d43ef2), uncommitted, In Progress. Steps 1-10 done: get_async_slack_write_client (AsyncRateLimitErrorRetryHandler only; built per call like the other Slack factories, cached by get_incident_conversation) and not_writable_errors in the Slack table -> PERMANENT_ERROR, mapped by the adapter to ErrorCode.CONVERSATION_NOT_WRITABLE; IncidentConversation (async; post, set_purpose, add_bookmark, invite, archive, is_writable; no create), SlackIncidentConversation, InMemoryIncidentConversation, conversation_is_writable(conversations, conversation | None), get_incident_conversation; the reader takes a ConversationReference and returns OperationResult (bare excepts gone; later pages, threads, name and identity lookups degrade only on classified Slack errors); scribe draft and comms read the record's conversation, summarize builds the reference in its handler (scopes passed like draft); a failed read gives today's reply. Within the plan, recorded in incident-management.md and outbound-clients.md: ekm_access_denied stays UNAUTHORIZED (a code sits in one catalogue; it was already there); restricted_action_thread_only_channel added (the port posts top-level only); invite sends force=True so one present account does not block the rest (Slack conversations.invite); is_member must be true for writable. Behaviour note: errors the Slack table does not name, connection errors included, now reach the command error boundary ("Error executing ...") instead of an empty transcript. Size: 9 production code files, +558/-90 incl. the fake (155) and docstrings, over the ~410 estimate. Tests: 4 new conversation files and a core conftest StubSlack, test_slack_client_write_handle.py; reader, api surface, scribe and comms stubs updated. Gates: ruff OK; make check-import-contracts 13 kept; make check-settings-key-ownership OK; mypy 41 errors, all pre-existing, none in touched files; pytest tests --ignore=tests/smoke 6396 passed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-05T20:31:00Z

---

2026-11-05 (human): revised plan approved: OQ1-OQ6, G1 and G2 as recommended. OQ1 create goes to TASK-145.7 with the first working-surface binding; OQ2 not-writable codes join the Slack classification table, unknown codes propagate; OQ3 invite takes chat account ids; OQ4 conversation_is_writable(conversations, conversation | None); OQ5 the reader returns OperationResult, superseding TASK-135.1's empty-on-failure choice (2026-10-02), callers keep today's replies; OQ6 summarize keeps behaviour here, TASK-145.9 gains the command-check AC; G1 rate-limit-only Slack write handle; G2 IncidentConversation async, the reader stays synchronous (tolerated in transport-slack.md). ACs reworded to the decisions (#1-#4) and #6 added. Cascade applied: incident-management.md, outbound-clients.md, transport-slack.md, TASK-145.7, TASK-145.9.

---
<!-- COMMENTS:END -->
