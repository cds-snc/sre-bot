"""Dispatching the Review button and the approval submission through a real Bolt app.

The real ``packages.incident.scribe`` plugin is registered on a real pluggy
PluginManager under its entry-point name ``incident.scribe``, so booting the
harness proves its action and callback ids pass the provider's plugin-prefix
check. Payloads are form-encoded as Slack posts them and fed to ``App.dispatch``
with listeners run inline. Only two edges are stubbed: ``WebClient.api_call``
records Web API calls, and the service boundary (``get_draft_for_review`` and
``approve_status_update`` in the entrypoint module, the publisher from
``providers.get_status_page_publisher``) is replaced by recording fakes that
return real ``OperationResult`` values. Assertions read the ack body Bolt
returns and the exact Web API calls the listeners made.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

import pytest

import packages.incident.scribe as scribe_module
from contracts.operations import OperationResult
from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from packages.incident.scribe import providers
from packages.incident.scribe.comms_profile import ProfileLabels
from packages.incident.scribe.domain import CopyReadyText, StatusUpdateEdit
from packages.incident.scribe.entrypoints import slack as slack_entrypoints
from packages.incident.scribe.platforms.slack import (
    REVIEW_ACTION_ID,
    REVIEW_CALLBACK_ID,
    build_copy_ready_view,
    build_review_field_errors,
    build_saving_view,
)
from tests.factories.slack_bolt import TRIGGER_ID, USER_ID, Harness, harness_fixture

pytestmark = pytest.mark.integration

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C0INCIDENT"
_SEQUENCE = 2
_VIEW_ID = "V0STATUS"
_VIEW_HASH = "status-hash=="
_REVIEW_VIEW_ID = "V0REVIEW"
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_FIELDS = ("affected_service", "impact", "current_action", "workaround")
_REVIEW_METADATA = json.dumps({"channel_id": _CHANNEL, "locale": "en-US", "incident_id": _INCIDENT, "sequence": _SEQUENCE})
_COPY = CopyReadyText(en="Stage: Resolved\n\nImpact: none", fr="Étape : Résolu\n\nIncidence : aucune")


def _text(language: str) -> StatusUpdateText:
    return StatusUpdateText(
        affected_service=f"{language} service",
        impact=f"{language} impact",
        current_action=f"{language} action",
        workaround=f"{language} workaround",
    )


_DRAFT = StatusUpdate(
    incident_id=_INCIDENT,
    sequence=_SEQUENCE,
    state=StatusUpdateState.DRAFT,
    stage=StatusUpdateStage.MONITORING,
    en=_text("en"),
    fr=_text("fr"),
    next_update_at=_NOW,
    author="U999",
    transcript_cutoff=_NOW,
    transcript_fingerprint="v1:sha256:abc123",
    created_at=_NOW,
)
_EDIT = StatusUpdateEdit(stage=StatusUpdateStage.RESOLVED, en=_text("en"), fr=_text("fr"))
_APPROVED = replace(_DRAFT, state=StatusUpdateState.APPROVED, stage=_EDIT.stage, approver=USER_ID, approved_at=_NOW)


@dataclass
class ServiceFakes:
    """Recording fakes for the scribe service boundary, answering with successful results."""

    review_calls: list[tuple[str, int]] = field(default_factory=list)
    approve_calls: list[tuple[str, int, str, StatusUpdateEdit]] = field(default_factory=list)
    publish_calls: list[tuple[StatusUpdate, ProfileLabels, ProfileLabels]] = field(default_factory=list)

    async def get_draft_for_review(self, incident_id: str, sequence: int) -> OperationResult[StatusUpdate]:
        self.review_calls.append((incident_id, sequence))
        return OperationResult.success(data=_DRAFT)

    async def approve_status_update(
        self, incident_id: str, sequence: int, *, approver: str, edit: StatusUpdateEdit
    ) -> OperationResult[StatusUpdate]:
        self.approve_calls.append((incident_id, sequence, approver, edit))
        return OperationResult.success(data=_APPROVED)

    async def publish(
        self, update: StatusUpdate, *, labels_en: ProfileLabels, labels_fr: ProfileLabels
    ) -> OperationResult[CopyReadyText]:
        self.publish_calls.append((update, labels_en, labels_fr))
        return OperationResult.success(data=_COPY)


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> ServiceFakes:
    service_fakes = ServiceFakes()
    monkeypatch.setattr(slack_entrypoints, "get_draft_for_review", service_fakes.get_draft_for_review)
    monkeypatch.setattr(slack_entrypoints, "approve_status_update", service_fakes.approve_status_update)
    monkeypatch.setattr(providers, "get_status_page_publisher", lambda: service_fakes)
    return service_fakes


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch, fakes: ServiceFakes) -> Iterator[Harness]:
    yield from harness_fixture("incident.scribe")(monkeypatch, scribe_module)


def _review_action() -> dict[str, Any]:
    return {
        "type": "block_actions",
        "trigger_id": TRIGGER_ID,
        "view": {
            "id": _VIEW_ID,
            "hash": _VIEW_HASH,
            "type": "modal",
            "private_metadata": json.dumps({"channel_id": _CHANNEL, "locale": "en-US"}),
        },
        "actions": [
            {
                "action_id": REVIEW_ACTION_ID,
                "block_id": "draft_button",
                "type": "button",
                "value": json.dumps({"incident_id": _INCIDENT, "sequence": _SEQUENCE}),
            }
        ],
    }


def _submission(**overrides: str) -> dict[str, Any]:
    texts = {
        f"{language}.{name}": getattr(text, name) for language, text in (("en", _EDIT.en), ("fr", _EDIT.fr)) for name in _FIELDS
    }
    texts |= overrides
    values: dict[str, Any] = {
        block_id: {"text": {"type": "plain_text_input", "value": value}} for block_id, value in texts.items()
    }
    stage = _EDIT.stage.value
    values["stage"] = {
        "stage": {"type": "static_select", "selected_option": {"text": {"type": "plain_text", "text": stage}, "value": stage}}
    }
    return {
        "type": "view_submission",
        "trigger_id": TRIGGER_ID,
        "view": {
            "id": _REVIEW_VIEW_ID,
            "hash": "review-hash==",
            "type": "modal",
            "callback_id": REVIEW_CALLBACK_ID,
            "private_metadata": _REVIEW_METADATA,
            "state": {"values": values},
        },
    }


def test_review_action_updates_the_modal_once_in_place(harness: Harness, fakes: ServiceFakes) -> None:
    """The Review press is acked and makes exactly one views.update, by view id and hash, to the review view."""
    response = harness.dispatch(_review_action())

    assert response.status == 200
    assert fakes.review_calls == [(_INCIDENT, _SEQUENCE)]
    ((method, payload),) = harness.api_calls
    assert method == "views.update"
    assert (payload["view_id"], payload["hash"]) == (_VIEW_ID, _VIEW_HASH)
    assert payload["view"]["callback_id"] == REVIEW_CALLBACK_ID


def test_blank_field_submission_acks_errors_without_approving(harness: Harness, fakes: ServiceFakes) -> None:
    """A blank field acks with response_action errors keyed by its block id; nothing is approved or called."""
    response = harness.dispatch(_submission(**{"fr.current_action": "  "}))

    assert response.status == 200
    assert json.loads(response.body) == {
        "response_action": "errors",
        "errors": build_review_field_errors(("fr.current_action",), "en-US"),
    }
    assert fakes.approve_calls == []
    assert harness.api_calls == []


def test_valid_submission_acks_the_saving_view(harness: Harness) -> None:
    """A valid submission acks with response_action update carrying the saving view."""
    response = harness.dispatch(_submission())

    assert response.status == 200
    assert json.loads(response.body) == {
        "response_action": "update",
        "view": build_saving_view("en-US", _REVIEW_METADATA),
    }


def test_valid_submission_approves_as_the_submitting_user(harness: Harness, fakes: ServiceFakes) -> None:
    """Approval gets the draft from the metadata, Slack's submitting user and the submitted edit."""
    harness.dispatch(_submission())

    assert fakes.approve_calls == [(_INCIDENT, _SEQUENCE, USER_ID, _EDIT)]
    assert [update for update, _, _ in fakes.publish_calls] == [_APPROVED]


def test_valid_submission_shows_the_copy_ready_view(harness: Harness) -> None:
    """After approval the only Web API call is one views.update, by id without hash, to the copy-ready view."""
    harness.dispatch(_submission())

    assert harness.api_calls == [
        ("views.update", {"view_id": _REVIEW_VIEW_ID, "view": build_copy_ready_view(_COPY, "en-US", _REVIEW_METADATA)})
    ]
