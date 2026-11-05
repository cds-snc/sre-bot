---
id: TASK-145.6.3
title: >-
  IncidentConversation with writability; the transcript reader takes a
  ConversationReference
status: To Do
assignee: []
created_date: '2026-11-05T00:44:00Z'
updated_date: '2026-11-05T20:17:00Z'
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
- [ ] #1 IncidentConversation is a Protocol in core/api.py; SlackIncidentConversation implements it in core/adapters/slack.py and InMemoryIncidentConversation is its fake, with a parity test
- [ ] #2 is_writable is false for an archived channel and for not_in_channel, true for an open one; conversation_is_writable is exported beside find_incident_for_conversation
- [ ] #3 read_transcript and conversation_started_at take a ConversationReference; a reference of another system returns an unsupported result
- [ ] #4 No user-visible command, reply or log event changes; the legacy_surface, scribe and comms suites pass
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports, make check-import-contracts, make check-settings-key-ownership and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Full plan 2026-11-05, grounded at 12b (8704abdd) on stack-k/task-145.6.3-incident-conversation. Replaces the outline (TASK-145.6 steps 11-13, narrowed by 145.6.2 C3). PROPOSED, awaiting human approval.

## Size gate: passes
6 production files (core/api.py, core/adapters/slack.py, core/adapters/in_memory.py, scribe/service.py, scribe/entrypoints/slack.py, comms/service.py), ~390 production LOC (~410 with OQ1), one subsystem (incident umbrella), new port plus a signature change, no mechanical move. Docs: features/incident/README.md, scribe/README.md, comms/README.md. Tests: 4 new files, ~14 edited (reader stubs change signature).

## Discovered state (12b)
- core/api.py (255): IncidentTranscriptReader :97 (conversation_started_at(conversation_id: str) :106, read_transcript(conversation_id: str, *, since, limit, exclude_own_and_system_messages=False) :115; never raises, empty on failure, not an OperationResult); IncidentReport :141; get_incident_report lru_cache :235; get_incident_transcript_reader lru_cache :241; find_incident_for_conversation(store, conversation) :247. __all__ :58-93 exports ConversationReference and MessageReference.
- core/adapters/slack.py (318): SlackIncidentTranscriptReader(client) :42; conversations_info :56 (created only); history, replies, auth_test, users_info all keyed on the conversation id string; bare except with logs; build_incident_transcript_reader :242 over integrations.slack.client.get_slack_web_client (:37). Allowed by import contract (e) "**.adapters.** -> integrations.**".
- classify_slack_error (integrations/slack/client.py:67): UNAUTHORIZED, NOT_FOUND (channel_not_found, user_not_found, ...), TRANSIENT_ERROR (ratelimited, ... with retry-after); re-raises any other code, so not_in_channel, is_archived, already_in_channel, name_taken re-raise. No incident code uses it today.
- 12b pattern to copy: unsupported system -> OperationResult.permanent_error(..., ErrorCode.UNSUPPORTED_OPERATION) with incident_report_system_unsupported (google_docs.py:709); InMemoryIncidentReport (in_memory.py:155); parity suite test_incident_core_report_protocol_parity.py parametrized ["google", "in_memory"].
- domain.py: ConversationReference(ResourceReference) :181 {system, tenant, vendor_id, url}; Incident.conversation: ConversationReference | None :259; MessageReference :278 {system, tenant, conversation_id, message_id}.
- Reader callers: scribe/service.py draft path :260 (holds the record from find_incident_for_conversation), :280-281 read_transcript(conversation.vendor_id, ...), :553 conversation_started_at; summarize path summarize_incident_conversation(conversation_id: str) :899 (no lookup; :929, :1018), called from scribe/entrypoints/slack.py:243 with payload.channel_id (the draft entrypoint :185-186 builds the reference from systems.tenants()[SLACK]); comms/service.py :177/:193 and :360/:375 hold the record, _read_window(reader, conversation.vendor_id, ...) :508-530 (:523, :524).
- Legacy conversation writes (modules/incident, untouched here): core.py create/purpose/topic/bookmarks/invite/posts (:133-610), incident_conversation.py:51 conversations_create, incident_roles.py:54 setPurpose, incident_helper.py:451-501 join then post then archive, plus status, update, nudge, retro posts. Pre-write checks: is_archived and is_member in incident_conversation.py:93-96, incident_folder.py:488-494; none in close_incident. No feature code writes to a conversation.

## Steps
1. core/api.py: runtime_checkable Protocol IncidentConversation, every method taking the ConversationReference (never a channel name), synchronous like the reader and IncidentReport:
   - post(conversation, text) -> OperationResult[MessageReference] (text only, no vendor blocks; the MessageReference serves the primary-message direction, ADR "primary message", without a second change);
   - set_purpose(conversation, text) -> OperationResult[None];
   - add_bookmark(conversation, title, link) -> OperationResult[None];
   - invite(conversation, user_ids: Sequence[str]) -> OperationResult[None] (vendor user ids in the reference's tenant; resolving people stays with the caller, OQ3);
   - archive(conversation) -> OperationResult[None];
   - is_writable(conversation) -> OperationResult[bool];
   - with OQ1: create(name, *, private) -> OperationResult[ConversationReference].
   conversation_is_writable(conversations: IncidentConversation, incident: Incident) -> OperationResult[bool] beside find_incident_for_conversation: success False when incident.conversation is None, else conversations.is_writable(incident.conversation) (OQ4). get_incident_conversation() lru_cache provider beside the reader's. __all__ gains IncidentConversation, conversation_is_writable, get_incident_conversation.
2. core/adapters/slack.py: SlackIncidentConversation(client) and build_incident_conversation() over get_slack_web_client.
   - Every method: reference system not SLACK -> permanent_error UNSUPPORTED_OPERATION, event incident_conversation_system_unsupported, no client call.
   - is_writable: conversations_info; is_archived -> False; is_member False -> False (not_in_channel); open and member -> True; channel_not_found -> NOT_FOUND (classified).
   - Writes: chat_postMessage (MessageReference from channel and ts), conversations_setPurpose, bookmarks_add(type link), conversations_invite (already_in_channel and cant_invite_self are success; the call is skipped for an empty list), conversations_archive (already_archived is success); with OQ1 conversations_create(name, is_private) -> ConversationReference(SLACK, tenant from the Slack tenant entry read at call time, channel id).
   - Errors (OQ2): one module helper _classify(exc) maps is_archived, not_in_channel, channel_is_archived -> permanent_error CONVERSATION_NOT_WRITABLE (new ErrorCode if none fits; checked at implementation), name_taken -> permanent_error CONFLICT-type code, then classify_slack_error for the rest; a code it re-raises becomes permanent_error with the Slack code in the message. Never raises to the caller; events incident_conversation_<op>_failed with the code. No change to integrations/slack/settings.py lists (other users' classification unchanged).
3. core/adapters/slack.py, reader: conversation_started_at(conversation: ConversationReference) and read_transcript(conversation: ConversationReference, *, since, limit, exclude_own_and_system_messages=False); a reference of another system -> None / () and event incident_transcript_system_unsupported, no client call (AC #3, OQ5); otherwise conversation.vendor_id goes where the string went. Existing events and behaviour unchanged.
4. core/adapters/in_memory.py: InMemoryIncidentConversation (tenant, next ids; seeded archived and non-member conversations; records posts, purposes, bookmarks, invites, archives; create allocates C-ids; same unsupported and not-writable results as Slack).
5. scribe/service.py: the draft path passes incident.conversation from the record found at :260 (OQ4: a record with no conversation reads no transcript, today's empty-transcript reply); _resolve_draft_window_start takes the reference. summarize_incident_conversation(conversation: ConversationReference, ...) (:899) and _resolve_summary_window_start take the reference; no incident lookup added (OQ6).
6. scribe/entrypoints/slack.py: the summarize handler (:243) builds the ConversationReference from systems.tenants()[SLACK] as the draft handler does (:185-186); no channel -> today's error reply.
7. comms/service.py: :193 and :375 pass incident.conversation; _read_window takes ConversationReference (:508-530).
8. Tests and docs: test stubs and legacy_surface conftest follow the new signatures; test_incident_core_api_surface.py asserts the three new names and the reference annotations; features/incident/README.md core row (IncidentConversation and conversation_is_writable present, not planned), scribe and comms READMEs (reader takes a reference). decisions/incident-management.md: the tolerated-debt line "IncidentTranscriptReader taking a conversation id string" deleted; log line.

No legacy caller is repointed: legacy writes are rebuilt in 145.7 (declare: create, purpose, bookmarks, invites, posts), 145.8 (status, roles purpose, archive, recreate) and 145.10 (retro confirmation), each calling conversation_is_writable before a write. Until then the port has no production caller (approved in the 145.6 plan).

## AC traceability
| AC | Steps | Tests |
| --- | --- | --- |
| 1 Protocol, Slack adapter, fake, parity | 1, 2, 4 | test_incident_core_conversation_protocol_parity.py (slack over MagicMock(spec=WebClient), in_memory) |
| 2 is_writable; helper exported | 1, 2 | test_incident_core_conversation_writable.py |
| 3 reader takes a reference; other system unsupported | 3, 5-7 | test_incident_core_transcript_read.py, test_incident_core_conversation_started_at.py (edited), test_incident_core_transcript_unsupported.py |
| 4 no visible change | 3, 5-7 | legacy_surface, scribe and comms suites unchanged in asserts; only stub signatures change |
| 5 gates | all | ruff, mypy, lint-imports, make check-import-contracts, make check-settings-key-ownership, pytest |

## Test matrix
- Operations (test_incident_core_conversation_operations.py): post returns MessageReference (channel, ts); purpose; bookmark with type link; invite several, already_in_channel success, empty list makes no call; archive, already_archived success; create (OQ1) public and private, name_taken classified.
- Writability (test_incident_core_conversation_writable.py): open member True; archived False; not a member False; channel_not_found NOT_FOUND; ratelimited TRANSIENT with retry-after; conversation_is_writable on an incident with no conversation False without a call; on another system UNSUPPORTED.
- Errors (test_incident_core_conversation_errors.py): post to an archived channel (is_archived) and not_in_channel -> CONVERSATION_NOT_WRITABLE; an unknown Slack code and a non-Slack exception (network) -> logged permanent error, never raised (the reader's never-raise contract).
- Parity (test_incident_core_conversation_protocol_parity.py): both implement the Protocol; post/purpose/bookmark/invite/archive/is_writable observable results equal; another-system reference UNSUPPORTED in both.
- Reader: by reference (history, replies, started-at use vendor_id); GOOGLE reference -> () / None and no client call.
- Scribe: draft passes the record's conversation; record without conversation -> empty-transcript reply; summarize builds the reference; no channel -> unchanged error. Comms: _read_window gets incident.conversation.

## Domain-model evolution gate
No stored entity changes; no new reference type (MessageReference and ConversationReference exist). Cardinality: conversations per incident 0 (declare failed after the record, 145.7) / 1 (today) / many (doc-15 E7 workstreams, TASK-165.5: one per linked incident; E1 bindings may map several channels to one incident).
| Scenario | Holds because |
| --- | --- |
| Single-team outage (happy path) | command channel = incident.conversation; same reads and writes as today |
| Archived channel, status update (145.8) | is_writable False skips only the post; the record update succeeds (ADR two-part check) |
| Bot removed from a private channel | is_member False -> not writable; the write is skipped, never a crash |
| Coordinated incident, command in a workstream channel bound to the root (E1/E7, the case most likely to break) | transcript and writes take the record's stored reference (incident.conversation), not the command's channel; workstreams are their own incidents with their own references, so a per-reference port needs no change |
| Security / embargoed incident (private channel) | create(private=True) (OQ1); the adapter acts as the bot; visibility unchanged by the port |
| Incident with no conversation | conversation_is_writable False; transcript empty; no call |
| Second suite (Teams) | another system's reference -> UNSUPPORTED until a Teams adapter is selected by the reference's system |
Rejected: a port keyed on the channel name or "the incident's channel" (one-to-one); passing the command's channel to the reader (wrong once bindings map several channels to one incident); Slack blocks in the Protocol (vendor payload in core, TASK-135.1 rule); join inside is_writable (a check must not mutate).

## Assumptions and doubts (how verified)
- conversations.info returns is_member for the bot on public and private channels it can see; a private channel it left returns channel_not_found -> NOT_FOUND, treated as not writable by callers. Verify against the Slack API reference at implementation and pin with tests.
- Synchronous adapter like the reader and IncidentReport (both callers run it via the existing sync paths); async conversion is not in scope.
- Tenant: the adapter checks only the system; a (system, tenant) pair waits for an instance with several tenants (ADR, System selection).
- MessageReference.message_id carries the Slack ts.

## Blast radius and rollback
Production paths changed: /sre incident draft and summarize, and comms status-update drafts read transcripts by reference. A bug empties the transcript (draft or summary of nothing) or breaks those commands; declare, status, roles and archive are untouched (no legacy caller repointed). Caught by the scribe, comms and legacy_surface suites. One git revert. No terraform, IAM, SSM or env-name change: no deploy-checks. The port itself ships unused.

## Open questions (recommendation first)
- OQ1 create: add create(name, *, private) -> OperationResult[ConversationReference] here (recommended: 145.7 declare and 145.8 recreate both need it, two consumers per the ADR rule, and IncidentReport already has create_from_template; ~40 LOC; the ADR list gains "create"); alternative: 145.7 adds it to core. The canvas stays out (Slack-only; 145.7 decides).
- OQ2 error mapping: adapter-local mapping of is_archived, not_in_channel, channel_is_archived and name_taken, then classify_slack_error, and unknown codes become a permanent error instead of raising (recommended: never raises, like the reader); alternative: add the codes to integrations/slack settings lists (changes classification for oncall_sync and tenant verification).
- OQ3 invite takes vendor user ids (recommended: person resolution is TASK-83.4 / D33, the caller's job; declare already resolves Slack ids); alternative: a person type now (no person capability exists).
- OQ4 conversation_is_writable(conversations, incident) takes the record, and the scribe and comms readers pass incident.conversation (recommended: the record's stored reference survives E1 bindings and E7 workstreams); alternative: (conversations, reference) and pass the command's reference.
- OQ5 AC #3 "unsupported result": the reader keeps its never-raise, empty-value contract, so another system returns () / None with incident_transcript_system_unsupported (recommended; AC #3 reworded on approval); alternative: OperationResult returns, which changes every caller's handling.
- OQ6 summarize keeps working outside incident channels: it builds the reference without find_incident_for_conversation (recommended: AC #4, no visible change; 145.9 moves summarize into response and decides the command check there); alternative: add the lookup now (a channel that is not an incident would start refusing).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-05 (human): TASK-145.6.2 C3 approved; the report-link AC (old #4: no IncidentReportLinkLookup or scribe/adapters/slack.py; report from the record) moved to TASK-145.6.2 and was removed here; title and description narrowed.
<!-- SECTION:NOTES:END -->
