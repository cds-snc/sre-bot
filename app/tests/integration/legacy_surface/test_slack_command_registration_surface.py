"""Pinning tests for the Slack commands registered on the Slack provider at startup.

Each test sends a form-encoded slash command through ``slack_bolt.App.dispatch``
on the harness app and asserts only what Slack and the backing services
observe: the HTTP ack, the message posted to ``response_url``, and the calls
made on faked Web API and service seams. Nothing asserts on hookimpl or
handler signatures, so the tests keep passing when registration moves to a
different contract as long as the user-facing behaviour is unchanged.
"""

from collections import Counter
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from contracts.operations import OperationResult, OperationStatus
from packages.access.sync.interactions import slack as access_sync_slack
from packages.access.sync.interactions.ingress import EnqueuedJob
from packages.geolocate.platforms import slack as geolocate_slack
from packages.incident.scribe import service as incident_scribe_service
from packages.incident.scribe.domain import DraftedDocument
from packages.incident.scribe.service import EMPTY_HISTORY_CODE
from packages.rant.service import format_rant
from packages.user_rotations.platforms import slack as user_rotations_slack
from packages.user_rotations.service import UserRotationShift

from .conftest import CHANNEL_ID, RESPONSE_URL, TRIGGER_ID, USER_ID, SlackCommandHarness, build_harness

pytestmark = pytest.mark.integration


class Recorder:
    """Callable fake that records its arguments and returns a fixed value."""

    def __init__(self, returns: Any = None) -> None:
        self.returns = returns
        self.calls: list[dict[str, Any]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append({"args": args, **kwargs})
        return self.returns


class AsyncRecorder(Recorder):
    """Async variant of ``Recorder`` for coroutine service functions."""

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        return super().__call__(*args, **kwargs)


def only_response(harness: SlackCommandHarness) -> dict[str, Any]:
    """The single message the command posted back to its response_url."""
    assert len(harness.responses) == 1, harness.responses
    response = harness.responses[0]
    assert response["url"] == RESPONSE_URL
    return response


# --- registration -----------------------------------------------------------


def test_each_root_slash_command_is_registered_once(slack_command_harness: SlackCommandHarness) -> None:
    """Every hookimpl command hangs off /sre or /rant, each wired to Bolt once.

    A duplicate would mean two registration paths for one command, which Bolt
    resolves silently by first match.
    """
    prefix = slack_command_harness.command_prefix

    counts = Counter(slack_command_harness.app.registered_commands)

    assert counts == Counter({f"/{prefix}sre": 1, f"/{prefix}rant": 1})


REGISTERED_COMMAND_TREE: dict[str, bool] = {
    "rant": False,
    "sre": True,
    "sre.access": False,
    "sre.access.sync": False,
    "sre.access.sync.platform": False,
    "sre.access.sync.status": False,
    "sre.access.sync.user": False,
    "sre.dev": False,
    "sre.dev.add-incident": False,
    "sre.dev.google": False,
    "sre.dev.incident": False,
    "sre.dev.load-incidents": False,
    "sre.dev.slack": False,
    "sre.dev.stale": False,
    "sre.geolocate": False,
    "sre.incident": False,
    "sre.incident.draft": False,
    "sre.incident.summarize": False,
    "sre.rotations": False,
    "sre.rotations.view": False,
    "sre.version": False,
    "sre.webhooks": False,
}


def test_registered_command_tree_is_unchanged(slack_command_harness: SlackCommandHarness) -> None:
    """The provider holds exactly the pinned command paths, each with its auto-generated flag.

    The literal is the whole tree, so an added, lost or replaced node fails
    the test, including the legacy /sre incident handler being shadowed by
    the auto-generated parent of its draft and summarize children.
    """
    commands = slack_command_harness.provider._commands

    tree = {full_path: command.is_auto_generated for full_path, command in commands.items()}

    assert tree == REGISTERED_COMMAND_TREE
    assert commands["sre.incident"].legacy_mode is True


def test_command_prefix_is_applied_to_root_slash_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    """A configured prefix renames the slash commands Slack routes to the app."""
    harness = build_harness(monkeypatch, command_prefix="dev-")

    response = harness.dispatch("sre", "version")

    assert sorted(harness.app.registered_commands) == ["/dev-rant", "/dev-sre"]
    assert response.status == 200
    assert only_response(harness)["text"].startswith("🤖 SRE Bot version:")


# --- modules/sre ------------------------------------------------------------


def test_sre_webhooks_subcommand_forwards_to_webhook_helper(
    slack_command_harness: SlackCommandHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/sre webhooks passes its arguments and invoker to the webhook helper once.

    The helper is faked because it reads DynamoDB; whatever it responds with
    is relayed ephemerally.
    """
    helper_calls: list[dict[str, Any]] = []

    def fake_handle_webhook_command(args: list[str], client: Any, body: dict[str, Any], respond: Any) -> None:
        helper_calls.append({"args": args, "body": body})
        respond(text="2 webhooks configured")

    monkeypatch.setattr("modules.sre.platforms.slack.webhook_helper.handle_webhook_command", fake_handle_webhook_command)

    response = slack_command_harness.dispatch("sre", "webhooks list")

    assert response.status == 200
    assert only_response(slack_command_harness) == {
        "url": RESPONSE_URL,
        "text": "2 webhooks configured",
        "response_type": "ephemeral",
    }
    assert len(helper_calls) == 1
    assert helper_calls[0]["args"] == ["list"]
    assert helper_calls[0]["body"]["user_id"] == USER_ID
    assert helper_calls[0]["body"]["channel_id"] == CHANNEL_ID


def test_sre_incident_subcommand_forwards_to_incident_helper(
    slack_command_harness: SlackCommandHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/sre incident passes its arguments and invoker to the legacy incident helper once.

    The helper is faked because it reads Google Drive and DynamoDB; whatever
    it responds with is relayed ephemerally.
    """
    helper_calls: list[dict[str, Any]] = []

    def fake_handle_incident_command(args: list[str], client: Any, body: dict[str, Any], respond: Any, ack: Any) -> None:
        helper_calls.append({"args": args, "body": body})
        respond(text="incident help")

    monkeypatch.setattr("modules.sre.platforms.slack.incident_helper.handle_incident_command", fake_handle_incident_command)

    response = slack_command_harness.dispatch("sre", "incident list")

    assert response.status == 200
    assert only_response(slack_command_harness) == {
        "url": RESPONSE_URL,
        "text": "incident help",
        "response_type": "ephemeral",
    }
    assert len(helper_calls) == 1
    assert helper_calls[0]["args"] == ["list"]
    assert helper_calls[0]["body"]["user_id"] == USER_ID
    assert helper_calls[0]["body"]["channel_id"] == CHANNEL_ID


# --- modules/dev ------------------------------------------------------------


def test_dev_group_acks_and_lists_its_subcommands(slack_command_harness: SlackCommandHarness) -> None:
    """/sre dev is a grouping node: it acks and answers with its subcommand help."""
    response = slack_command_harness.dispatch("sre", "dev")

    assert response.status == 200
    reply = only_response(slack_command_harness)
    assert reply["response_type"] == "ephemeral"
    for subcommand in ("add-incident", "google", "incident", "load-incidents", "slack", "stale"):
        assert f"/sre dev {subcommand}" in reply["text"]


def test_dev_leaf_outside_the_development_environment_is_refused(
    slack_command_harness: SlackCommandHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/sre dev google outside dev or local answers with a refusal and calls nothing.

    The environment is the only stubbed input; the refusal proves the dev leaf
    is registered and dispatched, without reaching its Google handler.
    """
    monkeypatch.setattr("modules.dev.platforms.slack.get_app_settings", lambda: SimpleNamespace(ENVIRONMENT="production"))

    response = slack_command_harness.dispatch("sre", "dev google")

    assert response.status == 200
    reply = only_response(slack_command_harness)
    assert reply["response_type"] == "ephemeral"
    assert reply["text"] == "This command is only available in the development environment."


# --- packages/rant ----------------------------------------------------------


def test_rant_posts_uppercase_message_as_the_invoking_user(slack_command_harness: SlackCommandHarness) -> None:
    """/rant posts the shouted text once under the invoker's name and avatar."""
    slack_command_harness.client.replies["users_info"] = {
        "ok": True,
        "user": {"profile": {"display_name": "Ada", "image_72": "https://avatars.test/ada.png"}},
    }

    response = slack_command_harness.dispatch("rant", "deploys keep failing")

    assert response.status == 200
    assert only_response(slack_command_harness) == {"url": RESPONSE_URL, "text": "✅ Ranted.", "response_type": "ephemeral"}
    assert slack_command_harness.client.calls_to("chat_postMessage") == [
        {
            "channel": CHANNEL_ID,
            "text": format_rant("deploys keep failing"),
            "username": "Ada",
            "icon_url": "https://avatars.test/ada.png",
        }
    ]


def test_rant_without_text_replies_with_usage_and_posts_nothing(slack_command_harness: SlackCommandHarness) -> None:
    """An empty /rant only explains the usage."""
    response = slack_command_harness.dispatch("rant", "")

    assert response.status == 200
    assert only_response(slack_command_harness)["text"] == "Usage: `/rant <text>` — shout a message in bold uppercase."
    assert slack_command_harness.client.calls_to("chat_postMessage") == []


# --- packages/user_rotations ------------------------------------------------


class FakeUserRotationsService:
    def __init__(self, shifts: list[UserRotationShift] | None) -> None:
        self.shifts = shifts
        self.handles: list[str] = []

    def get_rotation_shifts(self, handle: str) -> list[UserRotationShift] | None:
        self.handles.append(handle)
        return self.shifts


def test_rotations_view_opens_a_modal_with_the_rotation_shifts(
    slack_command_harness: SlackCommandHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/sre rotations view <handle> reads the rotation once and opens one modal."""
    shift = UserRotationShift(
        slack_user_id="U0ONCALL", start=datetime(2026, 9, 28, tzinfo=UTC), end=datetime(2026, 10, 5, tzinfo=UTC)
    )
    service = FakeUserRotationsService([shift])
    monkeypatch.setattr(user_rotations_slack, "get_user_rotations_service", lambda: service)

    response = slack_command_harness.dispatch("sre", "rotations view sre-oncall")

    assert response.status == 200
    assert service.handles == ["sre-oncall"]
    modal_calls = slack_command_harness.client.calls_to("views_open")
    assert len(modal_calls) == 1
    assert modal_calls[0]["trigger_id"] == TRIGGER_ID
    assert "<@U0ONCALL>" in str(modal_calls[0]["view"])
    assert only_response(slack_command_harness) == {"url": RESPONSE_URL, "text": "", "response_type": "ephemeral"}


def test_rotations_view_for_unknown_handle_reports_no_rotation(
    slack_command_harness: SlackCommandHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unconfigured rotation handle is reported and no modal opens."""
    monkeypatch.setattr(user_rotations_slack, "get_user_rotations_service", lambda: FakeUserRotationsService(None))

    slack_command_harness.dispatch("sre", "rotations view nobody")

    assert only_response(slack_command_harness)["text"] == "No user rotation configured for `nobody`."
    assert slack_command_harness.client.calls_to("views_open") == []


# --- packages/access/sync ---------------------------------------------------


@pytest.fixture
def fake_enqueue_user_sync(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    """Replace the access-sync ingress and its stores with recording fakes."""
    recorder = Recorder()
    monkeypatch.setattr(access_sync_slack, "enqueue_user_sync", recorder)
    for provider_name in (
        "get_access_sync_coordinator",
        "get_access_sync_job_status_store",
        "get_access_sync_lock_store",
        "get_access_sync_settings",
    ):
        monkeypatch.setattr(access_sync_slack, provider_name, lambda: object())
    return recorder


def _enqueued_job(*, already_running: bool) -> EnqueuedJob:
    return EnqueuedJob(
        job_id="job-42",
        platform="aws",
        user_email="ada@example.com",
        dry_run=False,
        started_at="2026-09-28T12:00:00Z",
        already_running=already_running,
    )


def test_access_sync_user_enqueues_one_job_and_returns_its_id(
    slack_command_harness: SlackCommandHarness, fake_enqueue_user_sync: Recorder
) -> None:
    """/sre access sync user enqueues exactly one normalised job and reports its id."""
    fake_enqueue_user_sync.returns = OperationResult.success(data=_enqueued_job(already_running=False))

    response = slack_command_harness.dispatch("sre", "access sync user Ada@Example.com AWS")

    assert response.status == 200
    assert len(fake_enqueue_user_sync.calls) == 1
    call = fake_enqueue_user_sync.calls[0]
    assert (call["user_email"], call["platform"], call["dry_run"]) == ("ada@example.com", "aws", False)
    text = only_response(slack_command_harness)["text"]
    assert "User sync enqueued for *ada@example.com* on *aws*" in text
    assert "`/sre access sync status job-42`" in text


def test_access_sync_user_already_running_points_at_the_existing_job(
    slack_command_harness: SlackCommandHarness, fake_enqueue_user_sync: Recorder
) -> None:
    """A sync already in flight is reported with the running job's id."""
    fake_enqueue_user_sync.returns = OperationResult.success(data=_enqueued_job(already_running=True))

    slack_command_harness.dispatch("sre", "access sync user ada@example.com aws")

    text = only_response(slack_command_harness)["text"]
    assert "User sync already in progress for *ada@example.com* on *aws*" in text
    assert "Job ID: `job-42`" in text


def test_access_sync_user_enqueue_failure_is_reported(
    slack_command_harness: SlackCommandHarness, fake_enqueue_user_sync: Recorder
) -> None:
    """An ingress failure becomes an ephemeral error carrying its message."""
    fake_enqueue_user_sync.returns = OperationResult.error(OperationStatus.TRANSIENT_ERROR, "lock store unavailable")

    slack_command_harness.dispatch("sre", "access sync user ada@example.com aws")

    reply = only_response(slack_command_harness)
    assert reply["response_type"] == "ephemeral"
    assert "lock store unavailable" in reply["text"]


# --- packages/incident/scribe ------------------------------------------------

CHANNEL_HISTORY = {
    "ok": True,
    "messages": [{"type": "message", "user": "U0RESPONDER", "text": "Rolled back the deploy", "ts": "1790000000.000100"}],
}


@pytest.fixture
def incident_channel(slack_command_harness: SlackCommandHarness) -> SlackCommandHarness:
    """An incident channel with history, bookmarked incident doc and a known responder."""
    slack_command_harness.client.replies.update(
        {
            "conversations_info": {"ok": True, "channel": {"created": 1789990000}},
            "conversations_history": CHANNEL_HISTORY,
            "users_info": {"ok": True, "user": {"profile": {"display_name": "Grace"}}},
            "bookmarks_list": {
                "ok": True,
                "bookmarks": [{"title": "Incident report", "link": "https://docs.google.com/document/d/doc-source/edit"}],
            },
        }
    )
    return slack_command_harness


def test_incident_draft_drafts_from_the_bookmarked_document(
    incident_channel: SlackCommandHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/sre incident draft drafts once from the channel transcript and links the new document."""
    drafter = AsyncRecorder(
        OperationResult.success(
            data=DraftedDocument(document_id="doc-draft", created=True, drafted_headings=("Summary",), unanswered_headings=())
        )
    )
    monkeypatch.setattr(incident_scribe_service, "draft_incident_document", drafter)

    response = incident_channel.dispatch("sre", "incident draft")

    assert response.status == 200
    assert len(drafter.calls) == 1
    source_document_id, transcript = drafter.calls[0]["args"]
    assert source_document_id == "doc-source"
    assert [message.text for message in transcript] == ["Rolled back the deploy"]
    reply = only_response(incident_channel)
    assert reply["response_type"] == "ephemeral"
    assert "https://docs.google.com/document/d/doc-draft/edit" in reply["text"]


def test_incident_draft_without_bookmarked_document_does_not_draft(
    incident_channel: SlackCommandHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without an "Incident report" bookmark the command explains and never calls the drafter."""
    incident_channel.client.replies["bookmarks_list"] = {"ok": True, "bookmarks": []}
    drafter = AsyncRecorder()
    monkeypatch.setattr(incident_scribe_service, "draft_incident_document", drafter)

    incident_channel.dispatch("sre", "incident draft")

    assert only_response(incident_channel)["text"] == "I couldn't find an incident document bookmarked in this channel."
    assert drafter.calls == []


def test_incident_summarize_returns_the_summary_ephemerally(
    incident_channel: SlackCommandHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/sre incident summarize summarises the channel transcript once."""
    summarizer = AsyncRecorder(OperationResult.success(data="The deploy was rolled back."))
    monkeypatch.setattr(incident_scribe_service, "summarize_transcript", summarizer)

    response = incident_channel.dispatch("sre", "incident summarize")

    assert response.status == 200
    assert len(summarizer.calls) == 1
    (transcript,) = summarizer.calls[0]["args"]
    assert [message.text for message in transcript] == ["Rolled back the deploy"]
    reply = only_response(incident_channel)
    assert reply["response_type"] == "ephemeral"
    assert reply["text"].startswith("🧾 Incident summary\n\n")
    assert "The deploy was rolled back." in reply["text"]


def test_incident_summarize_with_empty_history_says_there_is_nothing_yet(
    incident_channel: SlackCommandHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The service's empty-history outcome is rendered as a notice, not an error."""
    summarizer = AsyncRecorder(
        OperationResult.error(OperationStatus.PERMANENT_ERROR, "no messages", error_code=EMPTY_HISTORY_CODE)
    )
    monkeypatch.setattr(incident_scribe_service, "summarize_transcript", summarizer)

    incident_channel.dispatch("sre", "incident summarize")

    assert only_response(incident_channel)["text"] == "There's nothing to summarize yet in this channel."


# --- packages/geolocate -----------------------------------------------------


def test_geolocate_posts_location_blocks_in_channel(
    slack_command_harness: SlackCommandHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/sre geolocate <ip> looks the address up once and posts blocks to the channel."""
    lookup = Recorder(
        OperationResult.success(
            data={
                "city": "Mountain View",
                "country": "United States",
                "country_code": "US",
                "latitude": 37.386,
                "longitude": -122.0838,
            }
        )
    )
    monkeypatch.setattr(geolocate_slack, "geolocate_ip", lookup)

    response = slack_command_harness.dispatch("sre", "geolocate 8.8.8.8")

    assert response.status == 200
    assert [call["ip_address"] for call in lookup.calls] == ["8.8.8.8"]
    reply = only_response(slack_command_harness)
    assert reply["response_type"] == "in_channel"
    assert "Mountain View" in str(reply["blocks"])


def test_geolocate_unknown_address_reports_not_found(
    slack_command_harness: SlackCommandHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A NOT_FOUND lookup is reported ephemerally with the queried address."""
    monkeypatch.setattr(geolocate_slack, "geolocate_ip", Recorder(OperationResult.error(OperationStatus.NOT_FOUND, "not found")))

    slack_command_harness.dispatch("sre", "geolocate 10.0.0.1")

    assert only_response(slack_command_harness) == {
        "url": RESPONSE_URL,
        "text": "❌ Location not found for IP: 10.0.0.1",
        "response_type": "ephemeral",
    }
