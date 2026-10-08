"""Tests for the Open and Back listeners of the status-updates modal.

Open acks, reads the approved update named by the button's value, renders it
through the status page publisher with both label sets and replaces the modal
in place, by view id and hash, with the reopened copy-ready view. Back acks,
reads the incident's overview for the channel named by its value and replaces
the modal in place with the list. Failures show the Close-only error view;
Slack exceptions are logged, never raised; the only Slack call is
``views_update`` and nothing is written to the store.

The service boundary is stubbed with recording fakes in the entrypoint
module's namespace (``get_approved_update``, ``get_status_update_overview``)
and the publisher returned by ``providers.get_status_page_publisher``; every
fake writes to one shared event log with the ack and the client, so call order
is asserted directly. The no-write tests instead bind the real services to a
counting in-memory store and keep the real copy-ready publisher. Expected views
come from the platform view builders, so each assertion compares the exact view
sent.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from functools import partial
from typing import Any
from unittest.mock import MagicMock, call

import pytest
from structlog.testing import capture_logs

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from packages.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from packages.incident.scribe import providers
from packages.incident.scribe.adapters.copy_ready import CopyReadyPublisher
from packages.incident.scribe.comms_profile import ProfileLabels
from packages.incident.scribe.domain import CopyReadyText, StatusUpdateOverview
from packages.incident.scribe.entrypoints import slack as slack_entrypoints
from packages.incident.scribe.entrypoints.slack import (
    handle_draft_action,
    handle_draft_confirmed_action,
    handle_history_action,
    handle_open_action,
    handle_published_action,
    handle_redraft_action,
    handle_review_action,
    handle_review_submission,
    register,
)
from packages.incident.scribe.platforms.slack import (
    CONFIRM_ACTION_ID,
    DRAFT_ACTION_ID,
    HISTORY_ACTION_ID,
    OPEN_ACTION_ID,
    PUBLISHED_ACTION_ID,
    REDRAFT_ACTION_ID,
    REVIEW_ACTION_ID,
    REVIEW_CALLBACK_ID,
    build_copy_ready_view,
    build_draft_error_view,
    build_overview_view,
    build_profile_labels,
)
from packages.incident.scribe.publisher import render_copy_ready
from packages.incident.scribe.status_update import get_status_update_overview
from packages.incident.scribe.status_update_history import get_approved_update
from tests.factories.slack import FakeSlackRegistrar

pytestmark = pytest.mark.unit

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_USER = "U0VIEWER"
_SEQUENCE = 2
_VIEW_ID = "V456"
_VIEW_HASH = "hash123=="
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_COPY = CopyReadyText(en="Stage: Identified\n\nImpact: en impact", fr="Étape : Identifié\n\nIncidence : fr impact")


def _text(language: str) -> StatusUpdateText:
    return StatusUpdateText(
        affected_service=f"{language} service",
        impact=f"{language} impact",
        current_action=f"{language} action",
        workaround=f"{language} workaround",
    )


_APPROVED = StatusUpdate(
    incident_id=_INCIDENT,
    sequence=_SEQUENCE,
    state=StatusUpdateState.APPROVED,
    stage=StatusUpdateStage.IDENTIFIED,
    en=_text("en"),
    fr=_text("fr"),
    next_update_at=_NOW,
    author="U999",
    transcript_cutoff=_NOW,
    transcript_fingerprint="v1:sha256:abc123",
    created_at=_NOW,
    approver="U0APPROVER",
    approved_at=_NOW,
)
_DRAFT = replace(_APPROVED, sequence=_SEQUENCE + 1, state=StatusUpdateState.DRAFT, approver=None, approved_at=None)
_OVERVIEW = StatusUpdateOverview(pending=_DRAFT, approved=(_APPROVED,))


def _metadata(locale: str = "en-US") -> str:
    return json.dumps({"channel_id": _CHANNEL, "locale": locale})


@dataclass
class _Services:
    """Recording fakes for the approved-update read, the overview read and the publisher.

    Every call appends its name to the shared ``events`` log, which the ack and
    the Slack client also write to, so tests can assert call order.
    """

    events: list[str]
    approved_result: OperationResult[StatusUpdate] = field(default_factory=lambda: OperationResult.success(data=_APPROVED))
    overview_result: OperationResult[StatusUpdateOverview] = field(
        default_factory=lambda: OperationResult.success(data=_OVERVIEW)
    )
    publish_result: OperationResult[CopyReadyText] = field(default_factory=lambda: OperationResult.success(data=_COPY))
    approved_calls: list[tuple[str, int]] = field(default_factory=list)
    overview_calls: list[str] = field(default_factory=list)
    publish_calls: list[tuple[StatusUpdate, ProfileLabels, ProfileLabels]] = field(default_factory=list)

    async def get_approved_update(self, incident_id: str, sequence: int) -> OperationResult[StatusUpdate]:
        self.events.append("get_approved_update")
        self.approved_calls.append((incident_id, sequence))
        return self.approved_result

    def get_status_update_overview(self, conversation_id: str) -> OperationResult[StatusUpdateOverview]:
        self.events.append("get_status_update_overview")
        self.overview_calls.append(conversation_id)
        return self.overview_result

    async def publish(
        self, update: StatusUpdate, *, labels_en: ProfileLabels, labels_fr: ProfileLabels
    ) -> OperationResult[CopyReadyText]:
        self.events.append("publish")
        self.publish_calls.append((update, labels_en, labels_fr))
        return self.publish_result


class _CountingStore:
    """In-memory store wrapper that records reads and writes, so a test can prove nothing was written."""

    def __init__(self, *updates: StatusUpdate) -> None:
        self._inner = InMemoryStatusUpdateStore()
        for update in updates:
            self._inner.append(update)
        self.writes: list[str] = []

    def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        self.writes.append("append")
        return self._inner.append(update)

    def transition(self, update: StatusUpdate, *, expected_state: StatusUpdateState) -> OperationResult[StatusUpdate]:
        self.writes.append("transition")
        return self._inner.transition(update, expected_state=expected_state)

    def latest(self, incident_id: str) -> OperationResult[StatusUpdate | None]:
        return self._inner.latest(incident_id)

    def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        return self._inner.list_for_incident(incident_id)


class _StubLookup:
    def find_incident_for_conversation(self, conversation_id: str) -> OperationResult[str]:
        return OperationResult.success(data=_INCIDENT)


@pytest.fixture
def events() -> list[str]:
    return []


@pytest.fixture
def services(monkeypatch: pytest.MonkeyPatch, events: list[str]) -> _Services:
    fakes = _Services(events=events)
    monkeypatch.setattr(slack_entrypoints, "get_approved_update", fakes.get_approved_update)
    monkeypatch.setattr(slack_entrypoints, "get_status_update_overview", fakes.get_status_update_overview)
    monkeypatch.setattr(providers, "get_status_page_publisher", lambda: fakes)
    return fakes


@pytest.fixture
def ack(events: list[str]) -> MagicMock:
    return MagicMock(side_effect=lambda *args, **kwargs: events.append("ack"))


@pytest.fixture
def client(events: list[str]) -> MagicMock:
    slack_client = MagicMock()

    def views_update(**kwargs: Any) -> dict[str, Any]:
        events.append("views_update")
        return {"ok": True, "view": {"hash": "next-hash=="}}

    slack_client.views_update.side_effect = views_update
    return slack_client


def _action_body(action_id: str, value: str, locale: str = "en-US") -> dict[str, Any]:
    """A block_actions body for a button pressed in the status-updates modal."""
    return {
        "type": "block_actions",
        "user": {"id": _USER},
        "trigger_id": "trigger-123",
        "view": {"id": _VIEW_ID, "hash": _VIEW_HASH, "private_metadata": _metadata(locale)},
        "actions": [{"action_id": action_id, "block_id": "any", "type": "button", "value": value}],
    }


def _open_body(locale: str = "en-US", value: str | None = None) -> dict[str, Any]:
    target = value if value is not None else json.dumps({"incident_id": _INCIDENT, "sequence": _SEQUENCE})
    return _action_body(OPEN_ACTION_ID, target, locale)


def _back_body(locale: str = "en-US") -> dict[str, Any]:
    return _action_body(HISTORY_ACTION_ID, json.dumps({"channel_id": _CHANNEL}), locale)


def _client_method_names(client: MagicMock) -> list[str]:
    return [method_call[0] for method_call in client.method_calls]


class TestRegister:
    def test_registers_open_and_back_beside_the_existing_listeners(self) -> None:
        """Registration adds the Open and Back block actions and keeps every existing listener."""
        registrar = FakeSlackRegistrar()

        register(registrar)

        assert registrar.block_actions == {
            DRAFT_ACTION_ID: handle_draft_action,
            CONFIRM_ACTION_ID: handle_draft_confirmed_action,
            REVIEW_ACTION_ID: handle_review_action,
            OPEN_ACTION_ID: handle_open_action,
            HISTORY_ACTION_ID: handle_history_action,
            PUBLISHED_ACTION_ID: handle_published_action,
            REDRAFT_ACTION_ID: handle_redraft_action,
        }
        assert registrar.view_submissions == {REVIEW_CALLBACK_ID: handle_review_submission}


class TestHandleOpenAction:
    def test_acks_then_reads_publishes_and_updates(
        self, ack: MagicMock, client: MagicMock, services: _Services, events: list[str]
    ) -> None:
        """Ack comes first, then the approved-update read, the rendering and the one view update."""
        handle_open_action(ack, _open_body(), client)

        assert events == ["ack", "get_approved_update", "publish", "views_update"]
        ack.assert_called_once_with()

    def test_reads_the_update_named_by_the_button(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """The read gets the incident id and sequence decoded from the Open button's value."""
        handle_open_action(ack, _open_body(), client)

        assert services.approved_calls == [(_INCIDENT, _SEQUENCE)]

    def test_publishes_the_read_record_with_both_label_sets(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """The record read is rendered by the publisher with the English and French profile labels."""
        handle_open_action(ack, _open_body(), client)

        assert services.publish_calls == [(_APPROVED, build_profile_labels("en-US"), build_profile_labels("fr-FR"))]

    @pytest.mark.parametrize("locale", ["en-US", "fr-FR"])
    def test_replaces_the_modal_with_the_reopened_copy_ready_view(
        self, ack: MagicMock, client: MagicMock, services: _Services, locale: str
    ) -> None:
        """One views_update by view id and hash shows the copy-ready view of the record, keeping the metadata."""
        handle_open_action(ack, _open_body(locale), client)

        assert client.views_update.call_args_list == [
            call(
                view_id=_VIEW_ID,
                hash=_VIEW_HASH,
                view=build_copy_ready_view(_COPY, locale, _metadata(locale), update=_APPROVED),
            )
        ]

    @pytest.mark.parametrize(
        "result",
        [
            OperationResult.permanent_error(message="draft", error_code=ErrorCode.STATUS_UPDATE_NOT_APPROVED),
            OperationResult.permanent_error(message="missing", error_code=ErrorCode.STATUS_UPDATE_CONFLICT),
            OperationResult.transient_error(message="store throttled", error_code=ErrorCode.RATE_LIMITED),
        ],
        ids=["not-approved", "conflict", "store-error"],
    )
    def test_read_failure_shows_the_error_view_without_publishing(
        self, ack: MagicMock, client: MagicMock, services: _Services, result: OperationResult[StatusUpdate]
    ) -> None:
        """A refused read is not rendered; the modal shows the Close-only error view for its code."""
        services.approved_result = result

        handle_open_action(ack, _open_body(), client)

        assert services.publish_calls == []
        assert client.views_update.call_args_list == [
            call(view_id=_VIEW_ID, hash=_VIEW_HASH, view=build_draft_error_view(result.error_code, "en-US", _metadata()))
        ]

    def test_publish_failure_shows_the_error_view(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """A publisher refusal shows the error view for the publisher's code."""
        services.publish_result = OperationResult.permanent_error(
            message="not approved", error_code=ErrorCode.STATUS_UPDATE_NOT_APPROVED
        )

        handle_open_action(ack, _open_body(), client)

        assert client.views_update.call_args_list == [
            call(
                view_id=_VIEW_ID,
                hash=_VIEW_HASH,
                view=build_draft_error_view(ErrorCode.STATUS_UPDATE_NOT_APPROVED, "en-US", _metadata()),
            )
        ]

    def test_unreadable_value_shows_the_error_view_without_reading(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """A value without an integer sequence reads nothing and shows the generic error view."""
        handle_open_action(ack, _open_body(value=json.dumps({"incident_id": _INCIDENT})), client)

        assert services.approved_calls == []
        assert client.views_update.call_args_list == [
            call(view_id=_VIEW_ID, hash=_VIEW_HASH, view=build_draft_error_view(None, "en-US", _metadata()))
        ]

    def test_read_failure_is_logged(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """A refused read is logged once as a warning carrying its error code."""
        services.approved_result = OperationResult.permanent_error(message="x", error_code=ErrorCode.STATUS_UPDATE_CONFLICT)

        with capture_logs() as logs:
            handle_open_action(ack, _open_body(), client)

        failures = [entry for entry in logs if entry["event"] == "incident_status_update_open_failed"]
        assert [(entry["log_level"], entry["error_code"]) for entry in failures] == [
            ("warning", ErrorCode.STATUS_UPDATE_CONFLICT)
        ]

    def test_slack_failure_is_logged_not_raised(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """A views_update exception is logged as one warning and the listener returns normally."""
        client.views_update.side_effect = RuntimeError("view_not_found")

        with capture_logs() as logs:
            handle_open_action(ack, _open_body(), client)

        failures = [entry for entry in logs if entry["event"] == "incident_status_update_open_update_failed"]
        assert [entry["log_level"] for entry in failures] == ["warning"]

    def test_only_updates_the_view(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """The only Slack call is views_update: nothing is posted to the incident channel."""
        handle_open_action(ack, _open_body(), client)

        assert _client_method_names(client) == ["views_update"]


class TestHandleOpenActionOverRealServices:
    def test_writes_nothing_and_shows_the_approval_text(
        self, monkeypatch: pytest.MonkeyPatch, ack: MagicMock, client: MagicMock
    ) -> None:
        """Over the real read and the copy-ready publisher, the store sees no write and the text is the approval's.

        The shown text is ``render_copy_ready`` of the stored record with both
        label sets, which is what the approval view showed for that record.
        """
        store = _CountingStore(_APPROVED, _DRAFT)
        monkeypatch.setattr(slack_entrypoints, "get_approved_update", partial(get_approved_update, store=store))
        monkeypatch.setattr(providers, "get_status_page_publisher", CopyReadyPublisher)

        handle_open_action(ack, _open_body(), client)

        copy = render_copy_ready(_APPROVED, build_profile_labels("en-US"), build_profile_labels("fr-FR"))
        assert store.writes == []
        assert client.views_update.call_args_list == [
            call(view_id=_VIEW_ID, hash=_VIEW_HASH, view=build_copy_ready_view(copy, "en-US", _metadata(), update=_APPROVED))
        ]


class TestHandleHistoryAction:
    def test_acks_then_reads_the_overview_and_updates(
        self, ack: MagicMock, client: MagicMock, services: _Services, events: list[str]
    ) -> None:
        """Ack comes first, then the overview read, then the one view update; nothing is rendered by the publisher."""
        handle_history_action(ack, _back_body(), client)

        assert events == ["ack", "get_status_update_overview", "views_update"]
        ack.assert_called_once_with()

    def test_reads_the_overview_of_the_button_channel(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """The overview is read for the channel id decoded from the Back button's value."""
        handle_history_action(ack, _back_body(), client)

        assert services.overview_calls == [_CHANNEL]

    @pytest.mark.parametrize("locale", ["en-US", "fr-FR"])
    def test_replaces_the_modal_with_the_list(self, ack: MagicMock, client: MagicMock, services: _Services, locale: str) -> None:
        """One views_update by view id and hash shows the overview view, keeping the channel and locale metadata."""
        handle_history_action(ack, _back_body(locale), client)

        assert client.views_update.call_args_list == [
            call(view_id=_VIEW_ID, hash=_VIEW_HASH, view=build_overview_view(_OVERVIEW, locale, _metadata(locale)))
        ]

    @pytest.mark.parametrize(
        "result",
        [
            OperationResult.permanent_error(message="not an incident", error_code=ErrorCode.NOT_AN_INCIDENT),
            OperationResult.transient_error(message="store throttled", error_code=ErrorCode.RATE_LIMITED),
        ],
        ids=["not-an-incident", "store-error"],
    )
    def test_failure_shows_the_error_view(
        self, ack: MagicMock, client: MagicMock, services: _Services, result: OperationResult[StatusUpdateOverview]
    ) -> None:
        """A failed overview read shows the Close-only error view for its code."""
        services.overview_result = result

        handle_history_action(ack, _back_body(), client)

        assert client.views_update.call_args_list == [
            call(view_id=_VIEW_ID, hash=_VIEW_HASH, view=build_draft_error_view(result.error_code, "en-US", _metadata()))
        ]

    def test_failure_is_logged(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """A failed overview read is logged once as a warning carrying its error code."""
        services.overview_result = OperationResult.transient_error(message="x", error_code=ErrorCode.RATE_LIMITED)

        with capture_logs() as logs:
            handle_history_action(ack, _back_body(), client)

        failures = [entry for entry in logs if entry["event"] == "incident_status_update_history_failed"]
        assert [(entry["log_level"], entry["error_code"]) for entry in failures] == [("warning", ErrorCode.RATE_LIMITED)]

    def test_slack_failure_is_logged_not_raised(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """A views_update exception is logged as one warning and the listener returns normally."""
        client.views_update.side_effect = RuntimeError("view_not_found")

        with capture_logs() as logs:
            handle_history_action(ack, _back_body(), client)

        failures = [entry for entry in logs if entry["event"] == "incident_status_update_history_update_failed"]
        assert [entry["log_level"] for entry in failures] == ["warning"]

    def test_only_updates_the_view(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """The only Slack call is views_update: nothing is posted to the incident channel."""
        handle_history_action(ack, _back_body(), client)

        assert _client_method_names(client) == ["views_update"]


class TestHandleHistoryActionOverRealServices:
    def test_writes_nothing_and_shows_the_stored_overview(
        self, monkeypatch: pytest.MonkeyPatch, ack: MagicMock, client: MagicMock
    ) -> None:
        """Over the real overview read, the store sees no write and the list shows the stored records."""
        store = _CountingStore(_APPROVED, _DRAFT)
        monkeypatch.setattr(
            slack_entrypoints,
            "get_status_update_overview",
            partial(get_status_update_overview, lookup=_StubLookup(), store=store),
        )

        handle_history_action(ack, _back_body(), client)

        assert store.writes == []
        assert client.views_update.call_args_list == [
            call(view_id=_VIEW_ID, hash=_VIEW_HASH, view=build_overview_view(_OVERVIEW, "en-US", _metadata()))
        ]
