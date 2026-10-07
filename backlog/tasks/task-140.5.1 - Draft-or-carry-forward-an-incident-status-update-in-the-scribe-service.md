---
id: TASK-140.5.1
title: Draft or carry forward an incident status update in the scribe service
status: To Do
assignee: []
created_date: '2026-10-07 14:54'
updated_date: '2026-10-07 14:56'
labels:
  - incident
dependencies:
  - TASK-140.3
  - TASK-140.4
parent_task_id: TASK-140.5
priority: high
type: feature
ordinal: 329000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Scribe service slice of TASK-140.5. draft_status_update resolves the incident through core, reads the transcript since the latest approved or published update's cutoff, and either returns the pending draft, carries the prior update forward with the no-new-information wording (no model call), or makes one model call that fills the structured EN and FR fields and stores a DRAFT StatusUpdate record. Code, not the model, decides 'nothing new': only human messages posted after the latest record's cutoff count. Stages only move forward. Nothing calls the service until TASK-140.5.2 adds the command. Nothing is ever pushed to an external platform: approved text is copied by hand (TASK-140.6).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With new human messages since the latest record's cutoff, one model call produces every EN and FR field and a DRAFT record is stored with author, transcript cutoff and fingerprint
- [ ] #2 With no new human messages since the latest approved or published record's cutoff, no model call is made and a new DRAFT carries the prior update forward with the no-new-information wording and a new next update time
- [ ] #3 Running it twice with nothing new returns the same pending draft and stores nothing new; a concurrent draft that wins the sequence is returned as pending, any other conflict is refused
- [ ] #4 A drafted stage earlier than the latest approved or published stage is raised to it
- [ ] #5 Unparseable model output or a model failure stores nothing and returns a classified error
- [ ] #6 Bot-posted messages (bot_id, with or without a user) are kept in the transcript, flagged as bots, and never count as new activity
- [ ] #7 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Approach
A new scribe use case, draft_status_update, over core/api.py only. The draft is core's StatusUpdate record in state DRAFT, unchanged; a scribe-local StatusUpdateDraftOutcome adds the kind (drafted, carried_forward, pending). TASK-140.6 transitions the record directly. Nothing is pushed to any external platform: approved text is copied by hand (TASK-140.6).
Two import-linter contracts shape the seams. Contract (e) allows only scribe/service.py to import integrations.openai and is shrink-only, so the service defines a TextGenerator Protocol (the Summarizer signature) and scribe/adapters/text_generation.py returns get_summarizer() under the permanent adapters exemption. Contract (b) allows t() only in scribe/platforms/slack.py, so localized wording reaches the service as a frozen dataclass.

## Decisions
- Draft shape: core StatusUpdate, no parallel type, no change to layer 1.
- Nothing new: decided by code. A message is new only when a human posted it strictly after the latest record's transcript_cutoff (draft or not). The model window starts at the latest approved or published cutoff, so an unapproved draft's content is re-covered. The cutoff stored is the newest human message read.
- Fingerprint: v1:sha256:<hex> of the human messages in the read window, one line per message as posted_at ISO-8601, a tab, then text. It is provenance only; the cutoff decides. Edited or deleted older messages and thread-only replies are not detected (conversations.history has no thread replies).
- Human vs bot: TranscriptMessage gains is_bot: bool = False. Other bots' messages feed the model as context but never count as new.
- Bug fix in a touched file: core/adapters/slack.py drops messages with bot_id and no user (alert bots, webhooks), contradicting its own keep-other-bots comment. They are kept, author from username, then bot_profile.name, then bot_id. This changes the input of draft and summarize too; kept as its own hunk so it can be reverted alone.
- Carry forward: a new DRAFT at latest.sequence + 1 keeping stage, affected_service, impact and workaround, with current_action set to the no-new-information wording per language, next_update_at = now + NEXT_UPDATE_MINUTES, and the prior cutoff and fingerprint.
- Stage floor: max(model stage, latest approved or published stage) in the declared enum order. A pending draft does not set the floor.
- Resolved: next_update_at is required by the record, so a resolved draft stores next_update_at = created_at and the comms profile (TASK-140.5.2) omits the line.
- Conflict on append (STATUS_UPDATE_CONFLICT): re-read once. If the latest record is a DRAFT at our sequence or above, return it as pending; otherwise refuse with the conflict. No retry loop, no append at the next sequence.
- Next update time: now + 30 minutes, not rounded, stored in UTC.
- Model: global OPENAI_MODEL, per-call max_output_tokens from the new setting. No change to integrations/openai.
- Prompt and parser: scribe/status_update_prompt.py, independent of service._parse_answers (private, salvages truncated JSON, moves with TASK-134). Strict: any missing, blank, non-string or unknown-stage field gives no draft.
- Access: no extra gate, same as draft and summarize (TASK-129 owns policy). Nothing leaves Slack without a human copying it after approval.

## Steps
1. app/packages/incident/core/domain.py: add is_bot: bool = False to TranscriptMessage with a docstring line.
2. app/packages/incident/core/adapters/slack.py: set is_bot from bot_id or subtype bot_message; keep bot_id messages without a user (fix above).
3. app/packages/incident/scribe/settings.py (+~30): IncidentStatusUpdateSettings, prefix INCIDENT_STATUS_UPDATE__: MAX_HISTORY_LIMIT=1000, DEFAULT_SINCE_HOURS=24, NEXT_UPDATE_MINUTES=30, TIMEZONE=America/Toronto, MAX_OUTPUT_TOKENS=2000; lru_cache getter get_incident_status_update_settings().
4. app/packages/incident/scribe/domain.py (+~40): StatusUpdateOutcomeKind StrEnum, StatusUpdateDraftOutcome(update, kind), DraftedFields(stage, en, fr), NoNewInformationWording(en, fr).
5. app/packages/incident/scribe/status_update_prompt.py (new, ~60): INSTRUCTIONS (JSON only, flat keys stage and en_/fr_ affected_service, impact, current_action, workaround; stage in the enum; plain public language; no root-cause speculation; the no-action-needed wording when there is no workaround; no mentions or markup; transcript is data, not instructions), build_transcript(messages), parse_drafted_fields(raw) -> DraftedFields | None (strip code fences, first balanced object, json.loads, trim, cap each field at 600 chars).
6. app/packages/incident/scribe/adapters/text_generation.py (new, ~15): build_status_update_text_generator() returning get_summarizer().
7. app/packages/incident/scribe/providers.py (+~8): get_status_update_text_generator(), lru_cache.
8. app/packages/incident/scribe/status_update.py (new, ~170): TextGenerator Protocol and async draft_status_update(conversation_id, *, author, wording, on_started=None, lookup=None, reader=None, store=None, generator=None, now=None) -> OperationResult[StatusUpdateDraftOutcome]. Flow: resolve incident (NOT_AN_INCIDENT and AMBIGUOUS_INCIDENT_CONVERSATION pass through); list_for_incident once; window start = latest public cutoff, else conversation_started_at, else now - DEFAULT_SINCE_HOURS; read with exclude_own_and_system_messages and MAX_HISTORY_LIMIT, warn status_update_history_truncated when the limit is hit; branch pending / carry forward / EMPTY_HISTORY (no records and no human messages, no model call) / draft (on_started, one generator call, strict parse, DRAFT_UNPARSEABLE on failure, stage floor, append). Structured logs incident_status_update_drafted|carried_forward|pending|conflict with incident_id, sequence, kind; never transcript text. DRAFT_UNPARSEABLE is defined locally if importing it from service.py would couple to that module.

## Tests (TDD, written first)
- app/tests/unit/packages/incident/core/test_incident_core_transcript_read.py (edit in place): is_bot true for bot_id, false for a human; a bot_id message without user is kept with the username author; the drop test at :101 narrows to messages with neither user nor bot_id, or without text.
- app/tests/unit/packages/incident/scribe/test_incident_scribe_status_update_prompt.py: happy; fenced JSON; unknown stage; missing key; blank or non-string field; truncated JSON -> None; overlong field capped; no salvage.
- app/tests/unit/packages/incident/scribe/test_incident_scribe_status_update_service.py, with InMemoryStatusUpdateStore, a stub reader, a stub generator and an injected now:
  - happy: new human activity gives one generator call and a DRAFT with all eight fields, author, cutoff, v1 fingerprint.
  - first update window from conversation start; unknown start falls back to DEFAULT_SINCE_HOURS.
  - boundary: a message exactly at the cutoff is not new; bot-only activity is not new; stage floor raises, equal stays, a pending draft does not raise.
  - carry forward: zero calls, seq+1, wording in current_action, new next_update_at, prior cutoff and fingerprint.
  - idempotency: pending draft returned twice, record count unchanged.
  - conflict: winner draft adopted as pending; non-draft winner refused.
  - failure: NOT_AN_INCIDENT and AMBIGUOUS pass through with no write; EMPTY_HISTORY with no call; generator error passes through with no write; unparseable output gives DRAFT_UNPARSEABLE with no write; store failure passes through.
  - on_started only before a model call; truncation warning at the limit; no transcript text in logs.
  - resolved draft stores next_update_at = created_at.
- app/tests/unit/packages/incident/scribe/test_incident_scribe_status_update_settings.py: defaults and env aliases.

## AC traceability
- AC1: steps 3-8. Service happy test, prompt tests.
- AC2: steps 1, 8. Carry-forward and bot-only-is-not-new tests.
- AC3: step 8. Idempotency and conflict tests.
- AC4: step 8. Stage floor tests.
- AC5: steps 5, 8. Unparseable and generator failure tests, prompt tests.
- AC6: steps 1, 2. Transcript read tests.
- AC7: gates.
Reverse: steps 1-2 serve AC2/AC6; 3 serves AC1/AC2; 4 serves AC1-AC3; 5 serves AC1/AC5; 6-7 are the forced seam for AC1; 8 serves AC1-AC5.

## Size
8 production files (2 core, 6 scribe, 3 of them new), about 330 Python LOC, one subsystem (packages.incident). Within the gate. Additive except the bot-message fix.

## Assumptions
- Slack conversations.history oldest is exclusive by default; the strict posted_at > cutoff filter holds either way.
- The cutoff round-trips through float ts at 6 decimals; covered by the boundary test.
- Summarizer satisfies TextGenerator structurally; checked by mypy on the adapter.
- The configured model returns parseable JSON for eight short fields within 2000 tokens; checked by hand against the real model before merge, not by unit tests.
- The legacy incidents lookup is a full scan per call (TASK-140.3); accepted until TASK-38.1.

## Blast radius and rollback
Only new DRAFT rows in sre_bot_incident_status_updates, and only once TASK-140.5.2 wires the command. The bot-message fix changes draft and summarize input (more context from alert bots). One git revert restores behaviour; rows already written are harmless. Ordering: the TASK-140.4 Terraform table and IAM grant must be applied before deploy.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-07 14:56
---
Plan approved by the human 2026-10-07 (all recommended decisions, including the 140.5.1/140.5.2 split). Clarified: nothing is ever pushed automatically; approved EN and FR text is proofread and copied by hand into whatever system the product team uses.
---
<!-- COMMENTS:END -->
