"""Dispatching the Open and Back buttons of the status-updates modal through a real Bolt app.

The real ``packages.incident.scribe`` plugin is registered on a real pluggy
PluginManager under its entry-point name ``incident.scribe``, so booting the
harness proves the Open and Back action ids pass the provider's plugin-prefix
check. Payloads are form-encoded as Slack posts them and fed to
``App.dispatch`` with listeners run inline. Only two edges are stubbed:
``WebClient.api_call`` records Web API calls, and the service boundary
(``get_approved_update`` and ``get_status_update_overview`` in the entrypoint
module, the publisher from ``providers.get_status_page_publisher``) is replaced
by module-level recording fakes that return real ``OperationResult`` values.
Assertions read the HTTP status Bolt returns and the exact Web API calls made,
which must be one ``views.update`` and nothing posted to a channel.
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
from packages.incident.scribe.domain import CopyReadyText, StatusUpdateOverview
from packages.incident.scribe.entrypoints import slack as slack_entrypoints
from packages.incident.scribe.platforms.slack import (
    HISTORY_ACTION_ID,
    OPEN_ACTION_ID,
    build_copy_ready_view,
    build_overview_view,
    build_profile_labels,
)
from tests.factories.slack_bolt import TRIGGER_ID, Harness, harness_fixture

pytestmark = pytest.mark.integration

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C0INCIDENT"
_SEQUENCE = 2
_VIEW_ID = "V0STATUS"
_VIEW_HASH = "status-hash=="
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_METADATA = json.dumps({"channel_id": _CHANNEL, "locale": "en-US"})
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
_PUBLISHED = replace(_APPROVED, sequence=1, state=StatusUpdateState.PUBLISHED, published_at=_NOW)
_OVERVIEW = StatusUpdateOverview(pending=None, approved=(_APPROVED, _PUBLISHED))


@dataclass
class ServiceFakes:
    """Recording fakes for the scribe service boundary, answering with successful results."""

    approved_calls: list[tuple[str, int]] = field(default_factory=list)
    overview_calls: list[str] = field(default_factory=list)
    publish_calls: list[tuple[StatusUpdate, ProfileLabels, ProfileLabels]] = field(default_factory=list)

    async def get_approved_update(self, incident_id: str, sequence: int) -> OperationResult[StatusUpdate]:
        self.approved_calls.append((incident_id, sequence))
        return OperationResult.success(data=_APPROVED)

    def get_status_update_overview(self, conversation_id: str) -> OperationResult[StatusUpdateOverview]:
        self.overview_calls.append(conversation_id)
        return OperationResult.success(data=_OVERVIEW)

    async def publish(
        self, update: StatusUpdate, *, labels_en: ProfileLabels, labels_fr: ProfileLabels
    ) -> OperationResult[CopyReadyText]:
        self.publish_calls.append((update, labels_en, labels_fr))
        return OperationResult.success(data=_COPY)


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> ServiceFakes:
    service_fakes = ServiceFakes()
    monkeypatch.setattr(slack_entrypoints, "get_approved_update", service_fakes.get_approved_update)
    monkeypatch.setattr(slack_entrypoints, "get_status_update_overview", service_fakes.get_status_update_overview)
    monkeypatch.setattr(providers, "get_status_page_publisher", lambda: service_fakes)
    return service_fakes


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch, fakes: ServiceFakes) -> Iterator[Harness]:
    yield from harness_fixture("incident.scribe")(monkeypatch, scribe_module)


def _button_action(action_id: str, value: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "block_actions",
        "trigger_id": TRIGGER_ID,
        "view": {"id": _VIEW_ID, "hash": _VIEW_HASH, "type": "modal", "private_metadata": _METADATA},
        "actions": [{"action_id": action_id, "block_id": "any", "type": "button", "value": json.dumps(value)}],
    }


def _open_action() -> dict[str, Any]:
    return _button_action(OPEN_ACTION_ID, {"incident_id": _INCIDENT, "sequence": _SEQUENCE})


def _back_action() -> dict[str, Any]:
    return _button_action(HISTORY_ACTION_ID, {"channel_id": _CHANNEL})


def test_open_is_acked(harness: Harness) -> None:
    """Bolt routes the Open press to the plugin's listener and acks it with HTTP 200."""
    response = harness.dispatch(_open_action())

    assert response.status == 200


def test_open_reads_and_renders_the_named_update(harness: Harness, fakes: ServiceFakes) -> None:
    """The Open listener reads the update named by the button and renders it with both label sets."""
    harness.dispatch(_open_action())

    assert fakes.approved_calls == [(_INCIDENT, _SEQUENCE)]
    assert fakes.publish_calls == [(_APPROVED, build_profile_labels("en-US"), build_profile_labels("fr-FR"))]


def test_open_updates_the_modal_once_in_place(harness: Harness) -> None:
    """The only Web API call is one views.update, by view id and hash, to the reopened copy-ready view."""
    harness.dispatch(_open_action())

    assert harness.api_calls == [
        (
            "views.update",
            {
                "view_id": _VIEW_ID,
                "hash": _VIEW_HASH,
                "view": build_copy_ready_view(_COPY, "en-US", _METADATA, update=_APPROVED),
            },
        )
    ]


def test_back_is_acked(harness: Harness) -> None:
    """Bolt routes the Back press to the plugin's listener and acks it with HTTP 200."""
    response = harness.dispatch(_back_action())

    assert response.status == 200


def test_back_reads_the_channel_overview(harness: Harness, fakes: ServiceFakes) -> None:
    """The Back listener reads the overview for the channel named by the button, and renders nothing."""
    harness.dispatch(_back_action())

    assert fakes.overview_calls == [_CHANNEL]
    assert fakes.publish_calls == []


def test_back_updates_the_modal_once_in_place(harness: Harness) -> None:
    """The only Web API call is one views.update, by view id and hash, to the approved-updates list."""
    harness.dispatch(_back_action())

    assert harness.api_calls == [
        (
            "views.update",
            {"view_id": _VIEW_ID, "hash": _VIEW_HASH, "view": build_overview_view(_OVERVIEW, "en-US", _METADATA)},
        )
    ]
