"""Tests for the Review button and approval submission listeners of the status-updates modal.

The Review listener acks, reads the draft named by the button's value and
replaces the modal in place with the review view, or with a review error view.
The submission listener validates the parsed edit and acks with field errors,
or acks with the saving view, approves the draft and renders its copy-ready
text, then updates the modal by view id. Slack failures are logged, never
raised, and nothing is posted to a channel.

The service boundary is stubbed with recording fakes: ``get_draft_for_review``
and ``approve_status_update`` in the entrypoint module's namespace and the
publisher returned by ``providers.get_status_page_publisher``. The pure
``StatusUpdateEdit.blank_fields`` runs for real. Expected views are built with the
platform view builders, so each assertion compares the exact view sent.
"""

import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, call

import pytest
from structlog.testing import capture_logs

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from features.incident.comms import approval, form, providers
from features.incident.comms.comms_profile import ProfileLabels
from features.incident.comms.domain import CopyReadyText, StatusUpdateEdit
from features.incident.comms.entrypoints.slack import (
    handle_generate_action,
    handle_history_action,
    handle_new_update_action,
    handle_open_action,
    handle_published_action,
    handle_review_action,
    handle_review_submission,
    handle_save_action,
    register,
)
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
    build_review_error_view,
    build_review_field_errors,
    build_review_view,
    build_saving_view,
)
from features.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from tests.factories.slack import FakeSlackRegistrar

pytestmark = pytest.mark.unit

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_USER = "U0APPROVER"
_SEQUENCE = 3
_VIEW_ID = "V456"
_VIEW_HASH = "hash123=="
_REVIEW_VIEW_ID = "VREVIEW"
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_FIELDS = ("affected_service", "impact", "current_action", "workaround")
_FIELD_BLOCK_IDS = tuple(f"{language}.{name}" for language in ("en", "fr") for name in _FIELDS)
_COPY = CopyReadyText(en="Stage: Monitoring\n\nImpact: edited", fr="Étape : Surveillance\n\nIncidence : modifiée")


def _text(language: str, prefix: str = "") -> StatusUpdateText:
    return StatusUpdateText(
        affected_service=f"{prefix}{language} service",
        impact=f"{prefix}{language} impact",
        current_action=f"{prefix}{language} action",
        workaround=f"{prefix}{language} workaround",
    )


_DRAFT = StatusUpdate(
    incident_id=_INCIDENT,
    sequence=_SEQUENCE,
    state=StatusUpdateState.DRAFT,
    stage=StatusUpdateStage.IDENTIFIED,
    en=_text("en"),
    fr=_text("fr"),
    next_update_at=_NOW,
    author="U999",
    transcript_cutoff=_NOW,
    transcript_fingerprint="v1:sha256:abc123",
    created_at=_NOW,
)
_EDIT = StatusUpdateEdit(stage=StatusUpdateStage.MONITORING, en=_text("en", "edited "), fr=_text("fr", "edited "))
_APPROVED = replace(
    _DRAFT,
    state=StatusUpdateState.APPROVED,
    stage=_EDIT.stage,
    en=_EDIT.en,
    fr=_EDIT.fr,
    approver=_USER,
    approved_at=_NOW,
)


@dataclass
class _Services:
    """Recording fakes for the review service, the approval service and the publisher.

    Every call appends its name to the shared ``events`` log, which the ack and
    the Slack client also write to, so tests can assert call order.
    """

    events: list[str]
    review_result: OperationResult[StatusUpdate] = field(default_factory=lambda: OperationResult.success(data=_DRAFT))
    approve_result: OperationResult[StatusUpdate] = field(default_factory=lambda: OperationResult.success(data=_APPROVED))
    publish_result: OperationResult[CopyReadyText] = field(default_factory=lambda: OperationResult.success(data=_COPY))
    review_calls: list[tuple[str, int]] = field(default_factory=list)
    approve_calls: list[tuple[str, int, str, StatusUpdateEdit]] = field(default_factory=list)
    publish_calls: list[tuple[StatusUpdate, ProfileLabels, ProfileLabels]] = field(default_factory=list)

    async def get_draft_for_review(self, incident_id: str, sequence: int) -> OperationResult[StatusUpdate]:
        self.events.append("get_draft_for_review")
        self.review_calls.append((incident_id, sequence))
        return self.review_result

    async def approve_status_update(
        self, incident_id: str, sequence: int, *, approver: str, edit: StatusUpdateEdit
    ) -> OperationResult[StatusUpdate]:
        self.events.append("approve_status_update")
        self.approve_calls.append((incident_id, sequence, approver, edit))
        return self.approve_result

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
    monkeypatch.setattr(form, "get_draft_for_review", fakes.get_draft_for_review)
    monkeypatch.setattr(approval, "approve_status_update", fakes.approve_status_update)
    monkeypatch.setattr(providers, "get_status_page_publisher", lambda: fakes)
    monkeypatch.setattr(form, "text_generation_available", lambda: True)
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


def _review_metadata(locale: str = "en-US") -> str:
    return json.dumps({"channel_id": _CHANNEL, "locale": locale, "incident_id": _INCIDENT, "sequence": _SEQUENCE})


def _review_action_body(locale: str = "en-US") -> dict[str, Any]:
    """A block_actions body for the Review button pressed in the status-updates modal."""
    return {
        "type": "block_actions",
        "user": {"id": _USER},
        "trigger_id": "trigger-123",
        "view": {
            "id": _VIEW_ID,
            "hash": _VIEW_HASH,
            "private_metadata": json.dumps({"channel_id": _CHANNEL, "locale": locale}),
        },
        "actions": [
            {
                "action_id": REVIEW_ACTION_ID,
                "block_id": "overview_actions",
                "type": "button",
                "value": json.dumps({"incident_id": _INCIDENT, "sequence": _SEQUENCE}),
            }
        ],
    }


def _submission_body(
    edit: StatusUpdateEdit = _EDIT,
    *,
    stage_value: str | None = None,
    values: dict[str, str | None] | None = None,
    locale: str = "en-US",
) -> dict[str, Any]:
    """A view_submission body for the review modal, filled from ``edit`` with optional overrides."""
    stage = stage_value if stage_value is not None else edit.stage.value
    texts: dict[str, str | None] = {
        f"{language}.{name}": getattr(text, name) for language, text in (("en", edit.en), ("fr", edit.fr)) for name in _FIELDS
    }
    texts |= values or {}
    state: dict[str, Any] = {
        block_id: {"text": {"type": "plain_text_input", "value": value}} for block_id, value in texts.items()
    }
    state["stage"] = {
        "stage": {"type": "static_select", "selected_option": {"text": {"type": "plain_text", "text": stage}, "value": stage}}
    }
    return {
        "type": "view_submission",
        "user": {"id": _USER},
        "view": {
            "id": _REVIEW_VIEW_ID,
            "hash": "review-hash==",
            "callback_id": REVIEW_CALLBACK_ID,
            "private_metadata": _review_metadata(locale),
            "state": {"values": state},
        },
    }


def _client_method_names(client: MagicMock) -> list[str]:
    return [method_call[0] for method_call in client.method_calls]


def _sent_view(client: MagicMock) -> dict[str, Any]:
    (update,) = client.views_update.call_args_list
    view: dict[str, Any] = update.kwargs["view"]
    return view


class TestRegister:
    def test_registers_review_action_and_approval_submission(self) -> None:
        """Registration adds the Review block action and the approval view submission beside the Draft listeners."""
        registrar = FakeSlackRegistrar()

        register(registrar)

        assert registrar.block_actions == {
            NEW_ACTION_ID: handle_new_update_action,
            REVIEW_ACTION_ID: handle_review_action,
            OPEN_ACTION_ID: handle_open_action,
            HISTORY_ACTION_ID: handle_history_action,
            PUBLISHED_ACTION_ID: handle_published_action,
            GENERATE_ACTION_ID: handle_generate_action,
            SAVE_ACTION_ID: handle_save_action,
        }
        assert registrar.view_submissions == {REVIEW_CALLBACK_ID: handle_review_submission}


class TestHandleReviewAction:
    def test_acks_before_reading_the_draft(
        self, ack: MagicMock, client: MagicMock, services: _Services, events: list[str]
    ) -> None:
        """Ack comes first, then the draft read, then the one view update."""
        handle_review_action(ack, _review_action_body(), client)

        assert events == ["ack", "get_draft_for_review", "views_update"]
        ack.assert_called_once_with()

    def test_reads_the_draft_named_by_the_button(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """The service is asked for the incident id and sequence decoded from the button value."""
        handle_review_action(ack, _review_action_body(), client)

        assert services.review_calls == [(_INCIDENT, _SEQUENCE)]

    def test_replaces_the_modal_in_place_with_view_id_and_hash(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """The modal is updated by the pressed view's id and hash, so a concurrent change is not overwritten."""
        handle_review_action(ack, _review_action_body(), client)

        (update,) = client.views_update.call_args_list
        assert update.kwargs["view_id"] == _VIEW_ID
        assert update.kwargs["hash"] == _VIEW_HASH

    @pytest.mark.parametrize("locale", ["en-US", "fr-FR"])
    def test_shows_the_review_view_for_the_draft(
        self, ack: MagicMock, client: MagicMock, services: _Services, locale: str
    ) -> None:
        """The update is the review view of the returned draft in the invoker's locale."""
        handle_review_action(ack, _review_action_body(locale), client)

        view = _sent_view(client)
        assert view == build_review_view(_DRAFT, locale, view["private_metadata"])

    def test_without_text_generation_the_review_form_has_no_ai_section(
        self, ack: MagicMock, client: MagicMock, services: _Services, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With the generator unconfigured the form is built without Draft with AI; Save draft and Approve remain."""
        monkeypatch.setattr(form, "text_generation_available", lambda: False)

        handle_review_action(ack, _review_action_body(), client)

        view = _sent_view(client)
        assert view == build_review_view(_DRAFT, "en-US", view["private_metadata"], with_ai=False)

    def test_review_view_metadata_names_channel_locale_and_draft(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """The review view's metadata carries the channel, locale, incident id and sequence for the submission."""
        handle_review_action(ack, _review_action_body(), client)

        assert json.loads(_sent_view(client)["private_metadata"]) == {
            "channel_id": _CHANNEL,
            "locale": "en-US",
            "incident_id": _INCIDENT,
            "sequence": _SEQUENCE,
        }

    @pytest.mark.parametrize(
        "result",
        [
            OperationResult.permanent_error(message="no longer the draft", error_code=ErrorCode.STATUS_UPDATE_CONFLICT),
            OperationResult.transient_error(message="store throttled", error_code=ErrorCode.RATE_LIMITED),
        ],
        ids=["conflict", "store-error"],
    )
    def test_failure_shows_the_review_error_view(
        self, ack: MagicMock, client: MagicMock, services: _Services, result: OperationResult[StatusUpdate]
    ) -> None:
        """A conflict or store error replaces the modal with the review error view for that code."""
        services.review_result = result

        handle_review_action(ack, _review_action_body(), client)

        view = _sent_view(client)
        assert view == build_review_error_view(result.error_code, "en-US", view["private_metadata"])
        metadata = json.loads(view["private_metadata"])
        assert (metadata["channel_id"], metadata["locale"]) == (_CHANNEL, "en-US")

    def test_slack_failure_is_logged_not_raised(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """A views.update exception is logged as one warning and the listener returns normally."""
        client.views_update.side_effect = RuntimeError("view_not_found")

        with capture_logs() as logs:
            handle_review_action(ack, _review_action_body(), client)

        failures = [entry for entry in logs if entry["event"] == "incident_status_update_review_update_failed"]
        assert [entry["log_level"] for entry in failures] == ["warning"]

    def test_only_updates_the_view(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """The only Slack call is views_update: nothing is posted to a channel."""
        handle_review_action(ack, _review_action_body(), client)

        assert _client_method_names(client) == ["views_update"]


class TestHandleReviewSubmissionRejected:
    def test_unparseable_stage_acks_a_stage_error(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """An unknown stage acks with an error on the stage block, and nothing else happens."""
        handle_review_submission(ack, _submission_body(stage_value="not-a-stage"), client)

        assert ack.call_args_list == [call(response_action="errors", errors=build_review_field_errors(("stage",), "en-US"))]
        assert services.approve_calls == []
        assert client.method_calls == []

    @pytest.mark.parametrize("value", ["", "   ", None], ids=["empty", "whitespace", "null"])
    @pytest.mark.parametrize("block_id", _FIELD_BLOCK_IDS)
    def test_blank_field_acks_its_error(
        self, ack: MagicMock, client: MagicMock, services: _Services, block_id: str, value: str | None
    ) -> None:
        """A blank field acks with an error keyed by its block id only."""
        handle_review_submission(ack, _submission_body(values={block_id: value}), client)

        assert ack.call_args_list == [call(response_action="errors", errors=build_review_field_errors((block_id,), "en-US"))]

    @pytest.mark.parametrize("block_id", _FIELD_BLOCK_IDS)
    def test_blank_field_does_not_call_the_service_or_slack(
        self, ack: MagicMock, client: MagicMock, services: _Services, block_id: str
    ) -> None:
        """A blank field is rejected before approval and before any Slack call."""
        handle_review_submission(ack, _submission_body(values={block_id: " "}), client)

        assert services.approve_calls == []
        assert services.publish_calls == []
        assert client.method_calls == []

    def test_every_blank_field_is_reported_at_once(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """Several blank fields are reported together in validation order."""
        handle_review_submission(ack, _submission_body(values={"fr.workaround": "", "en.impact": ""}), client)

        assert ack.call_args_list == [
            call(response_action="errors", errors=build_review_field_errors(("en.impact", "fr.workaround"), "en-US"))
        ]

    def test_field_errors_use_the_metadata_locale(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """Field error messages are in the locale recorded in the review view's metadata."""
        handle_review_submission(ack, _submission_body(values={"en.impact": ""}, locale="fr-FR"), client)

        assert ack.call_args_list == [call(response_action="errors", errors=build_review_field_errors(("en.impact",), "fr-FR"))]


class TestHandleReviewSubmissionApproved:
    def test_acks_with_the_saving_view(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """A valid submission acks once, replacing the form with the saving view."""
        handle_review_submission(ack, _submission_body(), client)

        assert ack.call_args_list == [call(response_action="update", view=build_saving_view("en-US", _review_metadata()))]

    def test_approves_with_the_approver_and_parsed_edit(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """Approval gets the draft named in the metadata, the submitting user and the submitted edit."""
        handle_review_submission(ack, _submission_body(), client)

        assert services.approve_calls == [(_INCIDENT, _SEQUENCE, _USER, _EDIT)]

    def test_publishes_the_approved_record_with_both_label_sets(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """The approved record, not the draft, is rendered with the English and French profile labels."""
        handle_review_submission(ack, _submission_body(), client)

        assert services.publish_calls == [(_APPROVED, build_profile_labels("en-US"), build_profile_labels("fr-FR"))]
        assert services.publish_calls[0][0] is services.approve_result.data

    def test_shows_the_copy_ready_view_by_view_id_without_hash(
        self, ack: MagicMock, client: MagicMock, services: _Services
    ) -> None:
        """The submitted view is updated by id alone to the copy-ready view of the published text."""
        handle_review_submission(ack, _submission_body(), client)

        assert client.views_update.call_args_list == [
            call(view_id=_REVIEW_VIEW_ID, view=build_copy_ready_view(_COPY, "en-US", _review_metadata()))
        ]

    def test_ack_precedes_approval_and_publish_precedes_the_update(
        self, ack: MagicMock, client: MagicMock, services: _Services, events: list[str]
    ) -> None:
        """The ack is sent inside Slack's window, before the service runs; the view update comes last."""
        handle_review_submission(ack, _submission_body(), client)

        assert events == ["ack", "approve_status_update", "publish", "views_update"]

    @pytest.mark.parametrize(
        "result",
        [
            OperationResult.permanent_error(message="blank", error_code=ErrorCode.STATUS_UPDATE_FIELDS_INVALID),
            OperationResult.permanent_error(message="below floor", error_code=ErrorCode.STATUS_UPDATE_STAGE_BELOW_FLOOR),
            OperationResult.permanent_error(message="conflict", error_code=ErrorCode.STATUS_UPDATE_CONFLICT),
            OperationResult.transient_error(message="store throttled", error_code=ErrorCode.RATE_LIMITED),
        ],
        ids=["fields-invalid", "stage-below-floor", "conflict", "store-error"],
    )
    def test_approval_refusal_shows_the_review_error_view(
        self, ack: MagicMock, client: MagicMock, services: _Services, result: OperationResult[StatusUpdate]
    ) -> None:
        """A refused approval is not published; the modal shows the review error view for its code."""
        services.approve_result = result

        handle_review_submission(ack, _submission_body(), client)

        assert services.publish_calls == []
        assert client.views_update.call_args_list == [
            call(view_id=_REVIEW_VIEW_ID, view=build_review_error_view(result.error_code, "en-US", _review_metadata()))
        ]

    def test_publish_failure_shows_the_review_error_view(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """A publisher refusal after approval shows the review error view for its code."""
        services.publish_result = OperationResult.permanent_error(
            message="not approved", error_code=ErrorCode.STATUS_UPDATE_NOT_APPROVED
        )

        handle_review_submission(ack, _submission_body(), client)

        assert client.views_update.call_args_list == [
            call(
                view_id=_REVIEW_VIEW_ID,
                view=build_review_error_view(ErrorCode.STATUS_UPDATE_NOT_APPROVED, "en-US", _review_metadata()),
            )
        ]

    def test_slack_failure_is_logged_not_raised(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """A views.update exception after approval is logged as one warning and the listener returns normally."""
        client.views_update.side_effect = RuntimeError("view_not_found")

        with capture_logs() as logs:
            handle_review_submission(ack, _submission_body(), client)

        failures = [entry for entry in logs if entry["event"] == "incident_status_update_approval_update_failed"]
        assert [entry["log_level"] for entry in failures] == ["warning"]

    def test_only_updates_the_view(self, ack: MagicMock, client: MagicMock, services: _Services) -> None:
        """The only Slack call is views_update: the approved text is never posted to a channel."""
        handle_review_submission(ack, _submission_body(), client)

        assert _client_method_names(client) == ["views_update"]
