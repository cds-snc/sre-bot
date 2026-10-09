---
id: TASK-144.3
title: >-
  Start, save and AI-fill a status update draft in the scribe service, with the
  draft's origin and the AI availability predicate
status: To Do
assignee: []
created_date: '2026-10-09 12:53'
updated_date: '2026-10-09 13:01'
labels:
  - incident
  - features
dependencies:
  - TASK-144.2
references:
  - decisions/incident-management.md
  - decisions/type-model-boundaries.md
parent_task_id: TASK-144
priority: high
type: feature
ordinal: 347000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 3 of TASK-144 (service and store, no modal change). Builds on what #1566 merged in packages/incident/scribe/status_update.py: draft_status_update(manual=True) stores a prefilled draft without a model call, _prefill_fields, _holds, UnavailableTextGenerator.

THIS SLICE
- Origin: StatusUpdateOrigin (HAND, MODEL, MODEL_INSTRUCTED, CARRIED_FORWARD) in packages/incident/core/domain.py; StatusUpdate.origin: StatusUpdateOrigin | None = None (None for records written before origins existed). The DynamoDB adapter writes the attribute when set and reads it when present; no table change. draft_status_update sets MODEL, CARRIED_FORWARD or HAND (manual) on every record it appends; redraft sets MODEL_INSTRUCTED.
- Save: save_status_update_draft(conversation_id, sequence, edit, author) appends the next DRAFT record with the responder's stage and fields, origin HAND, cutoff and fingerprint copied from the pending draft at sequence. Partial fields are accepted (a draft may be unfinished); the stage floor stays at approval. A stale sequence or a non-draft latest is STATUS_UPDATE_CONFLICT; an identical repeat by the same author returns the stored draft.
- AI fill: generate_status_update_draft(conversation_id, sequence, current, author, instructions="", security_confirmed=False) is redraft_status_update generalised: blank instructions mean "draft from the conversation". With no new human messages since the latest approved update's cutoff and blank instructions it makes no model call and returns the current fields with the carried-forward wording (CARRIED_FORWARD); otherwise the security gate runs, then one model call fills the fields (MODEL or MODEL_INSTRUCTED). It returns StatusUpdateDraftOutcome. redraft_status_update becomes a thin wrapper that keeps today's blank-instructions refusal and return type, so the live redraft handler does not change in this slice; TASK-144.5 switches the handler and deletes the wrapper.
- Availability: text_generation_available() in status_update.py, true when the provider builds a working TextGenerator (false when it returns UnavailableTextGenerator). Pure wiring, no network.

Behaviour visible to users is unchanged: no handler calls the new functions yet.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 StatusUpdate has origin (HAND, MODEL, MODEL_INSTRUCTED, CARRIED_FORWARD or None); the DynamoDB adapter round-trips it and reads records without the attribute as None; the in-memory fake passes the same tests; draft_status_update and redraft_status_update set it on every record they append
- [ ] #2 save_status_update_draft appends the next DRAFT record with the edit, origin HAND and the pending draft's cutoff and fingerprint; partial fields are accepted; a stale sequence or non-draft latest is STATUS_UPDATE_CONFLICT; an identical repeat returns the stored draft without a write
- [ ] #3 generate_status_update_draft with blank instructions and no new human messages makes no model call and returns the carried-forward fields; with new messages it runs the security gate, then one model call; instructions give MODEL_INSTRUCTED; a failed or unparseable model call returns its error and leaves the pending draft as latest
- [ ] #4 text_generation_available() is False when the OpenAI settings do not load and True otherwise, without any network call; redraft_status_update keeps its signature and behaviour
- [ ] #5 No entry point changes; every existing scribe and core test passes; ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded at main af6a316e (2026-10-09); module paths assume TASK-144.1 has merged (handlers in `entrypoints/slack.py`, views in `entrypoints/slack_views.py`). Service and store only; no handler changes, no user-visible change.

## Discovered state

- `app/packages/incident/core/domain.py`: `StatusUpdateState`, `StatusUpdateText`, `StatusUpdate` (fields through `published_by`, defaults after `created_at`); `__post_init__` validates id, sequence and timezone-aware times. `core/api.py` re-exports the domain types and the `StatusUpdateStore` Protocol (`append`, `latest`, `list_for_incident`, `transition`); `transition` only allows DRAFT->APPROVED, APPROVED->PUBLISHED, PUBLISHED->APPROVED, so a changed draft is always a new appended DRAFT record, as `redraft_status_update` already does.
- `core/adapters/status_updates.py`: `_to_item` (157) writes PK/SK, sequence, state, stage, en, fr, next_update_at, author, transcript_cutoff, transcript_fingerprint, created_at and the optional approver/approved_at/published_at/published_by; `_from_item` (199) reads them back with `if "x" in item`. `core/adapters/in_memory.py` stores dataclasses, nothing to change.
- `app/packages/incident/scribe/status_update.py` (after #1566): `get_status_update_overview`, `get_pending_status_update`, `draft_status_update(..., manual=False)` with `_prefill_fields`, `_holds` and the MANUAL path (lines 143-258), `redraft_status_update` (261-370: blank instructions refused with `STATUS_UPDATE_INSTRUCTIONS_INVALID`; latest must be the DRAFT at `sequence`; window read; `_security_gate`; one `_generate_fields` call with `build_redraft_input(current, transcript)` and `build_redraft_instructions(guidance)`; `_draft_record(previous=latest)`; `store.append`), `_generate_fields`, `_security_gate`, `_read_window`, `_carry_forward`, `_draft_record`, `_append` (conflict: one re-read, a winning draft is returned as PENDING), `next_update_at_for`, `_fingerprint`.
- `scribe/domain.py`: `StatusUpdateOutcomeKind` (DRAFTED, CARRIED_FORWARD, PENDING, MANUAL), `StatusUpdateDraftOutcome`, `DraftedFields`, `NoNewInformationWording`, `StatusUpdateEdit`, `StatusUpdateOverview`.
- `scribe/adapters/text_generation.py` (after #1566): `UnavailableTextGenerator` answering `TEXT_GENERATION_UNAVAILABLE`; `build_status_update_text_generator()` returns it when `get_summarizer()` raises `ValidationError`. `scribe/providers.py:30` `get_status_update_text_generator()`.
- `contracts/operations/codes.py`: `TEXT_GENERATION_UNAVAILABLE`, `STATUS_UPDATE_CONFLICT`, `STATUS_UPDATE_INSTRUCTIONS_INVALID`, `SECURITY_CONFIRMATION_REQUIRED`, `EMPTY_HISTORY`, and the scribe-local `DRAFT_UNPARSEABLE_CODE`.
- Tests today: `tests/unit/packages/incident/core/test_incident_core_status_update_{record,store,fake}.py`, `test_incident_core_api_surface.py`; `tests/unit/packages/incident/scribe/test_incident_scribe_status_update_{service,pending,security_gate,redraft,redraft_prompt}.py`, `test_incident_scribe_text_generation_adapter.py`.

## Steps

1. `core/domain.py`: add `class StatusUpdateOrigin(StrEnum)` with `HAND = "hand"`, `MODEL = "model"`, `MODEL_INSTRUCTED = "model_instructed"`, `CARRIED_FORWARD = "carried_forward"` and a docstring ("how a draft's text came to be; approval does not change it"). Add `origin: StatusUpdateOrigin | None = None` as the last `StatusUpdate` field, documented as `None` for records written before origins existed. `core/api.py`: import and expose `StatusUpdateOrigin` beside the other domain types.
2. `core/adapters/status_updates.py`: in `_to_item`, `if update.origin is not None: item["origin"] = {"S": update.origin.value}`; in `_from_item`, `origin=StatusUpdateOrigin(item["origin"]["S"]) if "origin" in item else None`. No key, index or Terraform change (a new non-key attribute).
3. `status_update.py`, existing paths: `_carry_forward` sets `origin=StatusUpdateOrigin.CARRIED_FORWARD`; `_draft_record` gains a required keyword `origin`; `draft_status_update` passes `HAND` on the manual path and `MODEL` on the generated path; `redraft_status_update` passes `MODEL_INSTRUCTED`.
4. `status_update.py`, new `save_status_update_draft(conversation_id, sequence, *, edit: StatusUpdateEdit, author: str, lookup=None, store=None, now=None) -> OperationResult[StatusUpdate]`: resolve the incident; `list_for_incident`; the latest must be the DRAFT at `sequence`, otherwise `STATUS_UPDATE_CONFLICT` with the existing "no longer the pending draft" message; if the latest already holds `edit`'s stage and fields with the same author, return it without a write (replay); otherwise append `replace(latest, sequence=latest.sequence + 1, stage=edit.stage, en=edit.en, fr=edit.fr, author=author, origin=HAND, created_at=now, next_update_at=next_update_at_for(edit.stage, settings, now) if edit.stage is not latest.stage else latest.next_update_at)`, keeping `transcript_cutoff` and `transcript_fingerprint`. No blank validation (a draft may be partial) and no stage floor (approval owns both). On an append conflict, one re-read: a DRAFT with a higher sequence is returned as success, anything else is the conflict (same shape as `_append`). Log `incident_status_update_saved` with sequence; never log the text.
5. `status_update.py`, new `generate_status_update_draft(conversation_id, sequence, *, current: StatusUpdateEdit, author: str, wording: NoNewInformationWording, instructions: str = "", security_confirmed: bool = False, on_started=None, lookup=None, reader=None, store=None, generator=None, security_reader=None, now=None) -> OperationResult[StatusUpdateDraftOutcome]`, built by moving the body of `redraft_status_update` and adding two branches:
   - `guidance = normalize_instructions(instructions)` may be empty.
   - after the window read, `new_from_people` = people's messages strictly after `last_public.transcript_cutoff` (all of them when there is no approved update). With no new messages and empty guidance: no security gate, no model call; `fields = DraftedFields(stage=current.stage, en=replace(current.en, current_action=wording.en), fr=replace(current.fr, current_action=wording.fr))`; append through `_draft_record(..., previous=latest, origin=CARRIED_FORWARD)` and return kind `CARRIED_FORWARD`. With no approved update, no people and empty guidance: `EMPTY_HISTORY`, as `draft_status_update` returns today.
   - otherwise `_security_gate`, `on_started`, one `_generate_fields` call: with guidance, `build_redraft_input(current, transcript)` and `build_redraft_instructions(guidance)` as today; without, `build_redraft_input(current, transcript)` and `INSTRUCTIONS` (the base prompt), so the typed fields are still the model's base. Origin `MODEL_INSTRUCTED` with guidance, `MODEL` without. Return kind `DRAFTED`. Failures as today: generator error passed through, `DRAFT_UNPARSEABLE`, conflicts; every failure leaves the previous draft as latest.
   - `redraft_status_update` becomes a wrapper: blank instructions still refuse with `STATUS_UPDATE_INSTRUCTIONS_INVALID` before any read; otherwise call `generate_status_update_draft(..., wording=<unused but required>)` and return `OperationResult.success(data=outcome.update)` or the failure. To keep its signature, the wrapper passes a wording built from empty strings (it is never applied because guidance is non-blank). The live redraft handler and its tests do not change. TASK-144.5 deletes the wrapper.
6. `status_update.py`, new `text_generation_available() -> bool`: `not isinstance(providers.get_status_update_text_generator(), UnavailableTextGenerator)`. Import `UnavailableTextGenerator` from `scribe.adapters.text_generation`? No: the service must not import adapters. Instead add `providers.text_generation_available()` in `scribe/providers.py` (providers may know adapter types) and have the service predicate call it. Pure wiring, no network.
7. Docstrings: module docstring of `status_update.py` gains the save and generate paths and the origin vocabulary; `StatusUpdateEdit` docstring becomes "the stage and fields a responder submits, saves or hands to the model as its base".

## AC traceability

| AC | Steps | Tests |
| --- | --- | --- |
| 1 | 1, 2, 3 | core: test_incident_core_status_update_record.py (origin accepted, default None), test_incident_core_status_update_store.py (round-trip with origin; an item without the attribute reads None), test_incident_core_status_update_fake.py (same cases), test_incident_core_api_surface.py (name exported); scribe: new test_incident_scribe_status_update_origin.py (draft -> MODEL, manual -> HAND, carry-forward -> CARRIED_FORWARD, redraft -> MODEL_INSTRUCTED) |
| 2 | 4 | new test_incident_scribe_status_update_save.py |
| 3 | 5 | new test_incident_scribe_status_update_generate.py; existing test_incident_scribe_status_update_redraft.py unchanged and green |
| 4 | 5, 6 | new test_incident_scribe_text_generation_availability.py; test_incident_scribe_status_update_redraft.py |
| 5 | all | gates; no change under `entrypoints/` (`git diff --stat`) |

## Test matrix

Save: happy path appends sequence+1 with HAND and the pending draft's cutoff and fingerprint; partial (blank) fields accepted; stage change recomputes next_update_at, same stage keeps it; stale sequence -> conflict, no write; latest APPROVED -> conflict; identical repeat by the same author -> stored draft, no write; append conflict with a newer draft -> that draft; store read error passed through; lookup refusal passed through.
Generate: no approved update, no people, blank instructions -> EMPTY_HISTORY, no model call; approved update, no new people, blank -> CARRIED_FORWARD with the wording in current_action, no model call, no security read; new people, blank -> one model call with the base prompt, MODEL; new people with instructions -> redraft prompt, MODEL_INSTRUCTED; no new people with instructions -> still one model call (instructions are a request); security YES/UNKNOWN unconfirmed -> SECURITY_CONFIRMATION_REQUIRED before any call; confirmed -> flag not read; unreadable flag -> refusal; unparseable answer -> DRAFT_UNPARSEABLE and latest unchanged; generator error passed through; stale sequence -> conflict. Fakes: in-memory store, a recording `TextGenerator` fake, a transcript reader fake returning fixed messages, a security reader fake (same style as test_incident_scribe_status_update_security_gate.py).
Availability: provider builds the real generator -> True; provider returns `UnavailableTextGenerator` -> False; no network (patch `get_summarizer`).

## Assumptions and doubts

- `build_redraft_instructions("")` behaviour is unknown; the plan sidesteps it by using `INSTRUCTIONS` when guidance is blank. Read `status_update_prompt.py` before coding; if the redraft prompt without guidance is a better base prompt for "fill from my fields", use it and record why.
- `get_status_update_text_generator` may be `lru_cache`d (providers.py:30); if so `text_generation_available()` is stable per process, which is what the modal needs. Verify.
- A new DynamoDB attribute needs no Terraform change; confirm `terraform/` defines only PK/SK attributes for `sre_bot_incident_status_updates` (`rg incident_status_updates terraform`).
- `StatusUpdateEdit` is reused as the save and generate input; if a reviewer prefers a distinct type, it is a rename.

## Size

Production: `core/domain.py` about 15 lines, `core/api.py` 2, `core/adapters/status_updates.py` 4, `scribe/status_update.py` about 170 (new functions plus the refactor), `scribe/providers.py` 8, `scribe/domain.py` docstrings. About 200 production lines across 6 files; tests about 500 lines across 6 new or extended files. Under the gate.

## Blast radius and rollback

New records carry `origin`; the previous code's `_from_item` ignores unknown attributes, so a rollback reads them. No handler calls the new functions, so a defect here is unreachable from Slack until TASK-144.4. Single `git revert`. No Terraform, no config.
<!-- SECTION:PLAN:END -->
