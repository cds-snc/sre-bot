"""Dispatching the published toggle of the status-updates modal through a real Bolt app.

The real ``features.incident.scribe`` plugin is registered on a real pluggy
PluginManager under its entry-point name ``incident.scribe``, so booting the
harness proves the toggle's action id passes the provider's plugin-prefix
check. Payloads are form-encoded as Slack posts them and fed to
``App.dispatch`` with listeners run inline; the harness sends every payload as
user ``USER_ID``. Only edges are stubbed: ``WebClient.api_call`` records Web API
calls, and the entrypoint's ``set_published`` is the real service bound to a
core ``InMemoryStatusUpdateStore`` and a fixed ``now``. The publisher is the real
copy-ready one. Assertions read the HTTP status Bolt returns, the exact Web API
calls made (one ``views.update`` and nothing posted to a channel) and the record
left in the store.
"""

import json
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from functools import partial
from typing import Any

import pytest

import features.incident.scribe as scribe_module
from features.incident.core.adapters.in_memory import InMemoryStatusUpdateStore
from features.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from features.incident.scribe import providers
from features.incident.scribe.adapters.copy_ready import CopyReadyPublisher
from features.incident.scribe.entrypoints import slack as slack_entrypoints
from features.incident.scribe.entrypoints.slack_views import (
    PUBLISHED_ACTION_ID,
    build_copy_ready_view,
    build_profile_labels,
)
from features.incident.scribe.publisher import render_copy_ready
from features.incident.scribe.status_update_history import set_published
from tests.factories.slack_bolt import TRIGGER_ID, USER_ID, Harness, harness_fixture

pytestmark = pytest.mark.integration

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C0INCIDENT"
_SEQUENCE = 2
_VIEW_ID = "V0STATUS"
_VIEW_HASH = "status-hash=="
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_METADATA = json.dumps({"channel_id": _CHANNEL, "locale": "en-US"})


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
    approver="U0FIRST",
    approved_at=_NOW,
)


def _published() -> StatusUpdate:
    """The approved update as stored once the harness user marked it published at ``_NOW``."""
    return replace(_APPROVED, state=StatusUpdateState.PUBLISHED, published_at=_NOW, published_by=USER_ID)


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> InMemoryStatusUpdateStore:
    status_updates = InMemoryStatusUpdateStore()
    monkeypatch.setattr(slack_entrypoints, "set_published", partial(set_published, now=_NOW, store=status_updates))
    monkeypatch.setattr(providers, "get_status_page_publisher", CopyReadyPublisher)
    return status_updates


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch, store: InMemoryStatusUpdateStore) -> Iterator[Harness]:
    yield from harness_fixture("incident.scribe")(monkeypatch, scribe_module)


def _toggle_action(*, published: bool) -> dict[str, Any]:
    value = json.dumps({"incident_id": _INCIDENT, "sequence": _SEQUENCE, "published": published})
    return {
        "type": "block_actions",
        "trigger_id": TRIGGER_ID,
        "view": {"id": _VIEW_ID, "hash": _VIEW_HASH, "type": "modal", "private_metadata": _METADATA},
        "actions": [{"action_id": PUBLISHED_ACTION_ID, "block_id": "approved_status", "type": "button", "value": value}],
    }


def _copy_ready_view(update: StatusUpdate) -> dict[str, Any]:
    copy = render_copy_ready(update, build_profile_labels("en-US"), build_profile_labels("fr-FR"))
    return build_copy_ready_view(copy, "en-US", _METADATA, update=update)


def test_toggle_is_acked(harness: Harness, store: InMemoryStatusUpdateStore) -> None:
    """Bolt routes the toggle press to the plugin's listener and acks it with HTTP 200."""
    store.append(_APPROVED)

    response = harness.dispatch(_toggle_action(published=True))

    assert response.status == 200


def test_publish_stores_the_presser_and_time(harness: Harness, store: InMemoryStatusUpdateStore) -> None:
    """Marking an approved update published leaves it published by the pressing user at the fixed time."""
    store.append(_APPROVED)

    harness.dispatch(_toggle_action(published=True))

    assert store.latest(_INCIDENT).data == _published()


def test_publish_updates_the_modal_once_in_place(harness: Harness, store: InMemoryStatusUpdateStore) -> None:
    """The only Web API call is one views.update, by view id and hash, to the published record's copy-ready view."""
    store.append(_APPROVED)

    harness.dispatch(_toggle_action(published=True))

    assert harness.api_calls == [
        ("views.update", {"view_id": _VIEW_ID, "hash": _VIEW_HASH, "view": _copy_ready_view(_published())})
    ]


def test_undo_clears_the_publication(harness: Harness, store: InMemoryStatusUpdateStore) -> None:
    """Marking a published update not published leaves it approved with no publication time or person."""
    store.append(_APPROVED)
    store.transition(_published(), expected_state=StatusUpdateState.APPROVED)

    harness.dispatch(_toggle_action(published=False))

    assert store.latest(_INCIDENT).data == _APPROVED


def test_undo_updates_the_modal_once_in_place(harness: Harness, store: InMemoryStatusUpdateStore) -> None:
    """The undo's only Web API call is one views.update to the approved record's copy-ready view."""
    store.append(_APPROVED)
    store.transition(_published(), expected_state=StatusUpdateState.APPROVED)

    harness.dispatch(_toggle_action(published=False))

    assert harness.api_calls == [("views.update", {"view_id": _VIEW_ID, "hash": _VIEW_HASH, "view": _copy_ready_view(_APPROVED)})]
