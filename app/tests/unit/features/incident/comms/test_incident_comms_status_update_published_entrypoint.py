"""Tests for the published toggle listener of the status-updates modal.

The toggle acks, decodes the incident, sequence and target state from the
button's value, sets that state through the service with the pressing user as
the actor, renders the returned record through the status page publisher with
both label sets and replaces the modal in place, by view id and the payload's
hash, with the reopened copy-ready view of that record. A refusal or a
publisher failure shows the Close-only toggle error view. Slack exceptions are
logged, never raised; the only Slack call is ``views_update``, so nothing is
posted to the incident channel.

The service boundary is stubbed with recording fakes in the entrypoint
module's namespace (``set_published``) and the publisher returned by
``providers.get_status_page_publisher``; every fake writes to one shared event
log with the ack and the client, so call order is asserted directly. The
over-real-services test instead keeps the real ``set_published`` over the
status-update store the handler builds on a recording in-memory record store,
and the real copy-ready publisher, proving the one transition is the only
record write. Expected views come from the platform
view builders, so each assertion compares the exact view sent.
"""

import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from functools import partial
from typing import Any
from unittest.mock import MagicMock, call

import pytest
from structlog.testing import capture_logs

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from features.incident.comms import history, providers
from features.incident.comms.adapters.copy_ready import CopyReadyPublisher
from features.incident.comms.comms_profile import ProfileLabels
from features.incident.comms.domain import CopyReadyText
from features.incident.comms.entrypoints.slack import handle_published_action, register
from features.incident.comms.entrypoints.slack_views import (
    GENERATE_ACTION_ID,
    HISTORY_ACTION_ID,
    NEW_ACTION_ID,
    OPEN_ACTION_ID,
    PUBLISHED_ACTION_ID,
    REVIEW_ACTION_ID,
    REVIEW_CALLBACK_ID,
    SAVE_ACTION_ID,
    build_copy_ready_view,
    build_profile_labels,
    build_published_error_view,
)
from features.incident.comms.history import set_published
from features.incident.comms.publisher import render_copy_ready
from features.incident.core.api import (
    StatusUpdate,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateStore,
    StatusUpdateText,
)
from tests.factories.incident import CountingRecordStore, incident_scopes, status_update_store_in
from tests.factories.slack import FakeSlackRegistrar

pytestmark = pytest.mark.unit

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_USER = "U0PRESSER"
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


def _published() -> StatusUpdate:
    """The approved update as stored once the presser marked it published at ``_NOW``."""
    return replace(_APPROVED, state=StatusUpdateState.PUBLISHED, published_at=_NOW, published_by=_USER)


def _metadata(locale: str = "en-US") -> str:
    return json.dumps({"channel_id": _CHANNEL, "locale": locale})


@dataclass
class _Services:
    """Recording fakes for the toggle service and the publisher.

    Every call appends its name to the shared ``events`` log, which the ack and
    the Slack client also write to, so tests can assert call order. The
    toggle's default answer is the approved record, which every test can
    replace with any real ``OperationResult``.
    """

    events: list[str]
    toggle_result: OperationResult[StatusUpdate] = field(default_factory=lambda: OperationResult.success(data=_APPROVED))
    publish_result: OperationResult[CopyReadyText] = field(default_factory=lambda: OperationResult.success(data=_COPY))
    toggle_calls: list[tuple[str, int, bool, str]] = field(default_factory=list)
    stores: list[StatusUpdateStore] = field(default_factory=list)
    publish_calls: list[tuple[StatusUpdate, ProfileLabels, ProfileLabels]] = field(default_factory=list)

    async def set_published(
        self, incident_id: str, sequence: int, *, published: bool, actor: str, store: StatusUpdateStore
    ) -> OperationResult[StatusUpdate]:
        self.events.append("set_published")
        self.stores.append(store)
        self.toggle_calls.append((incident_id, sequence, published, actor))
        return self.toggle_result

    async def publish(
        self, update: StatusUpdate, *, labels_en: ProfileLabels, labels_fr: ProfileLabels
    ) -> OperationResult[CopyReadyText]:
        self.events.append("publish")
        self.publish_calls.append((update, labels_en, labels_fr))
        return self.publish_result


@pytest.fixture
def events() -> list[str]:
    return []


@pytest.fixture
def services(monkeypatch: pytest.MonkeyPatch, events: list[str]) -> _Services:
    fakes = _Services(events=events)
    monkeypatch.setattr(history, "set_published", fakes.set_published)
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


def _target(published: bool = True) -> str:
    """The toggle button's value: the update and the state the press will set."""
    return json.dumps({"incident_id": _INCIDENT, "sequence": _SEQUENCE, "published": published})


def _view(locale: str = "en-US") -> dict[str, Any]:
    return {"id": _VIEW_ID, "hash": _VIEW_HASH, "private_metadata": _metadata(locale)}


def _toggle_body(value: str = _target(), view: dict[str, Any] | None = None) -> dict[str, Any]:
    """A block_actions body for the toggle pressed in the reopened copy-ready view (English view by default)."""
    return {
        "type": "block_actions",
        "user": {"id": _USER},
        "trigger_id": "trigger-123",
        "view": view or _view(),
        "actions": [{"action_id": PUBLISHED_ACTION_ID, "block_id": "approved_status", "type": "button", "value": value}],
    }


def _client_method_names(client: MagicMock) -> list[str]:
    return [method_call[0] for method_call in client.method_calls]


class TestRegister:
    def test_registers_the_toggle_beside_the_existing_listeners(self) -> None:
        """Registration adds the toggle block action and keeps every existing listener.

        Every listener is a scope-binding wrapper around its handler, so the ids
        are asserted and the toggle listener is called to show it reaches the
        handler.
        """
        registrar = FakeSlackRegistrar(service_scopes=incident_scopes())

        register(registrar)

        assert set(registrar.block_actions) == {
            NEW_ACTION_ID,
            REVIEW_ACTION_ID,
            OPEN_ACTION_ID,
            HISTORY_ACTION_ID,
            PUBLISHED_ACTION_ID,
            GENERATE_ACTION_ID,
            SAVE_ACTION_ID,
        }
        assert list(registrar.view_submissions) == [REVIEW_CALLBACK_ID]

    def test_registered_toggle_listener_reaches_the_toggle_handler(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """The toggle listener, called with Bolt's keyword arguments, runs the toggle handler over the registrar's scopes."""
        registrar = FakeSlackRegistrar(service_scopes=incident_scopes())
        register(registrar)

        registrar.block_actions[PUBLISHED_ACTION_ID](ack=ack, body=_toggle_body(), client=client)

        assert services.toggle_calls == [(_INCIDENT, _SEQUENCE, True, _USER)]


class TestHandlePublishedAction:
    def test_acks_then_sets_renders_and_updates(
        self, ack: MagicMock, client: MagicMock, services: _Services, events: list[str]
    ) -> None:
        """Ack comes first, then the toggle, the rendering of its record and the one view update."""
        handle_published_action(ack, _toggle_body(), client, incident_scopes())

        assert events == ["ack", "set_published", "publish", "views_update"]
        ack.assert_called_once_with()

    @pytest.mark.parametrize("published", [True, False], ids=["publish", "undo"])
    def test_sets_the_target_state_with_the_presser_as_actor(
        self, ack: MagicMock, client: MagicMock, services: _Services, published: bool
    ) -> None:
        """The service gets the incident, sequence and target state from the button and the pressing user's id."""
        handle_published_action(ack, _toggle_body(_target(published)), client, incident_scopes())

        assert services.toggle_calls == [(_INCIDENT, _SEQUENCE, published, _USER)]
        assert len(services.stores) == 1 and isinstance(services.stores[0], StatusUpdateStore)

    def test_renders_the_returned_record_with_both_label_sets(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """The record the toggle returned is rendered with the English and French profile labels."""
        services.toggle_result = OperationResult.success(data=_published())

        handle_published_action(ack, _toggle_body(), client, incident_scopes())

        assert services.publish_calls == [(_published(), build_profile_labels("en-US"), build_profile_labels("fr-FR"))]

    @pytest.mark.parametrize("locale", ["en-US", "fr-FR"])
    def test_replaces_the_modal_with_the_record_s_copy_ready_view(
        self, ack: MagicMock, client: MagicMock, services: _Services, locale: str
    ) -> None:
        """One views_update by view id and hash shows the copy-ready view of the returned record, keeping the metadata."""
        services.toggle_result = OperationResult.success(data=_published())

        handle_published_action(ack, _toggle_body(view=_view(locale)), client, incident_scopes())

        assert client.views_update.call_args_list == [
            call(
                view_id=_VIEW_ID,
                hash=_VIEW_HASH,
                view=build_copy_ready_view(_COPY, locale, _metadata(locale), update=_published()),
            )
        ]

    def test_without_a_hash_updates_by_view_id_only(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """A payload without a view hash updates the modal by view id alone, as the other listeners do."""
        handle_published_action(
            ack, _toggle_body(view={"id": _VIEW_ID, "private_metadata": _metadata()}), client, incident_scopes()
        )

        assert client.views_update.call_args_list == [
            call(view_id=_VIEW_ID, view=build_copy_ready_view(_COPY, "en-US", _metadata(), update=_APPROVED))
        ]

    @pytest.mark.parametrize(
        "result",
        [
            OperationResult.permanent_error(message="changed", error_code=ErrorCode.STATUS_UPDATE_CONFLICT),
            OperationResult.permanent_error(message="draft", error_code=ErrorCode.STATUS_UPDATE_NOT_APPROVED),
            OperationResult.transient_error(message="store throttled", error_code=ErrorCode.RATE_LIMITED),
        ],
        ids=["conflict", "not-approved", "store-error"],
    )
    def test_toggle_failure_shows_the_error_view_without_rendering(
        self, ack: MagicMock, client: MagicMock, services: _Services, result: OperationResult[StatusUpdate]
    ) -> None:
        """A refused toggle is not rendered; the modal shows the Close-only toggle error view for its code."""
        services.toggle_result = result

        handle_published_action(ack, _toggle_body(), client, incident_scopes())

        assert services.publish_calls == []
        assert client.views_update.call_args_list == [
            call(view_id=_VIEW_ID, hash=_VIEW_HASH, view=build_published_error_view(result.error_code, "en-US", _metadata()))
        ]

    def test_publish_failure_shows_the_error_view(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """A publisher refusal after a successful toggle shows the error view for the publisher's code."""
        services.publish_result = OperationResult.permanent_error(
            message="not approved", error_code=ErrorCode.STATUS_UPDATE_NOT_APPROVED
        )

        handle_published_action(ack, _toggle_body(), client, incident_scopes())

        assert client.views_update.call_args_list == [
            call(
                view_id=_VIEW_ID,
                hash=_VIEW_HASH,
                view=build_published_error_view(ErrorCode.STATUS_UPDATE_NOT_APPROVED, "en-US", _metadata()),
            )
        ]

    @pytest.mark.parametrize(
        "value",
        [
            json.dumps({"incident_id": _INCIDENT, "published": True}),
            json.dumps({"incident_id": _INCIDENT, "sequence": _SEQUENCE}),
            json.dumps({"incident_id": _INCIDENT, "sequence": _SEQUENCE, "published": "yes"}),
            "not json",
        ],
        ids=["no-sequence", "no-target", "non-boolean-target", "malformed"],
    )
    def test_unreadable_value_shows_the_error_view_without_toggling(
        self, ack: MagicMock, client: MagicMock, services: _Services, value: str
    ) -> None:
        """A value without an integer sequence and a boolean target changes nothing and shows the generic error view."""
        handle_published_action(ack, _toggle_body(value), client, incident_scopes())

        assert services.toggle_calls == []
        assert client.views_update.call_args_list == [
            call(view_id=_VIEW_ID, hash=_VIEW_HASH, view=build_published_error_view(None, "en-US", _metadata()))
        ]

    def test_toggle_failure_is_logged(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """A refused toggle is logged once as a warning carrying its error code."""
        services.toggle_result = OperationResult.permanent_error(message="x", error_code=ErrorCode.STATUS_UPDATE_CONFLICT)

        with capture_logs() as logs:
            handle_published_action(ack, _toggle_body(), client, incident_scopes())

        failures = [entry for entry in logs if entry["event"] == "incident_status_update_published_failed"]
        assert [(entry["log_level"], entry["error_code"]) for entry in failures] == [
            ("warning", ErrorCode.STATUS_UPDATE_CONFLICT)
        ]

    def test_slack_failure_is_logged_not_raised(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """A views_update exception is logged as one warning and the listener returns normally."""
        client.views_update.side_effect = RuntimeError("view_not_found")

        with capture_logs() as logs:
            handle_published_action(ack, _toggle_body(), client, incident_scopes())

        failures = [entry for entry in logs if entry["event"] == "incident_status_update_published_update_failed"]
        assert [entry["log_level"] for entry in failures] == ["warning"]

    def test_only_updates_the_view(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """The only Slack call is views_update: nothing is posted to the incident channel."""
        handle_published_action(ack, _toggle_body(), client, incident_scopes())

        assert _client_method_names(client) == ["views_update"]


class TestHandlePublishedActionOverRealServices:
    def test_one_transition_and_the_view_shows_the_published_record(
        self, monkeypatch: pytest.MonkeyPatch, ack: MagicMock, client: MagicMock
    ) -> None:
        """Over the real toggle and copy-ready publisher, the one record write is the transition to published.

        The shown view is the copy-ready view of the stored published record,
        so it carries the presser as publisher and offers Mark as not published.
        """
        records = CountingRecordStore()
        store = status_update_store_in(records)
        store.append(_APPROVED)
        records.writes.clear()
        monkeypatch.setattr(history, "set_published", partial(set_published, now=_NOW))
        monkeypatch.setattr(providers, "get_status_page_publisher", CopyReadyPublisher)

        handle_published_action(ack, _toggle_body(_target(True)), client, incident_scopes(records))

        copy = render_copy_ready(_published(), build_profile_labels("en-US"), build_profile_labels("fr-FR"))
        assert records.writes == ["update"]
        assert store.latest(_INCIDENT).data == _published()
        assert client.views_update.call_args_list == [
            call(view_id=_VIEW_ID, hash=_VIEW_HASH, view=build_copy_ready_view(copy, "en-US", _metadata(), update=_published()))
        ]
