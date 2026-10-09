"""Dispatching the Save draft button of the review modal through a real Bolt app.

The real ``packages.incident.scribe`` plugin is registered on a real pluggy
PluginManager under its entry-point name ``incident.scribe``, so booting the
harness proves the Save draft action id passes the provider's plugin-prefix
check. Payloads are form-encoded as Slack posts them, with the review form's
state, and fed to ``App.dispatch`` with listeners run inline; the harness sends
every payload as user ``USER_ID``. Only edges are stubbed: ``WebClient.api_call``
records Web API calls, and the entrypoint's ``save_status_update_draft`` and
``get_draft_for_review`` are the real services bound to a core
``InMemoryStatusUpdateStore`` and a stub incident lookup, with a fixed ``now``.
Assertions read the exact Web API calls (only ``views.update``, never a channel
post) and the records left in the store.
"""

import json
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any

import pytest

import packages.incident.scribe as scribe_module
from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from packages.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from packages.incident.core.api import (
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
)
from packages.incident.scribe.domain import StatusUpdateEdit
from packages.incident.scribe.entrypoints import slack as slack_entrypoints
from packages.incident.scribe.entrypoints.slack_views import (
    REVIEW_CALLBACK_ID,
    SAVE_ACTION_ID,
    build_review_error_view,
    build_review_view,
)
from packages.incident.scribe.status_update import save_status_update_draft
from packages.incident.scribe.status_update_approval import get_draft_for_review
from tests.factories.slack_bolt import TRIGGER_ID, USER_ID, Harness, harness_fixture

pytestmark = pytest.mark.integration

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C0INCIDENT"
_SEQUENCE = 1
_VIEW_ID = "V0REVIEW"
_VIEW_HASH = "review-hash=="
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_FIELDS = ("affected_service", "impact", "current_action", "workaround")
_SAVED_NOTE = "Draft saved."


def _metadata(sequence: int) -> str:
    return json.dumps({"channel_id": _CHANNEL, "locale": "en-US", "incident_id": _INCIDENT, "sequence": sequence})


def _text(language: str, tag: str) -> StatusUpdateText:
    return StatusUpdateText(**{name: f"{language} {name} {tag}" for name in _FIELDS})


_PENDING = StatusUpdate(
    incident_id=_INCIDENT,
    sequence=_SEQUENCE,
    state=StatusUpdateState.DRAFT,
    stage=StatusUpdateStage.IDENTIFIED,
    en=_text("en", "pending"),
    fr=_text("fr", "pending"),
    next_update_at=_NOW - timedelta(minutes=10),
    author="U999",
    transcript_cutoff=_NOW - timedelta(minutes=40),
    transcript_fingerprint="v1:sha256:pending",
    created_at=_NOW - timedelta(minutes=40),
    origin=StatusUpdateOrigin.MODEL,
)
_EDIT = StatusUpdateEdit(
    stage=StatusUpdateStage.IDENTIFIED,
    en=replace(_text("en", "typed"), workaround=""),
    fr=_text("fr", "typed"),
)
_SAVED = replace(
    _PENDING, sequence=_SEQUENCE + 1, en=_EDIT.en, fr=_EDIT.fr, author=USER_ID, created_at=_NOW, origin=StatusUpdateOrigin.HAND
)


class _StubLookup:
    def find_incident_for_conversation(self, conversation_id: str) -> OperationResult[str]:
        return OperationResult.success(data=_INCIDENT)


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> InMemoryStatusUpdateStore:
    status_updates = InMemoryStatusUpdateStore()
    status_updates.append(_PENDING)
    monkeypatch.setattr(
        slack_entrypoints,
        "save_status_update_draft",
        partial(save_status_update_draft, lookup=_StubLookup(), store=status_updates, now=_NOW),
    )
    monkeypatch.setattr(slack_entrypoints, "get_draft_for_review", partial(get_draft_for_review, store=status_updates))
    return status_updates


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch, store: InMemoryStatusUpdateStore) -> Iterator[Harness]:
    yield from harness_fixture("incident.scribe")(monkeypatch, scribe_module)


def _save_action(sequence: int = _SEQUENCE) -> dict[str, Any]:
    values: dict[str, Any] = {
        f"{language}.{name}": {"text": {"type": "plain_text_input", "value": getattr(text, name) or None}}
        for language, text in (("en", _EDIT.en), ("fr", _EDIT.fr))
        for name in _FIELDS
    }
    stage = _EDIT.stage.value
    values["stage"] = {
        "stage": {"type": "static_select", "selected_option": {"text": {"type": "plain_text", "text": stage}, "value": stage}}
    }
    return {
        "type": "block_actions",
        "trigger_id": TRIGGER_ID,
        "view": {
            "id": _VIEW_ID,
            "hash": _VIEW_HASH,
            "type": "modal",
            "callback_id": REVIEW_CALLBACK_ID,
            "private_metadata": _metadata(sequence),
            "state": {"values": values},
        },
        "actions": [{"action_id": SAVE_ACTION_ID, "block_id": "save_button", "type": "button"}],
    }


def test_save_is_acked(harness: Harness) -> None:
    """Bolt routes the Save draft press to the plugin's listener and acks it with HTTP 200."""
    response = harness.dispatch(_save_action())

    assert response.status == 200


def test_save_stores_the_typed_values_as_the_next_hand_written_draft(harness: Harness, store: InMemoryStatusUpdateStore) -> None:
    """The typed fields, a blank one included, are the next draft by the presser; the AI draft stays below it."""
    harness.dispatch(_save_action())

    assert store.list_for_incident(_INCIDENT).data == (_SAVED, _PENDING)


def test_save_shows_the_saved_form_and_posts_nothing(harness: Harness) -> None:
    """The only Web API call is one views.update of the pressed modal to the saved draft's form with the notice."""
    harness.dispatch(_save_action())

    assert harness.api_calls == [
        (
            "views.update",
            {
                "view_id": _VIEW_ID,
                "hash": _VIEW_HASH,
                "view": build_review_view(_SAVED, "en-US", _metadata(_SEQUENCE + 1), notice=_SAVED_NOTE),
            },
        )
    ]


def test_a_stale_form_shows_the_conflict_view_and_stores_nothing(harness: Harness, store: InMemoryStatusUpdateStore) -> None:
    """A form opened on an older sequence cannot overwrite the newer draft; the modal shows the conflict view."""
    store.append(replace(_PENDING, sequence=_SEQUENCE + 1, author="U0OTHER"))

    harness.dispatch(_save_action())

    assert harness.api_calls == [
        (
            "views.update",
            {
                "view_id": _VIEW_ID,
                "hash": _VIEW_HASH,
                "view": build_review_error_view(ErrorCode.STATUS_UPDATE_CONFLICT, "en-US", _metadata(_SEQUENCE)),
            },
        )
    ]
    assert [record.sequence for record in store.list_for_incident(_INCIDENT).data or ()] == [_SEQUENCE + 1, _SEQUENCE]
