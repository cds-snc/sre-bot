"""The status-update review form: what to show after start, open, save or Draft with AI.

Platform-neutral use cases behind the status-updates modal. Each makes the
store and model calls one modal action needs and returns the form to show as a
``StatusUpdateFormState``, so an entry point makes one call and renders it:

- ``start_status_update_form`` starts or returns the pending draft.
- ``open_status_update_form`` reads the pending draft for review.
- ``save_status_update_form`` stores the typed values as the next draft.
- ``fill_status_update_form`` fills the draft with AI from the typed values, or
  from the stored draft when the form had no readable stage.

A save or fill that changes nothing (refused, failed, or no readable stage)
keeps the stored draft: the result is a success with ``kept`` set, the stored
draft overlaid with the typed values and the code that explains it. A stale
sequence (``STATUS_UPDATE_CONFLICT``) or an unreadable stored draft is an error
result. This module imports only ``core.api`` from the core.
"""

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from features.incident.core.api import StatusUpdate
from features.incident.scribe.domain import NoNewInformationWording, StatusUpdateEdit, StatusUpdateFormState
from features.incident.scribe.status_update import (
    generate_status_update_draft,
    save_status_update_draft,
    start_status_update_draft,
    text_generation_available,
)
from features.incident.scribe.status_update_approval import get_draft_for_review


def start_status_update_form(conversation_id: str, *, author: str) -> OperationResult[StatusUpdateFormState]:
    """Return the form for the pending draft, starting a hand-written draft when none is pending.

    Args:
        conversation_id: The incident conversation the modal was opened from.
        author: Platform user id of the responder who pressed New update.

    Returns:
        Success with the draft and how it came to be; otherwise the start's classified error.
    """
    started = start_status_update_draft(conversation_id, author=author)
    if not started.is_success or started.data is None:
        return _failure(started)
    return OperationResult.success(
        data=StatusUpdateFormState(update=started.data.update, ai_available=text_generation_available(), kind=started.data.kind)
    )


async def open_status_update_form(incident_id: str, sequence: int) -> OperationResult[StatusUpdateFormState]:
    """Return the form for the incident's pending draft at ``sequence``.

    Returns:
        Success with the draft; ``STATUS_UPDATE_CONFLICT`` when it is no longer
        the pending draft; otherwise the store's classified error.
    """
    stored = await get_draft_for_review(incident_id, sequence)
    if not stored.is_success or stored.data is None:
        return _failure(stored)
    return OperationResult.success(data=StatusUpdateFormState(update=stored.data, ai_available=text_generation_available()))


async def save_status_update_form(
    conversation_id: str,
    incident_id: str,
    sequence: int,
    *,
    edit: StatusUpdateEdit | None,
    author: str,
) -> OperationResult[StatusUpdateFormState]:
    """Store the typed values as the next draft and return the form to show.

    Args:
        conversation_id: The incident conversation the form was opened from.
        incident_id: The incident the draft belongs to.
        sequence: The pending draft's sequence the responder is editing.
        edit: The typed stage and fields; ``None`` when the form had no readable stage.
        author: Platform user id of the responder who pressed Save draft.

    Returns:
        Success with the saved draft; success with ``kept`` set when nothing
        was saved; ``STATUS_UPDATE_CONFLICT`` for a stale sequence or the
        stored draft's read error.
    """
    if edit is None:
        failure_code: str | None = ErrorCode.STATUS_UPDATE_FIELDS_INVALID
    else:
        saved = save_status_update_draft(conversation_id, sequence, edit=edit, author=author)
        if saved.is_success and saved.data is not None:
            return OperationResult.success(
                data=StatusUpdateFormState(update=saved.data, ai_available=text_generation_available())
            )
        if saved.error_code == ErrorCode.STATUS_UPDATE_CONFLICT:
            return _failure(saved)
        failure_code = saved.error_code
    return await _kept(incident_id, sequence, edit, failure_code, ai_available=text_generation_available())


async def fill_status_update_form(
    conversation_id: str,
    incident_id: str,
    sequence: int,
    *,
    edit: StatusUpdateEdit | None,
    author: str,
    wording: NoNewInformationWording,
    instructions: str,
    security_confirmed: bool,
    on_started: Callable[[], None] | None = None,
) -> OperationResult[StatusUpdateFormState]:
    """Fill the pending draft with AI from the typed values and return the form to show.

    The stored draft is read only when it is the model's base (``edit`` is
    ``None``) or a kept draft needs it.

    Args:
        conversation_id: The incident conversation the form was opened from.
        incident_id: The incident the draft belongs to.
        sequence: The pending draft's sequence the responder is editing.
        edit: The typed stage and fields; ``None`` when the form had no readable stage.
        author: Platform user id of the responder who pressed Draft with AI.
        wording: The no-new-information wording for a carry forward.
        instructions: The responder's instructions; blank means "draft from the conversation".
        security_confirmed: Whether the responder checked the security confirmation.
        on_started: Called just before a model call.

    Returns:
        Success with the new draft and its kind; success with ``kept`` set and
        the refusal or failure code when nothing changed;
        ``STATUS_UPDATE_CONFLICT`` for a stale sequence or the stored draft's read error.
    """
    base: StatusUpdate | None = None
    if edit is None:
        stored = await get_draft_for_review(incident_id, sequence)
        if not stored.is_success or stored.data is None:
            return _failure(stored)
        base = stored.data
        current = StatusUpdateEdit(stage=base.stage, en=base.en, fr=base.fr)
    else:
        current = edit
    filled = await generate_status_update_draft(
        conversation_id,
        sequence,
        current=current,
        author=author,
        wording=wording,
        instructions=instructions,
        security_confirmed=security_confirmed,
        on_started=on_started,
    )
    if filled.is_success and filled.data is not None:
        return OperationResult.success(
            data=StatusUpdateFormState(update=filled.data.update, ai_available=True, kind=filled.data.kind)
        )
    if filled.error_code == ErrorCode.STATUS_UPDATE_CONFLICT:
        return _failure(filled)
    ai_available = filled.error_code != ErrorCode.TEXT_GENERATION_UNAVAILABLE
    return await _kept(incident_id, sequence, edit, filled.error_code, ai_available=ai_available, stored=base)


async def _kept(
    incident_id: str,
    sequence: int,
    edit: StatusUpdateEdit | None,
    failure_code: str | None,
    *,
    ai_available: bool,
    stored: StatusUpdate | None = None,
) -> OperationResult[StatusUpdateFormState]:
    """The stored draft overlaid with the typed values, read unless already in hand."""
    if stored is None:
        read = await get_draft_for_review(incident_id, sequence)
        if not read.is_success or read.data is None:
            return _failure(read)
        stored = read.data
    update = stored if edit is None else replace(stored, stage=edit.stage, en=edit.en, fr=edit.fr)
    return OperationResult.success(
        data=StatusUpdateFormState(update=update, ai_available=ai_available, kept=True, failure_code=failure_code)
    )


def _failure[T](result: OperationResult[Any]) -> OperationResult[T]:
    """Carry an error result's classification over to another payload type."""
    return OperationResult.error(
        result.status,
        message=result.message or "status update failed",
        error_code=result.error_code,
        retry_after=result.retry_after,
    )
