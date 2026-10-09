"""Draft an incident's public status update from its conversation.

Platform-neutral use case behind ``/sre incident status-update``
(decisions/incident-management.md, External status updates). It resolves the
incident through the core, reads the conversation since the latest approved
update, and returns a draft record in one of four ways:

- ``PENDING``: the latest record is a draft and no person has posted since its
  cutoff, so that draft is returned as is;
- ``CARRIED_FORWARD``: the latest record is approved and no person has posted
  since, so the prior update is carried forward with the no-new-information
  wording, without a model call;
- ``DRAFTED``: people have posted since, so one model call fills the fields;
- ``MANUAL``: people have posted since and the responder chose to write the
  update, or the model call failed, so the draft is the latest approved update
  (blank at the first stage when there is none) for the responder to edit.

A pending draft still equal to that prefill is a manual draft nobody wrote,
so Draft asks the model again over it rather than returning it as pending.

Code, not the model, decides that nothing is new: only messages posted by a
person strictly after the latest record's transcript cutoff count. Stages only
move forward from the latest approved or published stage.

``save_status_update_draft`` stores the responder's fields as the next draft
without reading the conversation. ``generate_status_update_draft`` fills the
pending draft with AI from the responder's fields: with nothing new and no
instructions it carries them forward by code, otherwise one model call over
the same window fills them. ``redraft_status_update`` is that call with
instructions required; the instructions steer the fields only.

Every appended draft records its origin: ``HAND`` (written or saved by a
responder, or a manual prefill), ``MODEL``, ``MODEL_INSTRUCTED`` (the model
followed a responder's instructions) or ``CARRIED_FORWARD``.
``text_generation_available`` says whether AI drafting can be offered.

This module imports only ``core.api`` from the core and no platform SDK.
"""

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from packages.incident.core.api import (
    IncidentLookup,
    IncidentSecurityFlag,
    IncidentSecurityReader,
    IncidentTranscriptReader,
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateStore,
    StatusUpdateText,
    TranscriptMessage,
    get_incident_lookup,
    get_incident_security_reader,
    get_incident_transcript_reader,
    get_status_update_store,
)
from packages.incident.scribe import providers
from packages.incident.scribe.domain import (
    DraftedFields,
    NoNewInformationWording,
    StatusUpdateDraftOutcome,
    StatusUpdateEdit,
    StatusUpdateOutcomeKind,
    StatusUpdateOverview,
)
from packages.incident.scribe.ports import TextGenerator
from packages.incident.scribe.settings import IncidentStatusUpdateSettings, get_incident_status_update_settings
from packages.incident.scribe.status_update_prompt import (
    INSTRUCTIONS,
    build_redraft_input,
    build_redraft_instructions,
    build_transcript,
    normalize_instructions,
    parse_drafted_fields,
)

logger = structlog.get_logger()

DRAFT_UNPARSEABLE_CODE = "DRAFT_UNPARSEABLE"

_STAGE_ORDER = tuple(StatusUpdateStage)


def get_status_update_overview(
    conversation_id: str,
    *,
    lookup: IncidentLookup | None = None,
    store: StatusUpdateStore | None = None,
) -> OperationResult[StatusUpdateOverview]:
    """Return the incident's pending draft and approved updates, without drafting anything.

    Args:
        conversation_id: The incident conversation the command ran in.
        lookup: Resolves the conversation to its incident; core's by default.
        store: Holds the incident's status updates; core's by default.

    Returns:
        Success with the latest record as ``pending`` when it is a draft, and
        every approved or published record newest first. Otherwise the lookup's
        refusal (``NOT_AN_INCIDENT``, ``AMBIGUOUS_INCIDENT_CONVERSATION``) or
        the store's classified error.
    """
    lookup = lookup or get_incident_lookup()
    incident = lookup.find_incident_for_conversation(conversation_id)
    if not incident.is_success or incident.data is None:
        return _failure(incident)

    store = store or get_status_update_store()
    listed = store.list_for_incident(incident.data)
    if not listed.is_success or listed.data is None:
        return _failure(listed)
    latest = listed.data[0] if listed.data else None
    pending = latest if latest is not None and latest.state is StatusUpdateState.DRAFT else None
    approved = tuple(update for update in listed.data if update.state is not StatusUpdateState.DRAFT)
    return OperationResult.success(data=StatusUpdateOverview(pending=pending, approved=approved))


def get_pending_status_update(
    conversation_id: str,
    *,
    lookup: IncidentLookup | None = None,
    store: StatusUpdateStore | None = None,
) -> OperationResult[StatusUpdate | None]:
    """Return the incident's pending draft, without drafting anything.

    Args:
        conversation_id: The incident conversation the command ran in.
        lookup: Resolves the conversation to its incident; core's by default.
        store: Holds the incident's status updates; core's by default.

    Returns:
        Success with the latest record when it is a draft, or ``None`` when
        there is no record or the latest is not a draft. Otherwise the error
        of ``get_status_update_overview``.
    """
    overview = get_status_update_overview(conversation_id, lookup=lookup, store=store)
    if not overview.is_success or overview.data is None:
        return _failure(overview)
    return OperationResult.success(data=overview.data.pending)


async def draft_status_update(
    conversation_id: str,
    *,
    author: str,
    wording: NoNewInformationWording,
    on_started: Callable[[], None] | None = None,
    security_confirmed: bool = False,
    manual: bool = False,
    lookup: IncidentLookup | None = None,
    reader: IncidentTranscriptReader | None = None,
    store: StatusUpdateStore | None = None,
    generator: TextGenerator | None = None,
    security_reader: IncidentSecurityReader | None = None,
    now: datetime | None = None,
) -> OperationResult[StatusUpdateDraftOutcome]:
    """Return the incident's pending, carried-forward, drafted or manual status update.

    Args:
        conversation_id: The incident conversation the command ran in.
        author: Platform user id of the responder asking for the draft.
        wording: The no-new-information wording of a carried-forward update.
        on_started: Called once just before the model call, after the security
            gate, so the caller can say drafting has begun; never called when no
            model call is made.
        security_confirmed: The responder confirmed drafting for a security or
            unknown-flag incident; the flag is then not read.
        manual: The responder writes the update: no model call and no
            security gate, and a pending draft is always returned as is.
        lookup: Resolves the conversation to its incident; core's by default.
        reader: Reads the conversation; core's by default.
        store: Holds the incident's status updates; core's by default.
        generator: Drafts the fields; the scribe provider's by default.
        security_reader: Reads the incident's security flag; core's by default.
        now: The current time; injected in tests.

    Returns:
        Success with the draft and how it was produced; a failed or unusable
        model call is a ``MANUAL`` draft, never an error. Otherwise the lookup's
        refusal (``NOT_AN_INCIDENT``, ``AMBIGUOUS_INCIDENT_CONVERSATION``), the
        store's classified error, ``EMPTY_HISTORY`` when there is no update yet
        and no person has posted, or
        ``STATUS_UPDATE_CONFLICT`` when another writer took the sequence with
        something other than a draft, or ``SECURITY_CONFIRMATION_REQUIRED`` when
        a model call is needed, the incident is or may be a security incident
        (or its flag cannot be read) and ``security_confirmed`` is false.
    """
    settings = get_incident_status_update_settings()
    now = now or datetime.now(UTC)
    lookup = lookup or get_incident_lookup()
    log = logger.bind(operation="draft_status_update", conversation_id=conversation_id)

    incident = lookup.find_incident_for_conversation(conversation_id)
    if not incident.is_success or incident.data is None:
        return _failure(incident)
    incident_id = incident.data
    log = log.bind(incident_id=incident_id)

    store = store or get_status_update_store()
    listed = store.list_for_incident(incident_id)
    if not listed.is_success or listed.data is None:
        return _failure(listed)
    records = listed.data
    latest = records[0] if records else None
    last_public = next((record for record in records if record.state is not StatusUpdateState.DRAFT), None)

    reader = reader or get_incident_transcript_reader()
    messages = _read_window(reader, conversation_id, last_public, settings, now, log)
    people = [message for message in messages if not message.is_bot and message.posted_at is not None]
    new_from_people = [message for message in people if latest is None or _posted_at(message) > latest.transcript_cutoff]
    prefill = _prefill_fields(last_public)
    # With new activity a fresh draft is due anyway, so only an otherwise-pending draft can be abandoned.
    abandoned = latest if not new_from_people and not manual and latest is not None and _holds(latest, prefill) else None

    if not new_from_people and abandoned is None:
        if latest is None:
            log.info("incident_status_update_empty_history")
            return OperationResult.permanent_error(
                message="No conversation from people to draft a status update from",
                error_code=ErrorCode.EMPTY_HISTORY,
            )
        if latest.state is StatusUpdateState.DRAFT:
            log.info("incident_status_update_pending", sequence=latest.sequence)
            return OperationResult.success(data=StatusUpdateDraftOutcome(update=latest, kind=StatusUpdateOutcomeKind.PENDING))
        carried = _carry_forward(latest, author=author, wording=wording, settings=settings, now=now)
        return _append(store, carried, StatusUpdateOutcomeKind.CARRIED_FORWARD, log)

    def record(fields: DraftedFields, origin: StatusUpdateOrigin) -> StatusUpdate:
        return _draft_record(
            incident_id,
            sequence=latest.sequence + 1 if latest else 1,
            fields=fields,
            floor=last_public.stage if last_public else None,
            people=people,
            author=author,
            settings=settings,
            now=now,
            previous=latest,
            origin=origin,
        )

    if manual:
        return _append(store, record(prefill, StatusUpdateOrigin.HAND), StatusUpdateOutcomeKind.MANUAL, log)

    refusal = _security_gate(incident_id, security_confirmed, security_reader, log)
    if refusal is not None:
        return refusal

    if on_started is not None:
        on_started()
    generated = await _generate_fields(generator or _default_generator(), build_transcript(messages), INSTRUCTIONS, settings, log)
    if generated.is_success and generated.data is not None:
        return _append(store, record(generated.data, StatusUpdateOrigin.MODEL), StatusUpdateOutcomeKind.DRAFTED, log)

    log.info("incident_status_update_manual_fallback", error_code=generated.error_code, retried=abandoned is not None)
    if abandoned is not None:
        return OperationResult.success(data=StatusUpdateDraftOutcome(update=abandoned, kind=StatusUpdateOutcomeKind.MANUAL))
    return _append(store, record(prefill, StatusUpdateOrigin.HAND), StatusUpdateOutcomeKind.MANUAL, log)


def save_status_update_draft(
    conversation_id: str,
    sequence: int,
    *,
    edit: StatusUpdateEdit,
    author: str,
    lookup: IncidentLookup | None = None,
    store: StatusUpdateStore | None = None,
    now: datetime | None = None,
) -> OperationResult[StatusUpdate]:
    """Store the responder's stage and fields as the next draft, written by hand.

    A draft may be unfinished, so blank fields are accepted and no stage floor
    applies; approval checks both. Cutoff and fingerprint stay the pending
    draft's, since saving reads no conversation.

    Args:
        conversation_id: The incident conversation the form was opened from.
        sequence: The pending draft's sequence the responder is editing.
        edit: The responder's stage and both languages' fields.
        author: Platform user id of the saving responder.
        lookup: Resolves the conversation to its incident; core's by default.
        store: Holds the incident's status updates; core's by default.
        now: The current time; injected in tests.

    Returns:
        Success with the stored draft: the new record (origin ``HAND``), the
        latest draft unchanged when it already holds ``edit`` by ``author``
        (a repeated save), or another writer's newer draft that took the
        sequence. Otherwise the lookup's refusal, the store's classified error,
        or ``STATUS_UPDATE_CONFLICT`` when the latest record is not the draft
        at ``sequence``.
    """
    settings = get_incident_status_update_settings()
    now = now or datetime.now(UTC)
    lookup = lookup or get_incident_lookup()
    log = logger.bind(operation="save_status_update_draft", conversation_id=conversation_id, sequence=sequence)

    incident = lookup.find_incident_for_conversation(conversation_id)
    if not incident.is_success or incident.data is None:
        return _failure(incident)
    log = log.bind(incident_id=incident.data)

    store = store or get_status_update_store()
    listed = store.list_for_incident(incident.data)
    if not listed.is_success or listed.data is None:
        return _failure(listed)
    latest = listed.data[0] if listed.data else None
    edited = DraftedFields(stage=edit.stage, en=edit.en, fr=edit.fr)
    if latest is not None and latest.sequence >= sequence and latest.author == author and _holds(latest, edited):
        log.info("incident_status_update_save_replayed", saved_sequence=latest.sequence)
        return OperationResult.success(data=latest)
    if latest is None or not _is_pending(latest, sequence):
        return _stale(log)

    saved = replace(
        latest,
        sequence=latest.sequence + 1,
        stage=edit.stage,
        en=edit.en,
        fr=edit.fr,
        next_update_at=latest.next_update_at if edit.stage is latest.stage else next_update_at_for(edit.stage, settings, now),
        author=author,
        created_at=now,
        origin=StatusUpdateOrigin.HAND,
    )
    appended = store.append(saved)
    if appended.is_success:
        log.info("incident_status_update_saved", sequence=saved.sequence)
        return OperationResult.success(data=saved)
    if appended.error_code != ErrorCode.STATUS_UPDATE_CONFLICT:
        log.warning("incident_status_update_save_store_failed", status=appended.status, error_code=appended.error_code)
        return _failure(appended)

    # One re-read, no retry loop: a winning draft is what the responder would see on reopening.
    winner = store.latest(saved.incident_id).data
    if winner is not None and winner.state is StatusUpdateState.DRAFT and winner.sequence >= saved.sequence:
        log.info("incident_status_update_save_superseded", winner_sequence=winner.sequence)
        return OperationResult.success(data=winner)
    log.warning("incident_status_update_conflict", sequence=saved.sequence)
    return _failure(appended)


async def generate_status_update_draft(
    conversation_id: str,
    sequence: int,
    *,
    current: StatusUpdateEdit,
    author: str,
    wording: NoNewInformationWording,
    instructions: str = "",
    security_confirmed: bool = False,
    on_started: Callable[[], None] | None = None,
    lookup: IncidentLookup | None = None,
    reader: IncidentTranscriptReader | None = None,
    store: StatusUpdateStore | None = None,
    generator: TextGenerator | None = None,
    security_reader: IncidentSecurityReader | None = None,
    now: datetime | None = None,
) -> OperationResult[StatusUpdateDraftOutcome]:
    """Fill the pending draft with AI from the responder's fields and store it as the next draft.

    Blank instructions mean "draft from the conversation". When no person has
    posted since the latest approved update and there are no instructions,
    code carries the responder's fields forward with the no-new-information
    wording, with no security read and no model call. Otherwise one model call
    fills the fields, with the responder's fields as its base.

    Args:
        conversation_id: The incident conversation the form was opened from.
        sequence: The pending draft's sequence the responder is looking at.
        current: The responder's current stage and fields, the model's base.
        author: Platform user id of the responder asking for the fill.
        wording: The no-new-information wording of a carried-forward update.
        instructions: The responder's guidance, trimmed and capped; may be blank.
        security_confirmed: The responder confirmed sending a security or
            unknown-flag incident to the model; the flag is then not read.
        on_started: Called once just before the model call.
        lookup: Resolves the conversation to its incident; core's by default.
        reader: Reads the conversation; core's by default.
        store: Holds the incident's status updates; core's by default.
        generator: Fills the fields; the scribe provider's by default.
        security_reader: Reads the incident's security flag; core's by default.
        now: The current time; injected in tests.

    Returns:
        Success with the new draft, ``CARRIED_FORWARD`` (origin
        ``CARRIED_FORWARD``) or ``DRAFTED`` (origin ``MODEL``, or
        ``MODEL_INSTRUCTED`` with instructions). Otherwise the lookup's refusal,
        the store's or the generator's classified error, ``EMPTY_HISTORY`` with
        no approved update, no person's message and no instructions,
        ``STATUS_UPDATE_CONFLICT`` when the latest record is not the draft at
        ``sequence`` or another writer took the next sequence,
        ``SECURITY_CONFIRMATION_REQUIRED``, or ``DRAFT_UNPARSEABLE``. Every
        failure leaves the previous draft as the latest.
    """
    settings = get_incident_status_update_settings()
    now = now or datetime.now(UTC)
    guidance = normalize_instructions(instructions)
    lookup = lookup or get_incident_lookup()
    log = logger.bind(
        operation="generate_status_update_draft",
        conversation_id=conversation_id,
        sequence=sequence,
        instructions_length=len(guidance),
    )

    incident = lookup.find_incident_for_conversation(conversation_id)
    if not incident.is_success or incident.data is None:
        return _failure(incident)
    incident_id = incident.data
    log = log.bind(incident_id=incident_id)

    store = store or get_status_update_store()
    listed = store.list_for_incident(incident_id)
    if not listed.is_success or listed.data is None:
        return _failure(listed)
    records = listed.data
    latest = records[0] if records else None
    if latest is None or not _is_pending(latest, sequence):
        return _stale(log)
    last_public = next((record for record in records if record.state is not StatusUpdateState.DRAFT), None)

    messages = _read_window(reader or get_incident_transcript_reader(), conversation_id, last_public, settings, now, log)
    people = [message for message in messages if not message.is_bot and message.posted_at is not None]
    new_from_people = [
        message for message in people if last_public is None or _posted_at(message) > last_public.transcript_cutoff
    ]

    def record(fields: DraftedFields, origin: StatusUpdateOrigin, read: Sequence[TranscriptMessage]) -> StatusUpdate:
        return _draft_record(
            incident_id,
            sequence=latest.sequence + 1,
            fields=fields,
            floor=last_public.stage if last_public else None,
            people=read,
            author=author,
            settings=settings,
            now=now,
            previous=latest,
            origin=origin,
        )

    if not new_from_people and not guidance:
        if last_public is None:
            log.info("incident_status_update_empty_history")
            return OperationResult.permanent_error(
                message="No conversation from people to draft a status update from",
                error_code=ErrorCode.EMPTY_HISTORY,
            )
        carried = DraftedFields(
            stage=current.stage,
            en=replace(current.en, current_action=wording.en),
            fr=replace(current.fr, current_action=wording.fr),
        )
        return _append_new(
            store, record(carried, StatusUpdateOrigin.CARRIED_FORWARD, ()), StatusUpdateOutcomeKind.CARRIED_FORWARD, log
        )

    refusal = _security_gate(incident_id, security_confirmed, security_reader, log)
    if refusal is not None:
        return refusal

    if on_started is not None:
        on_started()
    generated = await _generate_fields(
        generator or _default_generator(),
        build_redraft_input(current, build_transcript(messages)),
        build_redraft_instructions(guidance) if guidance else INSTRUCTIONS,
        settings,
        log,
    )
    if not generated.is_success or generated.data is None:
        return _failure(generated)
    origin = StatusUpdateOrigin.MODEL_INSTRUCTED if guidance else StatusUpdateOrigin.MODEL
    return _append_new(store, record(generated.data, origin, people), StatusUpdateOutcomeKind.DRAFTED, log)


async def redraft_status_update(
    conversation_id: str,
    sequence: int,
    *,
    instructions: str,
    current: StatusUpdateEdit,
    author: str,
    security_confirmed: bool = False,
    on_started: Callable[[], None] | None = None,
    lookup: IncidentLookup | None = None,
    reader: IncidentTranscriptReader | None = None,
    store: StatusUpdateStore | None = None,
    generator: TextGenerator | None = None,
    security_reader: IncidentSecurityReader | None = None,
    now: datetime | None = None,
) -> OperationResult[StatusUpdate]:
    """Redraft the pending draft from the reviewer's instructions and store it as the next draft.

    ``generate_status_update_draft`` with instructions required, for the
    review modal's Redraft button.

    Args:
        conversation_id: The incident conversation the review modal was opened from.
        sequence: The pending draft's sequence the reviewer is looking at.
        instructions: The reviewer's guidance; trimmed and capped before use.
        current: The reviewer's current stage and fields, the model's base.
        author: Platform user id of the redrafting responder.
        security_confirmed: The responder confirmed sending a security or
            unknown-flag incident to the model; the flag is then not read.
        on_started: Called once just before the model call.
        lookup: Resolves the conversation to its incident; core's by default.
        reader: Reads the conversation; core's by default.
        store: Holds the incident's status updates; core's by default.
        generator: Redrafts the fields; the scribe provider's by default.
        security_reader: Reads the incident's security flag; core's by default.
        now: The current time; injected in tests.

    Returns:
        Success with the new draft (origin ``MODEL_INSTRUCTED``). Otherwise
        ``STATUS_UPDATE_INSTRUCTIONS_INVALID`` for blank instructions (nothing
        is read), or the error of ``generate_status_update_draft``.
    """
    if not normalize_instructions(instructions):
        logger.info(
            "incident_status_update_redraft_blank",
            operation="redraft_status_update",
            conversation_id=conversation_id,
            sequence=sequence,
            error_code=ErrorCode.STATUS_UPDATE_INSTRUCTIONS_INVALID,
        )
        return OperationResult.permanent_error(
            message="Redraft instructions are blank",
            error_code=ErrorCode.STATUS_UPDATE_INSTRUCTIONS_INVALID,
        )
    generated = await generate_status_update_draft(
        conversation_id,
        sequence,
        current=current,
        author=author,
        # Never applied: non-blank instructions always reach the model.
        wording=NoNewInformationWording(en="", fr=""),
        instructions=instructions,
        security_confirmed=security_confirmed,
        on_started=on_started,
        lookup=lookup,
        reader=reader,
        store=store,
        generator=generator,
        security_reader=security_reader,
        now=now,
    )
    if not generated.is_success or generated.data is None:
        return _failure(generated)
    return OperationResult.success(data=generated.data.update)


def text_generation_available() -> bool:
    """Whether AI drafting can be offered: the text generator is configured. No network call."""
    return providers.text_generation_available()


async def _generate_fields(
    generator: TextGenerator,
    transcript: str,
    instructions: str,
    settings: IncidentStatusUpdateSettings,
    log: structlog.stdlib.BoundLogger,
) -> OperationResult[DraftedFields]:
    """Make the one model call and parse its answer strictly; never logs the transcript or instructions."""
    generated = await generator.summarize(transcript, instructions=instructions, max_output_tokens=settings.MAX_OUTPUT_TOKENS)
    if not generated.is_success or generated.data is None:
        log.warning("incident_status_update_generation_failed", status=generated.status, error_code=generated.error_code)
        return _failure(generated)
    fields = parse_drafted_fields(generated.data)
    if fields is None:
        log.warning("incident_status_update_unparseable")
        return OperationResult.permanent_error(
            message="The drafted status update could not be read",
            error_code=DRAFT_UNPARSEABLE_CODE,
        )
    return OperationResult.success(data=fields)


def _prefill_fields(last_public: StatusUpdate | None) -> DraftedFields:
    """The fields a manual draft starts from: the latest approved update, else blank at the first stage."""
    if last_public is None:
        blank = StatusUpdateText(affected_service="", impact="", current_action="", workaround="")
        return DraftedFields(stage=_STAGE_ORDER[0], en=blank, fr=blank)
    return DraftedFields(stage=last_public.stage, en=last_public.en, fr=last_public.fr)


def _holds(update: StatusUpdate, fields: DraftedFields) -> bool:
    """Whether ``update`` is a draft whose stage and text are exactly ``fields``."""
    return update.state is StatusUpdateState.DRAFT and (update.stage, update.en, update.fr) == (
        fields.stage,
        fields.en,
        fields.fr,
    )


def _security_gate(
    incident_id: str,
    security_confirmed: bool,
    security_reader: IncidentSecurityReader | None,
    log: structlog.stdlib.BoundLogger,
) -> OperationResult[StatusUpdateDraftOutcome] | None:
    """Return a refusal unless drafting for this incident may reach the model.

    Confirmation is explicit consent, so the flag is not read when given. A
    security, unknown or unreadable flag refuses with one code; the underlying
    read error is logged, never returned.
    """
    if security_confirmed:
        return None
    flag = (security_reader or get_incident_security_reader()).read_security_flag(incident_id)
    if flag.is_success and flag.data is IncidentSecurityFlag.NO:
        return None
    if flag.is_success:
        log.info("incident_status_update_security_confirmation_required", error_code=ErrorCode.SECURITY_CONFIRMATION_REQUIRED)
        message = "Drafting this status update needs the responder's security confirmation"
    else:
        log.warning(
            "incident_status_update_security_flag_unreadable",
            status=flag.status,
            read_error_code=flag.error_code,
            error_code=ErrorCode.SECURITY_CONFIRMATION_REQUIRED,
        )
        message = "The incident's security flag could not be read, so drafting needs the responder's confirmation"
    return OperationResult.permanent_error(message=message, error_code=ErrorCode.SECURITY_CONFIRMATION_REQUIRED)


def _read_window(
    reader: IncidentTranscriptReader,
    conversation_id: str,
    last_public: StatusUpdate | None,
    settings: IncidentStatusUpdateSettings,
    now: datetime,
    log: structlog.stdlib.BoundLogger,
) -> Sequence[TranscriptMessage]:
    """Read the conversation since the latest approved update, or since it started.

    A newer draft that was never approved does not narrow the window, so its
    content is drafted again with whatever followed.
    """
    if last_public is not None:
        since = last_public.transcript_cutoff
    else:
        since = reader.conversation_started_at(conversation_id) or now - timedelta(hours=settings.DEFAULT_SINCE_HOURS)
    messages = reader.read_transcript(
        conversation_id,
        since=since,
        limit=settings.MAX_HISTORY_LIMIT,
        exclude_own_and_system_messages=True,
    )
    if len(messages) >= settings.MAX_HISTORY_LIMIT:
        # One history page is read; older messages in the window may be missing.
        log.warning("incident_status_update_history_truncated", limit=settings.MAX_HISTORY_LIMIT)
    return messages


def _carry_forward(
    latest: StatusUpdate,
    *,
    author: str,
    wording: NoNewInformationWording,
    settings: IncidentStatusUpdateSettings,
    now: datetime,
) -> StatusUpdate:
    """Return the next draft repeating ``latest`` with the no-new-information wording."""
    return StatusUpdate(
        incident_id=latest.incident_id,
        sequence=latest.sequence + 1,
        state=StatusUpdateState.DRAFT,
        stage=latest.stage,
        en=replace(latest.en, current_action=wording.en),
        fr=replace(latest.fr, current_action=wording.fr),
        next_update_at=next_update_at_for(latest.stage, settings, now),
        author=author,
        transcript_cutoff=latest.transcript_cutoff,
        transcript_fingerprint=latest.transcript_fingerprint,
        created_at=now,
        origin=StatusUpdateOrigin.CARRIED_FORWARD,
    )


def _draft_record(
    incident_id: str,
    *,
    sequence: int,
    fields: DraftedFields,
    floor: StatusUpdateStage | None,
    people: Sequence[TranscriptMessage],
    author: str,
    settings: IncidentStatusUpdateSettings,
    now: datetime,
    origin: StatusUpdateOrigin,
    previous: StatusUpdate | None = None,
) -> StatusUpdate:
    """Return the draft record for freshly drafted fields, with the stage floor applied.

    Cutoff and fingerprint come from the people's messages read; with none
    (a redraft from instructions alone) they stay ``previous``'s.
    """
    stage = fields.stage if floor is None else max(fields.stage, floor, key=_STAGE_ORDER.index)
    if people or previous is None:
        cutoff, fingerprint = max(_posted_at(message) for message in people), _fingerprint(people)
    else:
        cutoff, fingerprint = previous.transcript_cutoff, previous.transcript_fingerprint
    return StatusUpdate(
        incident_id=incident_id,
        sequence=sequence,
        state=StatusUpdateState.DRAFT,
        stage=stage,
        en=fields.en,
        fr=fields.fr,
        next_update_at=next_update_at_for(stage, settings, now),
        author=author,
        transcript_cutoff=cutoff,
        transcript_fingerprint=fingerprint,
        created_at=now,
        origin=origin,
    )


def _append(
    store: StatusUpdateStore,
    update: StatusUpdate,
    kind: StatusUpdateOutcomeKind,
    log: structlog.stdlib.BoundLogger,
) -> OperationResult[StatusUpdateDraftOutcome]:
    """Store ``update``; when another writer's draft took its sequence, return that draft instead."""
    appended = store.append(update)
    if appended.is_success:
        log.info(f"incident_status_update_{kind}", sequence=update.sequence, kind=kind)
        return OperationResult.success(data=StatusUpdateDraftOutcome(update=update, kind=kind))
    if appended.error_code != ErrorCode.STATUS_UPDATE_CONFLICT:
        return _failure(appended)

    # One re-read, no retry loop: a winning draft is what a rerun would return anyway.
    winner = store.latest(update.incident_id).data
    if winner is not None and winner.state is StatusUpdateState.DRAFT and winner.sequence >= update.sequence:
        log.info("incident_status_update_pending", sequence=winner.sequence, kind=StatusUpdateOutcomeKind.PENDING)
        return OperationResult.success(data=StatusUpdateDraftOutcome(update=winner, kind=StatusUpdateOutcomeKind.PENDING))
    log.warning("incident_status_update_conflict", sequence=update.sequence)
    return _failure(appended)


def _append_new(
    store: StatusUpdateStore,
    update: StatusUpdate,
    kind: StatusUpdateOutcomeKind,
    log: structlog.stdlib.BoundLogger,
) -> OperationResult[StatusUpdateDraftOutcome]:
    """Store ``update``; another writer's record at its sequence is a conflict, never adopted."""
    appended = store.append(update)
    if not appended.is_success:
        log.warning("incident_status_update_store_failed", status=appended.status, error_code=appended.error_code)
        return _failure(appended)
    log.info(f"incident_status_update_{kind}", new_sequence=update.sequence, kind=kind, origin=update.origin)
    return OperationResult.success(data=StatusUpdateDraftOutcome(update=update, kind=kind))


def _is_pending(latest: StatusUpdate, sequence: int) -> bool:
    """Whether ``latest`` is the draft at ``sequence`` the responder is looking at."""
    return latest.sequence == sequence and latest.state is StatusUpdateState.DRAFT


def _stale[T](log: structlog.stdlib.BoundLogger) -> OperationResult[T]:
    log.info("incident_status_update_stale", error_code=ErrorCode.STATUS_UPDATE_CONFLICT)
    return OperationResult.permanent_error(
        message="The status update is no longer the pending draft",
        error_code=ErrorCode.STATUS_UPDATE_CONFLICT,
    )


def next_update_at_for(stage: StatusUpdateStage, settings: IncidentStatusUpdateSettings, now: datetime) -> datetime:
    """When the next update is due; a resolved incident has none, so it is ``now``."""
    if stage is StatusUpdateStage.RESOLVED:
        return now
    return now + timedelta(minutes=settings.NEXT_UPDATE_MINUTES)


def _fingerprint(messages: Sequence[TranscriptMessage]) -> str:
    """Digest of the people's messages a draft read: time and text, one per line."""
    content = "\n".join(f"{_posted_at(message).isoformat()}\t{message.text}" for message in messages)
    return f"v1:sha256:{hashlib.sha256(content.encode()).hexdigest()}"


def _posted_at(message: TranscriptMessage) -> datetime:
    """The message's time; callers only pass messages that have one."""
    if message.posted_at is None:
        raise ValueError("message has no posted_at")
    return message.posted_at


def _default_generator() -> TextGenerator:
    return providers.get_status_update_text_generator()


def _failure[T](result: OperationResult[Any]) -> OperationResult[T]:
    """Carry an error result's classification over to another payload type."""
    return OperationResult.error(
        result.status,
        message=result.message or "status update failed",
        error_code=result.error_code,
        retry_after=result.retry_after,
    )
