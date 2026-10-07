"""Draft an incident's public status update from its conversation.

Platform-neutral use case behind ``/sre incident status-update``
(decisions/incident-management.md, External status updates). It resolves the
incident through the core, reads the conversation since the latest approved
update, and returns a draft record in one of three ways:

- ``PENDING``: the latest record is a draft and no person has posted since its
  cutoff, so that draft is returned as is;
- ``CARRIED_FORWARD``: the latest record is approved and no person has posted
  since, so the prior update is carried forward with the no-new-information
  wording, without a model call;
- ``DRAFTED``: people have posted since, so one model call fills the fields.

Code, not the model, decides that nothing is new: only messages posted by a
person strictly after the latest record's transcript cutoff count. Stages only
move forward from the latest approved or published stage. This module imports
only ``core.api`` from the core and no platform SDK.
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
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateStore,
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
    StatusUpdateOutcomeKind,
)
from packages.incident.scribe.ports import TextGenerator
from packages.incident.scribe.settings import IncidentStatusUpdateSettings, get_incident_status_update_settings
from packages.incident.scribe.status_update_prompt import INSTRUCTIONS, build_transcript, parse_drafted_fields

logger = structlog.get_logger()

DRAFT_UNPARSEABLE_CODE = "DRAFT_UNPARSEABLE"

_STAGE_ORDER = tuple(StatusUpdateStage)


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
        there is no record or the latest is not a draft. Otherwise the lookup's
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
    return OperationResult.success(data=pending)


async def draft_status_update(
    conversation_id: str,
    *,
    author: str,
    wording: NoNewInformationWording,
    on_started: Callable[[], None] | None = None,
    security_confirmed: bool = False,
    lookup: IncidentLookup | None = None,
    reader: IncidentTranscriptReader | None = None,
    store: StatusUpdateStore | None = None,
    generator: TextGenerator | None = None,
    security_reader: IncidentSecurityReader | None = None,
    now: datetime | None = None,
) -> OperationResult[StatusUpdateDraftOutcome]:
    """Return the incident's pending, carried-forward or newly drafted status update.

    Args:
        conversation_id: The incident conversation the command ran in.
        author: Platform user id of the responder asking for the draft.
        wording: The no-new-information wording of a carried-forward update.
        on_started: Called once just before the model call, after the security
            gate, so the caller can say drafting has begun; never called when no
            model call is made.
        security_confirmed: The responder confirmed drafting for a security or
            unknown-flag incident; the flag is then not read.
        lookup: Resolves the conversation to its incident; core's by default.
        reader: Reads the conversation; core's by default.
        store: Holds the incident's status updates; core's by default.
        generator: Drafts the fields; the scribe provider's by default.
        security_reader: Reads the incident's security flag; core's by default.
        now: The current time; injected in tests.

    Returns:
        Success with the draft and how it was produced. Otherwise the lookup's
        refusal (``NOT_AN_INCIDENT``, ``AMBIGUOUS_INCIDENT_CONVERSATION``), the
        store's or the generator's classified error, ``EMPTY_HISTORY`` when
        there is no update yet and no person has posted, ``DRAFT_UNPARSEABLE``
        when the model's answer is not fully usable, or
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

    if not new_from_people:
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

    refusal = _security_gate(incident_id, security_confirmed, security_reader, log)
    if refusal is not None:
        return refusal

    if on_started is not None:
        on_started()
    generator = generator or _default_generator()
    generated = await generator.summarize(
        build_transcript(messages),
        instructions=INSTRUCTIONS,
        max_output_tokens=settings.MAX_OUTPUT_TOKENS,
    )
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

    drafted = _draft_record(
        incident_id,
        sequence=latest.sequence + 1 if latest else 1,
        fields=fields,
        floor=last_public.stage if last_public else None,
        people=people,
        author=author,
        settings=settings,
        now=now,
    )
    return _append(store, drafted, StatusUpdateOutcomeKind.DRAFTED, log)


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
) -> StatusUpdate:
    """Return the draft record for freshly drafted fields, with the stage floor applied."""
    stage = fields.stage if floor is None else max(fields.stage, floor, key=_STAGE_ORDER.index)
    return StatusUpdate(
        incident_id=incident_id,
        sequence=sequence,
        state=StatusUpdateState.DRAFT,
        stage=stage,
        en=fields.en,
        fr=fields.fr,
        next_update_at=next_update_at_for(stage, settings, now),
        author=author,
        transcript_cutoff=max(_posted_at(message) for message in people),
        transcript_fingerprint=_fingerprint(people),
        created_at=now,
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
