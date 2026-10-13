"""Dispatching the Draft with AI button of the review form through a real Bolt app.

The real ``features.incident.scribe`` plugin is registered on a real pluggy
PluginManager under its entry-point name ``incident.scribe``, so booting the
harness proves the Draft with AI action id passes the provider's plugin-prefix
check.
Payloads are form-encoded as Slack posts them, with the review form's state,
and fed to ``App.dispatch`` with listeners run inline; the harness sends every
payload as user ``USER_ID``. Only edges are stubbed: ``WebClient.api_call``
records Web API calls, and the entrypoint's ``generate_status_update_draft`` and
``get_draft_for_review`` are the real services bound to a core
``InMemoryStatusUpdateStore``, a stub incident lookup, a stub transcript reader,
a stub security flag reader and a stub text generator, with a fixed ``now``;
text generation is reported available.
Assertions read the exact Web API calls in order (only ``views.update``, never
a channel post), the one model call and the records left in the store.
"""

import hashlib
import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any

import pytest

import features.incident.scribe as scribe_module
from contracts.operations import OperationResult
from features.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from features.incident.core.api import (
    IncidentSecurityFlag,
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
    TranscriptMessage,
)
from features.incident.scribe import status_update_form
from features.incident.scribe.domain import StatusUpdateEdit
from features.incident.scribe.entrypoints.slack_views import (
    GENERATE_ACTION_ID,
    REVIEW_CALLBACK_ID,
    build_generating_view,
    build_no_new_information_wording,
    build_review_view,
)
from features.incident.scribe.status_update import generate_status_update_draft
from features.incident.scribe.status_update_approval import get_draft_for_review
from features.incident.scribe.status_update_prompt import INSTRUCTIONS, build_redraft_input, build_redraft_instructions
from tests.factories.slack_bolt import TRIGGER_ID, USER_ID, Harness, harness_fixture

pytestmark = pytest.mark.integration

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C0INCIDENT"
_SEQUENCE = 2
_VIEW_ID = "V0REVIEW"
_VIEW_HASH = "review-hash=="
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_GUIDANCE = "do not name the vendor"
_FIELDS = ("affected_service", "impact", "current_action", "workaround")
_REVIEW_METADATA = json.dumps({"channel_id": _CHANNEL, "locale": "en-US", "incident_id": _INCIDENT, "sequence": _SEQUENCE})
_NEW_METADATA = json.dumps({"channel_id": _CHANNEL, "locale": "en-US", "incident_id": _INCIDENT, "sequence": _SEQUENCE + 1})
_DRAFTED_NOTICE = "Drafted with AI. Review the new draft before you approve it."
_PERSON_AT = _NOW - timedelta(minutes=20)
_MESSAGES = (
    TranscriptMessage(author="Ada", text="vendor fixed the DNS", posted_at=_PERSON_AT),
    TranscriptMessage(author="Alertmanager", text="RESOLVED: 5xx", posted_at=_NOW - timedelta(minutes=10), is_bot=True),
)


def _text(language: str, tag: str) -> StatusUpdateText:
    return StatusUpdateText(**{name: f"{language} {name} {tag}" for name in _FIELDS})


_APPROVED = StatusUpdate(
    incident_id=_INCIDENT,
    sequence=1,
    state=StatusUpdateState.APPROVED,
    stage=StatusUpdateStage.IDENTIFIED,
    en=_text("en", "first"),
    fr=_text("fr", "first"),
    next_update_at=_NOW - timedelta(minutes=60),
    author="U999",
    transcript_cutoff=_NOW - timedelta(minutes=90),
    transcript_fingerprint="v1:sha256:first",
    created_at=_NOW - timedelta(minutes=90),
    approver="U0FIRST",
    approved_at=_NOW - timedelta(minutes=85),
)
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
)
_EDIT = StatusUpdateEdit(stage=StatusUpdateStage.MONITORING, en=_text("en", "edited"), fr=_text("fr", "edited"))
_ANSWER = {"stage": "monitoring"} | {
    f"{language}_{name}": f"{language} {name} filled" for language in ("en", "fr") for name in _FIELDS
}


def _expected_fill(origin: StatusUpdateOrigin = StatusUpdateOrigin.MODEL_INSTRUCTED) -> StatusUpdate:
    """The record the real service stores: the model's fields at the next sequence, by the presser, with the people's provenance."""
    content = f"{_PERSON_AT.isoformat()}\tvendor fixed the DNS"
    return StatusUpdate(
        incident_id=_INCIDENT,
        sequence=_SEQUENCE + 1,
        state=StatusUpdateState.DRAFT,
        stage=StatusUpdateStage.MONITORING,
        en=_text("en", "filled"),
        fr=_text("fr", "filled"),
        next_update_at=_NOW + timedelta(minutes=30),
        author=USER_ID,
        transcript_cutoff=_PERSON_AT,
        transcript_fingerprint=f"v1:sha256:{hashlib.sha256(content.encode()).hexdigest()}",
        created_at=_NOW,
        origin=origin,
    )


class _StubLookup:
    def find_incident_for_conversation(self, conversation_id: str) -> OperationResult[str]:
        return OperationResult.success(data=_INCIDENT)


class _StubReader:
    def conversation_started_at(self, conversation_id: str) -> datetime | None:
        return _NOW - timedelta(hours=10)

    def read_transcript(
        self,
        conversation_id: str,
        *,
        since: datetime,
        limit: int,
        exclude_own_and_system_messages: bool = False,
    ) -> Sequence[TranscriptMessage]:
        return _MESSAGES


class _StubSecurityReader:
    def read_security_flag(self, incident_id: str) -> OperationResult[IncidentSecurityFlag]:
        return OperationResult.success(data=IncidentSecurityFlag.NO)


@dataclass
class _StubGenerator:
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def summarize(
        self,
        transcript: str,
        *,
        instructions: str | None = None,
        max_output_tokens: int | None = None,
    ) -> OperationResult[str]:
        self.calls.append({"transcript": transcript, "instructions": instructions, "max_output_tokens": max_output_tokens})
        return OperationResult.success(data=json.dumps(_ANSWER))


@pytest.fixture
def generator() -> _StubGenerator:
    return _StubGenerator()


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch, generator: _StubGenerator) -> InMemoryStatusUpdateStore:
    status_updates = InMemoryStatusUpdateStore()
    status_updates.append(_APPROVED)
    status_updates.append(_PENDING)
    monkeypatch.setattr(
        status_update_form,
        "generate_status_update_draft",
        partial(
            generate_status_update_draft,
            lookup=_StubLookup(),
            reader=_StubReader(),
            store=status_updates,
            generator=generator,
            security_reader=_StubSecurityReader(),
            now=_NOW,
        ),
    )
    monkeypatch.setattr(status_update_form, "get_draft_for_review", partial(get_draft_for_review, store=status_updates))
    monkeypatch.setattr(status_update_form, "text_generation_available", lambda: True)
    return status_updates


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch, store: InMemoryStatusUpdateStore) -> Iterator[Harness]:
    yield from harness_fixture("incident.scribe")(monkeypatch, scribe_module)


def _generate_action(instructions: str | None) -> dict[str, Any]:
    values: dict[str, Any] = {
        f"{language}.{name}": {"text": {"type": "plain_text_input", "value": getattr(text, name)}}
        for language, text in (("en", _EDIT.en), ("fr", _EDIT.fr))
        for name in _FIELDS
    }
    stage = _EDIT.stage.value
    values["stage"] = {
        "stage": {"type": "static_select", "selected_option": {"text": {"type": "plain_text", "text": stage}, "value": stage}}
    }
    values["instructions"] = {"text": {"type": "plain_text_input", "value": instructions}}
    return {
        "type": "block_actions",
        "trigger_id": TRIGGER_ID,
        "view": {
            "id": _VIEW_ID,
            "hash": _VIEW_HASH,
            "type": "modal",
            "callback_id": REVIEW_CALLBACK_ID,
            "private_metadata": _REVIEW_METADATA,
            "state": {"values": values},
        },
        "actions": [{"action_id": GENERATE_ACTION_ID, "block_id": "generate_button", "type": "button"}],
    }


def test_draft_with_ai_is_acked(harness: Harness) -> None:
    """Bolt routes the Draft with AI press to the plugin's listener and acks it with HTTP 200."""
    response = harness.dispatch(_generate_action(_GUIDANCE))

    assert response.status == 200


def test_instructions_make_one_model_call_from_the_form_values_and_the_window(
    harness: Harness, generator: _StubGenerator
) -> None:
    """The model gets the guidance as instructions and the responder's typed values with the transcript as input."""
    harness.dispatch(_generate_action(_GUIDANCE))

    assert generator.calls == [
        {
            "transcript": build_redraft_input(_EDIT, "Ada: vendor fixed the DNS\nAlertmanager: RESOLVED: 5xx"),
            "instructions": build_redraft_instructions(_GUIDANCE),
            "max_output_tokens": 2000,
        }
    ]


def test_blank_instructions_draft_from_the_conversation_with_the_base_prompt(
    harness: Harness, generator: _StubGenerator, store: InMemoryStatusUpdateStore
) -> None:
    """Someone posted since the approved update, so blank instructions still make one model call, with the base prompt."""
    harness.dispatch(_generate_action("   "))

    assert [call["instructions"] for call in generator.calls] == [INSTRUCTIONS]
    assert store.list_for_incident(_INCIDENT).data == (_expected_fill(StatusUpdateOrigin.MODEL), _PENDING, _APPROVED)


def test_the_fill_is_stored_as_a_new_draft_and_keeps_the_previous_one(harness: Harness, store: InMemoryStatusUpdateStore) -> None:
    """The fill is the next DRAFT by the presser; the reviewed draft and the approved update are unchanged."""
    harness.dispatch(_generate_action(_GUIDANCE))

    assert store.list_for_incident(_INCIDENT).data == (_expected_fill(), _PENDING, _APPROVED)


def test_shows_generating_then_the_new_draft_form_and_posts_nothing(harness: Harness) -> None:
    """The only Web API calls are two views.update: the generating view by hash, then the new draft's form by id."""
    harness.dispatch(_generate_action(_GUIDANCE))

    assert harness.api_calls == [
        ("views.update", {"view_id": _VIEW_ID, "hash": _VIEW_HASH, "view": build_generating_view("en-US", _REVIEW_METADATA)}),
        (
            "views.update",
            {
                "view_id": _VIEW_ID,
                "view": build_review_view(_expected_fill(), "en-US", _NEW_METADATA, notice=_DRAFTED_NOTICE),
            },
        ),
    ]


def test_nothing_new_carries_the_typed_values_forward_without_a_model_call(
    harness: Harness, generator: _StubGenerator, store: InMemoryStatusUpdateStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With only messages from before the approved cutoff, the new draft repeats the typed values with the wording."""
    monkeypatch.setattr(_StubReader, "read_transcript", lambda self, conversation_id, **kwargs: ())

    harness.dispatch(_generate_action(""))

    assert generator.calls == []
    latest = store.latest(_INCIDENT).data
    assert latest is not None
    assert (latest.sequence, latest.origin, latest.en) == (
        _SEQUENCE + 1,
        StatusUpdateOrigin.CARRIED_FORWARD,
        replace(_EDIT.en, current_action=build_no_new_information_wording().en),
    )
    assert [method for method, _ in harness.api_calls] == ["views.update"]
