"""Fixtures that drive Slack commands and interactions through a real slack_bolt App.

``slack_command_harness`` registers the production ``register_slack_commands`` hookimpls
through a pluggy PluginManager, then the legacy sre and dev commands through
the lifespan's own ``_register_legacy_slack_commands``, onto a real
``SlackPlatformProvider`` bound to a real ``slack_bolt.App``, then feeds form-encoded slash-command requests to
``App.dispatch``. Only the edges are faked: the Slack Web API client (which
also backs each package's Slack lookup adapter), the ``response_url`` webhook
that Bolt's ``respond`` posts to, the incident records (an in-memory record
store holding one legacy incident on the test channel, its report linked), and
each package's backing service (patched per test).

``legacy_handler_harness`` registers the hard-coded legacy modules through the
lifespan's own ``_register_legacy_handlers`` on a fresh Bolt app, and feeds it
slash commands, interaction payloads and Events API callbacks. Bolt hands those
listeners a ``WebClient`` it builds per request, so ``WebClient.api_call`` is
routed into a ``FakeSlackClient``. The external edges the legacy handlers reach
are faked: ``response_url`` posts and the Sentinel ``send_event`` sender.

A legacy module that reaches no external edge is faked at an internal seam,
and only in a named ``legacy_*_seam`` fixture whose docstring names its owning
rebuild task: the task that rebuilds the caller and deletes the fixture. The
test-seam guard (``make check-test-seams``) lists each seam in
``bin/baselines/test_seams_legacy.txt`` and fails on a patch of a features/,
capabilities/ or modules/ target anywhere else (decisions/testing.md).
"""

import base64
import json
import re
from collections.abc import Callable, Coroutine, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from types import ModuleType, SimpleNamespace
from typing import Any, cast
from urllib.parse import urlencode

import httplib2
import i18n  # type: ignore
import pluggy
import pytest
import requests_mock as requests_mock_module
import structlog
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI
from fastapi.testclient import TestClient
from googleapiclient.errors import HttpError
from pydantic import SecretStr
from slack_bolt import App, BoltRequest, BoltResponse
from slack_sdk import WebClient
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.webhook import WebhookClient

import capabilities.oncall.plugin as oncall_plugin_module
import features.incident.comms as incident_comms_module
import features.incident.response.plugin as incident_response_module
import features.incident.scribe as incident_scribe_module
import packages.access.sync as access_sync_module
import packages.geolocate as geolocate_module
import packages.rant as rant_module
from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import get_incident_core_settings
from features.incident.core.adapters.slack import SlackIncidentTranscriptReader
from features.incident.scribe import service as incident_scribe_service
from infrastructure.configuration.features.sre_ops import get_sre_ops_settings
from infrastructure.records.in_memory import InMemoryRecordStore
from infrastructure.security import get_limiter
from infrastructure.spreadsheets import get_spreadsheet_provider
from integrations.aws.settings import get_aws_settings
from integrations.google_workspace import client as google_workspace_client
from integrations.notify.settings import get_notify_settings
from integrations.sentinel import client as sentinel_client
from integrations.slack.formatter import SlackBlockKitFormatter
from integrations.slack.provider import SlackPlatformProvider
from integrations.slack.settings import SlackSettings
from models.incidents import Incident
from modules.sre.platforms import slack as sre_slack
from modules.webhooks.patterns.aws_sns_notification.settings import get_notify_api_key_leak_settings
from packages.aws_platform.adapters import dynamodb as dynamodb_adapter
from packages.rant.adapters.slack import SlackUserIdentityLookup
from packages.rant.platforms import slack as rant_slack
from server.lifespan import _register_legacy_handlers, _register_legacy_slack_commands
from server.server import create_app
from server.slack.settings import get_slack_transport_settings
from tests.factories.incident import GOOGLE_TENANT, SLACK_TENANT, incident_scopes, seed_legacy_incident
from tests.factories.slack_bolt import FakeSlackClient, InlineExecutor, authorize_single_workspace, unpatched_app_init

SLACK_COMMAND_HOOKIMPLS: tuple[ModuleType, ...] = (
    rant_module,
    oncall_plugin_module,
    access_sync_module,
    incident_scribe_module,
    incident_comms_module,
    incident_response_module,
    geolocate_module,
)

USER_ID = "U0INVOKER"
CHANNEL_ID = "C0INCIDENT"
TRIGGER_ID = "trigger-123"
TEAM_ID = "T0TEAM"
RESPONSE_URL = "https://hooks.slack.test/commands/response"
REPORT_URL = "https://docs.google.com/document/d/doc-source/edit"


class RecordingApp(App):
    """Unmodified Bolt App that also records each listener it registers.

    Slash commands land in ``registered_commands``; actions, views and events
    land in ``registered_listeners`` as ``(kind, id, has_matchers)``.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.registered_commands: list[str] = []
        self.registered_listeners: list[tuple[str, str, bool]] = []

    def command(self, command: Any, *args: Any, **kwargs: Any) -> Any:
        self.registered_commands.append(str(command))
        return super().command(command, *args, **kwargs)

    def action(self, constraints: Any, *args: Any, **kwargs: Any) -> Any:
        self.registered_listeners.append(("action", str(constraints), bool(kwargs.get("matchers"))))
        return super().action(constraints, *args, **kwargs)

    def view(self, constraints: Any, *args: Any, **kwargs: Any) -> Any:
        self.registered_listeners.append(("view", str(constraints), bool(kwargs.get("matchers"))))
        return super().view(constraints, *args, **kwargs)

    def event(self, event: Any, *args: Any, **kwargs: Any) -> Any:
        self.registered_listeners.append(("event", str(event), bool(kwargs.get("matchers"))))
        return super().event(event, *args, **kwargs)


@dataclass
class SlackCommandHarness:
    """A Bolt app with the command hookimpls registered, plus captured output."""

    app: RecordingApp
    provider: SlackPlatformProvider
    client: FakeSlackClient
    command_prefix: str
    records: InMemoryRecordStore = field(default_factory=InMemoryRecordStore)
    responses: list[dict[str, Any]] = field(default_factory=list)

    def dispatch(self, command: str, text: str = "") -> BoltResponse:
        """Send one slash command through ``App.dispatch`` as Slack would."""
        body = urlencode(
            {
                "command": f"/{self.command_prefix}{command}",
                "text": text,
                "user_id": USER_ID,
                "channel_id": CHANNEL_ID,
                "team_id": TEAM_ID,
                "trigger_id": TRIGGER_ID,
                "response_url": RESPONSE_URL,
            }
        )
        request = BoltRequest(body=body, headers={"content-type": ["application/x-www-form-urlencoded"]})
        return self.app.dispatch(request)


def build_bolt_app(monkeypatch: pytest.MonkeyPatch) -> RecordingApp:
    """A real Bolt app that authorizes one workspace and runs its listeners inline."""
    monkeypatch.setattr(App, "__init__", unpatched_app_init())
    return RecordingApp(
        authorize=authorize_single_workspace,
        request_verification_enabled=False,
        listener_executor=InlineExecutor(),
    )


def capture_response_url_posts(monkeypatch: pytest.MonkeyPatch, responses: list[dict[str, Any]]) -> None:
    """Record each message Bolt's ``respond`` posts to a ``response_url`` instead of sending it."""

    def capture_send_dict(webhook: WebhookClient, body: dict[str, Any], headers: dict[str, str] | None = None) -> SimpleNamespace:
        responses.append({"url": webhook.url, **body})
        return SimpleNamespace(status_code=200, body="ok")

    monkeypatch.setattr(WebhookClient, "send_dict", capture_send_dict)


class _AwaitedSlackClient:
    """Async view of the harness's ``FakeSlackClient``: each Web API method is awaited and delegates to the fake, which records it."""

    def __init__(self, client: FakeSlackClient) -> None:
        self._client = client

    def __getattr__(self, name: str) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
        method = getattr(self._client, name)

        async def awaited(**kwargs: Any) -> dict[str, Any]:
            response: dict[str, Any] = method(**kwargs)
            return response

        return awaited


@pytest.fixture
def legacy_scribe_transcript_reader_seam(monkeypatch: pytest.MonkeyPatch) -> FakeSlackClient:
    """Internal legacy seam: scribe's transcript reader factory, over the harness's Slack client.

    Scribe resolves its reader through ``core/api.py``, not a provider, so the
    real Slack reader is built over an awaited view of the returned fake client and handed to
    scribe's service module. Owning rebuild task: TASK-145.11, which moves the
    report draft into incident/postmortem and deletes scribe; this fixture is
    deleted there (or earlier if TASK-145.9 moves summarize off it).
    """
    client = FakeSlackClient()
    reader = SlackIncidentTranscriptReader(cast(AsyncWebClient, _AwaitedSlackClient(client)))
    monkeypatch.setattr(incident_scribe_service, "get_incident_transcript_reader", lambda: reader)
    return client


def build_harness(monkeypatch: pytest.MonkeyPatch, command_prefix: str, client: FakeSlackClient) -> SlackCommandHarness:
    """Wire the seven hookimpls and the legacy sre and dev commands onto a fresh provider and Bolt app.

    ``client`` is the fake from ``legacy_scribe_transcript_reader_seam``, so
    scribe's transcript reader and every other Slack lookup share it.
    """
    app = build_bolt_app(monkeypatch)
    settings = SimpleNamespace(app_token=SecretStr("xapp-test"), bot_token=SecretStr("xoxb-test"))
    provider = SlackPlatformProvider(
        settings=cast(SlackSettings, settings), formatter=SlackBlockKitFormatter(), command_prefix=command_prefix
    )
    provider._app = app
    provider._client = client
    # The incident records the entry points read: the channel is one legacy incident with its report linked.
    records = InMemoryRecordStore()
    seed_legacy_incident(records, CHANNEL_ID, report_url=REPORT_URL)
    provider.set_scope_opener(
        incident_scopes(records, tenants={WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT})
    )

    # Each package's Slack lookups run through its real adapter over the same fake client.
    web_client = cast(WebClient, client)
    monkeypatch.setattr(rant_slack, "get_user_identity_lookup", lambda: SlackUserIdentityLookup(web_client))

    plugin_manager = pluggy.PluginManager(PLUGIN_NAMESPACE)
    plugin_manager.add_hookspecs(FeatureLifecycleSpecs)
    for hookimpl_module in SLACK_COMMAND_HOOKIMPLS:
        plugin_manager.register(hookimpl_module)
    plugin_manager.hook.register_slack_commands(registrar=provider)
    _register_legacy_slack_commands(provider, structlog.get_logger())
    provider._auto_register_root_commands()

    harness = SlackCommandHarness(app=app, provider=provider, client=client, command_prefix=command_prefix, records=records)
    capture_response_url_posts(monkeypatch, harness.responses)
    return harness


@pytest.fixture
def slack_command_harness(
    monkeypatch: pytest.MonkeyPatch, legacy_scribe_transcript_reader_seam: FakeSlackClient
) -> Iterator[SlackCommandHarness]:
    """Harness using the deployment's configured slash-command prefix."""
    yield build_harness(monkeypatch, get_slack_transport_settings().command_prefix, legacy_scribe_transcript_reader_seam)


@dataclass
class LegacyHandlerHarness:
    """A Bolt app with the hard-coded legacy handlers registered, plus captured edges."""

    app: RecordingApp
    client: FakeSlackClient
    command_prefix: str
    sentinel_events: list[dict[str, Any]] = field(default_factory=list)
    responses: list[dict[str, Any]] = field(default_factory=list)

    def command(self, command: str, text: str = "", **fields: str) -> BoltResponse:
        """Send one slash command through ``App.dispatch`` as Slack would; ``fields`` add form fields such as ``channel_name``."""
        body = urlencode(
            {
                "command": f"/{self.command_prefix}{command}",
                "text": text,
                "user_id": USER_ID,
                "channel_id": CHANNEL_ID,
                "team_id": TEAM_ID,
                "trigger_id": TRIGGER_ID,
                "response_url": RESPONSE_URL,
                **fields,
            }
        )
        request = BoltRequest(body=body, headers={"content-type": ["application/x-www-form-urlencoded"]})
        return self.app.dispatch(request)

    def interaction(self, payload: dict[str, Any]) -> BoltResponse:
        """Send a block_actions, interactive_message or view_submission payload as Slack would."""
        body = urlencode({"payload": json.dumps({"team": {"id": TEAM_ID}, "user": {"id": USER_ID}, **payload})})
        request = BoltRequest(body=body, headers={"content-type": ["application/x-www-form-urlencoded"]})
        return self.app.dispatch(request)

    def event(self, event: dict[str, Any]) -> BoltResponse:
        """Send one Events API callback wrapping ``event`` as Slack would."""
        body = json.dumps({"type": "event_callback", "team_id": TEAM_ID, "event_id": "Ev0TEST", "event": event})
        request = BoltRequest(body=body, headers={"content-type": ["application/json"]})
        return self.app.dispatch(request)


@pytest.fixture
def legacy_handler_harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[LegacyHandlerHarness]:
    """Bolt app with ``_register_legacy_handlers`` applied and every external edge faked.

    Listener-injected Web API clients reach the harness's ``FakeSlackClient``
    by method name (``views.open`` -> ``views_open``), with canned replies for
    the lookups the legacy handlers index into. The global i18n locale is
    restored afterwards because the legacy handlers set it per request.
    """
    client = FakeSlackClient()
    client.replies["users_info"] = {"ok": True, "user": {"id": USER_ID, "locale": "en-US"}}
    client.replies["conversations_create"] = {"ok": True, "channel": {"id": "C0NEWINCIDENT"}}
    app = build_bolt_app(monkeypatch)
    harness = LegacyHandlerHarness(
        app=app,
        client=client,
        command_prefix=get_slack_transport_settings().command_prefix,
    )

    def route_api_call(web_client: WebClient, api_method: str, **kwargs: Any) -> Any:
        arguments = kwargs.get("json") or kwargs.get("params") or kwargs.get("data") or {}
        # The SDK strips unset optional arguments before sending; so does the router.
        sent = {name: value for name, value in arguments.items() if value is not None}
        return getattr(client, api_method.replace(".", "_"))(**sent)

    def record_sentinel_event(payload: dict[str, Any]) -> bool:
        harness.sentinel_events.append(payload)
        return True

    monkeypatch.setattr(WebClient, "api_call", route_api_call)
    capture_response_url_posts(monkeypatch, harness.responses)
    monkeypatch.setattr(sentinel_client, "send_event", record_sentinel_event)

    _register_legacy_handlers(app, structlog.get_logger())
    locale, fallback = i18n.get("locale"), i18n.get("fallback")
    yield harness
    i18n.set("locale", locale)
    i18n.set("fallback", fallback)


class ChannelAwareSlackClient(FakeSlackClient):
    """``FakeSlackClient`` whose channel listing and history answers depend on the request.

    ``conversations_list`` replies by the request's cursor (``None`` for the
    first page) and ``conversations_history`` by the requested channel, which
    is what a workspace with several channels and pages looks like to a job.
    """

    def __init__(self) -> None:
        super().__init__()
        self.channel_pages: dict[str | None, dict[str, Any]] = {}
        self.history_by_channel: dict[str, dict[str, Any]] = {}

    def conversations_list(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("conversations_list", kwargs))
        return self.channel_pages.get(kwargs.get("cursor"), {"ok": True, "channels": []})

    def conversations_history(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("conversations_history", kwargs))
        return self.history_by_channel.get(kwargs["channel"], {"ok": True, "messages": []})


@dataclass
class RoutedSlackEdges:
    """The Slack Web API fake and the Sentinel events a scheduled job reached."""

    client: ChannelAwareSlackClient
    sentinel_events: list[dict[str, Any]] = field(default_factory=list)


@pytest.fixture
def routed_slack_client(monkeypatch: pytest.MonkeyPatch) -> RoutedSlackEdges:
    """Route every ``WebClient`` request into a ``ChannelAwareSlackClient`` and record Sentinel events.

    Jobs build their own outbound Web client per run, so the routing is on
    ``WebClient.api_call`` rather than on an injected client. Calls arrive by
    method name (``chat.postMessage`` -> ``chat_postMessage``) with unset
    optional arguments removed, as the SDK would send them.
    """
    edges = RoutedSlackEdges(client=ChannelAwareSlackClient())

    def route_api_call(web_client: WebClient, api_method: str, **kwargs: Any) -> Any:
        arguments = kwargs.get("json") or kwargs.get("params") or kwargs.get("data") or {}
        sent = {name: value for name, value in arguments.items() if value is not None}
        return getattr(edges.client, api_method.replace(".", "_"))(**sent)

    def record_sentinel_event(payload: dict[str, Any]) -> bool:
        edges.sentinel_events.append(payload)
        return True

    monkeypatch.setattr(WebClient, "api_call", route_api_call)
    monkeypatch.setattr(sentinel_client, "send_event", record_sentinel_event)
    return edges


# The incident surface: /sre incident commands and the modals they open, over faked external edges.

INCIDENT_CHANNEL_NAME = "incident-2026-10-checkout"
REPORT_DOCUMENT_ID = "doc-source"
# The report template's timeline placeholder; the bot edits the text between it and the "Trigger" heading.
TIMELINE_PLACEHOLDER = "DO NOT REMOVE this line as the SRE bot needs it as a placeholder."
VIEW_ID = "V0OPEN"
ROOT_VIEW_ID = "V0ROOT"
INCIDENT_SHEET_ROW = ["2026-10-01", "Checkout outage", "Forms", "Open", "#2026-10-checkout"]


class FakeDynamoDbClient:
    """In-memory stand-in for the boto3 DynamoDB client the incidents table adapter wraps.

    Understands only the requests the incident module sends: a scan filtered by
    ``field = :field``, ``put_item``, ``get_item`` of the marker, ``SET #field = :field`` updates (conditions are not evaluated: seeded items have no marker) and the
    ``list_append`` activity-log update. ``unavailable`` makes every request
    fail the way a throttled or unreachable table does.
    """

    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.unavailable = False

    def _guard(self, operation: str) -> None:
        if self.unavailable:
            raise ClientError({"Error": {"Code": "InternalServerError", "Message": "table down"}}, operation)

    def get_paginator(self, operation: str) -> FakeDynamoDbClient:
        assert operation == "scan"
        return self

    def paginate(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        self._guard("Scan")
        items = self.tables.get(kwargs["TableName"], [])
        filter_expression = kwargs.get("FilterExpression")
        if filter_expression:
            attribute = filter_expression.split(" = ")[0]
            wanted = kwargs["ExpressionAttributeValues"][f":{attribute}"]
            items = [item for item in items if item.get(attribute) == wanted]
        yield {"Items": [dict(item) for item in items]}

    def put_item(self, **kwargs: Any) -> dict[str, Any]:
        self._guard("PutItem")
        self.tables.setdefault(kwargs["TableName"], []).append(dict(kwargs["Item"]))
        return {}

    def get_item(self, **kwargs: Any) -> dict[str, Any]:
        self._guard("GetItem")
        item = next((item for item in self.tables.get(kwargs["TableName"], []) if item["id"] == kwargs["Key"]["id"]), None)
        if item is None:
            return {}
        return {"Item": {name: value for name, value in item.items() if name in kwargs["ProjectionExpression"].split(",")}}

    def update_item(self, **kwargs: Any) -> dict[str, Any]:
        self._guard("UpdateItem")
        item = next(item for item in self.tables[kwargs["TableName"]] if item["id"] == kwargs["Key"]["id"])
        values = kwargs["ExpressionAttributeValues"]
        if "list_append" in kwargs["UpdateExpression"]:
            item.setdefault("logs", {"L": []})["L"].extend(values[":logs"]["L"])
            return {}
        attribute = re.match(r"SET #(\w+) = :\1", kwargs["UpdateExpression"])
        assert attribute is not None, kwargs["UpdateExpression"]
        item[attribute.group(1)] = values[f":{attribute.group(1)}"]
        return {}


class FakeIncidentTable:
    """The incidents table the legacy incident module reads and writes, seeded through domain values."""

    def __init__(self, client: FakeDynamoDbClient) -> None:
        self._client = client

    def seed(self, **overrides: Any) -> None:
        """Add one incident on the test channel; ``overrides`` replace any field of the stored record."""
        record = Incident(
            id="inc-1",
            channel_id=CHANNEL_ID,
            channel_name=INCIDENT_CHANNEL_NAME,
            name="Checkout outage",
            user_id=USER_ID,
            teams=["Forms"],
            report_url=REPORT_URL,
            status="Open",
            created_at="1760000000.0",
            severity="sev-2",
            meet_url="https://meet.google.com/abc-defg-hij",
            **overrides,
        )
        serializer = TypeSerializer()
        item = {name: serializer.serialize(value) for name, value in record.model_dump().items()}
        self._client.tables.setdefault("incidents", []).append(item)

    def go_down(self) -> None:
        """Make every later request to the table fail."""
        self._client.unavailable = True

    def items(self) -> list[dict[str, Any]]:
        """The stored incidents, as plain values."""
        deserializer = TypeDeserializer()
        return [
            {name: deserializer.deserialize(value) for name, value in item.items()}
            for item in self._client.tables.get("incidents", [])
        ]


class _Request:
    """A googleapiclient request whose ``execute`` returns a prepared result, or raises a prepared error."""

    def __init__(self, result: Any) -> None:
        self._result = result

    def execute(self, **_: Any) -> Any:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def google_http_error(status: int, message: str) -> HttpError:
    """The error googleapiclient raises when Google answers ``status`` with ``message``."""
    response = httplib2.Response({"status": status})
    response.reason = message
    return HttpError(resp=response, content=json.dumps({"error": {"code": status, "message": message}}).encode())


class FakeDriveFiles:
    """The Drive ``files()`` resource over folders and documents, with ``appProperties`` metadata."""

    def __init__(self) -> None:
        self.entries: dict[str, dict[str, Any]] = {}
        self._created = 0

    def add(self, file_id: str, name: str, *, parent: str, folder: bool, **app_properties: str) -> None:
        self.entries[file_id] = {"id": file_id, "name": name, "parent": parent, "folder": folder, "appProperties": app_properties}

    def properties(self, file_id: str) -> dict[str, str]:
        """The ``appProperties`` currently stored on a file."""
        properties: dict[str, str] = self.entries[file_id]["appProperties"]
        return dict(properties)

    def list(self, *, q: str, **_: Any) -> _Request:
        parent = re.search(r"parents in '([^']*)'", q)
        name = re.search(r"name='([^']*)'", q)
        found = [
            entry
            for entry in self.entries.values()
            if (parent is None or entry["parent"] == parent.group(1))
            and (name is None or entry["name"] == name.group(1))
            and ("mimeType = " not in q or entry["folder"])
        ]
        return _Request({"files": [{"id": entry["id"], "name": entry["name"]} for entry in found]})

    def list_next(self, request: Any, response: Any) -> None:
        return None

    def get(self, *, fileId: str, **_: Any) -> _Request:
        entry = self.entries[fileId]
        result: dict[str, Any] = {"id": fileId, "name": entry["name"]}
        if entry["appProperties"]:
            result["appProperties"] = dict(entry["appProperties"])
        return _Request(result)

    def update(self, *, fileId: str, body: dict[str, Any], **_: Any) -> _Request:
        properties = self.entries[fileId]["appProperties"]
        for key, value in body["appProperties"].items():
            if value is None:
                properties.pop(key, None)
            else:
                properties[key] = value
        return _Request({"id": fileId})

    def create(self, *, body: dict[str, Any], **_: Any) -> _Request:
        self._created += 1
        file_id = f"F0CREATED{self._created}"
        self.add(file_id, body["name"], parent=body["parents"][0], folder=True)
        return _Request({"id": file_id, "name": body["name"]})


class FakeDocsDocuments:
    """The Docs ``documents()`` resource over in-memory documents.

    ``texts`` holds each document's text and ``links`` the link URL on each of its
    characters (``None`` for plain text; reset when ``texts`` is set directly).
    ``get`` returns the body as paragraphs of text runs with Google's 1-based
    indexes and the current revision id. ``batchUpdate`` applies
    ``replaceAllText``, ``deleteContentRange``, ``insertText`` and link
    ``updateTextStyle`` requests in order (paragraph styling is accepted and
    ignored). A ``writeControl.requiredRevisionId`` that is not the current
    revision is refused with HTTP 400, as Google refuses it; ``concurrent_edits``
    makes that many guarded writes find the document moved on by another editor.
    Every ``batchUpdate`` body sent is kept in ``edits``.
    """

    def __init__(self) -> None:
        self.texts: dict[str, str] = {}
        self.links: dict[str, list[str | None]] = {}
        self.revisions: dict[str, int] = {}
        self.edits: list[dict[str, Any]] = []
        self.concurrent_edits = 0

    def _links(self, document_id: str) -> list[str | None]:
        links = self.links.setdefault(document_id, [])
        if len(links) != len(self.texts[document_id]):
            links[:] = [None] * len(self.texts[document_id])
        return links

    def _revision(self, document_id: str) -> str:
        return f"rev-{self.revisions.get(document_id, 1)}"

    def _bump(self, document_id: str) -> None:
        self.revisions[document_id] = self.revisions.get(document_id, 1) + 1

    @staticmethod
    def _offset(text: str, index: int) -> int:
        encoded = text.encode("utf-16-le")
        assert 1 <= index <= len(encoded) // 2 + 1
        return len(encoded[: (index - 1) * 2].decode("utf-16-le"))

    def get(self, *, documentId: str, **_: Any) -> _Request:
        text, links = self.texts[documentId], self._links(documentId)
        content: list[dict[str, Any]] = []
        elements: list[dict[str, Any]] = []
        start = 0
        for position, char in enumerate(text):
            end = position + 1
            if end < len(text) and char != "\n" and links[end] == links[start]:
                continue
            style = {"link": {"url": links[start]}} if links[start] else {}
            elements.append(
                {
                    "startIndex": len(text[:start].encode("utf-16-le")) // 2 + 1,
                    "endIndex": len(text[:end].encode("utf-16-le")) // 2 + 1,
                    "textRun": {"content": text[start:end], "textStyle": style},
                }
            )
            start = end
            if char == "\n" or end == len(text):
                content.append(
                    {
                        "startIndex": elements[0]["startIndex"],
                        "endIndex": elements[-1]["endIndex"],
                        "paragraph": {"elements": elements},
                    }
                )
                elements = []
        return _Request({"documentId": documentId, "revisionId": self._revision(documentId), "body": {"content": content}})

    def batchUpdate(self, *, documentId: str, body: dict[str, Any]) -> _Request:
        self.edits.append(body)
        required = body.get("writeControl", {}).get("requiredRevisionId")
        if required is not None:
            if self.concurrent_edits:
                self.concurrent_edits -= 1
                self._bump(documentId)
            if required != self._revision(documentId):
                return _Request(google_http_error(400, "The document was modified after the required revision"))
        replies = [self._apply(documentId, request) for request in body["requests"]]
        self._bump(documentId)
        return _Request({"replies": replies})

    def _apply(self, document_id: str, request: dict[str, Any]) -> dict[str, Any]:
        text, links = self.texts[document_id], self._links(document_id)
        if "replaceAllText" in request:
            spec = request["replaceAllText"]
            flags = 0 if spec["containsText"]["matchCase"] else re.IGNORECASE
            updated, changed = re.subn(re.escape(spec["containsText"]["text"]), spec["replaceText"], text, flags=flags)
            self.texts[document_id] = updated
            return {"replaceAllText": {"occurrencesChanged": changed}}
        if "deleteContentRange" in request:
            span = request["deleteContentRange"]["range"]
            start, end = self._offset(text, span["startIndex"]), self._offset(text, span["endIndex"])
            self.texts[document_id] = text[:start] + text[end:]
            del links[start:end]
        elif "insertText" in request:
            at, inserted = self._offset(text, request["insertText"]["location"]["index"]), request["insertText"]["text"]
            self.texts[document_id] = text[:at] + inserted + text[at:]
            links[at:at] = [None] * len(inserted)
        elif "updateTextStyle" in request:
            span = request["updateTextStyle"]["range"]
            url = request["updateTextStyle"]["textStyle"].get("link", {}).get("url")
            start, end = self._offset(text, span["startIndex"]), self._offset(text, span["endIndex"])
            links[start:end] = [url] * (end - start)
        else:
            assert "updateParagraphStyle" in request, request
        return {}

    def linked_text(self, document_id: str) -> str:
        """The document's text with each linked run written as ``[text](url)``, as a reader of the document sees it."""
        rendered, run, run_link = "", "", None
        for char, link in [*zip(self.texts[document_id], self._links(document_id), strict=True), ("", None)]:
            if link != run_link or not char:
                rendered += f"[{run}]({run_link})" if run_link else run
                run, run_link = "", link
            run += char
        return rendered


EVENT_LINK = "https://calendar.google.com/calendar/event?eid=retro-1"


class FakeCalendar:
    """The Calendar ``freebusy()`` and ``events()`` resources.

    ``fully_busy`` holds the emails whose calendars are busy over the whole
    requested range; every other calendar is free. Inserted events are kept in
    ``events`` (calendar id and body); ``insert_error`` makes inserts fail.
    """

    def __init__(self) -> None:
        self.fully_busy: set[str] = set()
        self.queries: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.insert_error: Exception | None = None

    def query(self, *, body: dict[str, Any]) -> _Request:
        self.queries.append(body)
        busy = [{"start": body["timeMin"], "end": body["timeMax"]}]
        calendars = {item["id"]: {"busy": busy if item["id"] in self.fully_busy else []} for item in body["items"]}
        return _Request({"kind": "calendar#freeBusy", "calendars": calendars})

    def insert(self, *, calendarId: str, body: dict[str, Any], **_: Any) -> _Request:
        if self.insert_error is not None:
            return _Request(self.insert_error)
        self.events.append({"calendarId": calendarId, "body": body})
        return _Request({"id": "retro-1", "htmlLink": EVENT_LINK, "start": body["start"], "end": body["end"]})


class FakeSheetValues:
    """The Sheets ``values()`` resource over one sheet of rows."""

    def __init__(self) -> None:
        self.rows: list[list[str]] = []

    def get(self, *, spreadsheetId: str, range: str) -> _Request:
        return _Request({"values": [list(row) for row in self.rows]})

    def batchUpdate(self, *, spreadsheetId: str, body: dict[str, Any]) -> _Request:
        for update in body["data"]:
            cell = re.search(r"!([A-Z]+)(\d+)$", update["range"])
            assert cell is not None, update["range"]
            column = ord(cell.group(1)) - ord("A")
            self.rows[int(cell.group(2)) - 1][column] = update["values"][0][0]
        return _Request({})


@dataclass
class FakeGoogleWorkspace:
    """The Drive, Docs, Sheets and Calendar services the incident module reaches, as in-memory state."""

    drive: FakeDriveFiles = field(default_factory=FakeDriveFiles)
    docs: FakeDocsDocuments = field(default_factory=FakeDocsDocuments)
    sheet: FakeSheetValues = field(default_factory=FakeSheetValues)
    calendar: FakeCalendar = field(default_factory=FakeCalendar)

    def service(self, api_name: str) -> Any:
        """The service object Google's client factory would build for ``api_name``."""
        drive, docs, sheet, calendar = self.drive, self.docs, self.sheet, self.calendar
        match api_name:
            case "drive":
                return SimpleNamespace(files=lambda: drive)
            case "docs":
                return SimpleNamespace(documents=lambda: docs)
            case "sheets":
                return SimpleNamespace(spreadsheets=lambda: SimpleNamespace(values=lambda: sheet))
            case "calendar":
                return SimpleNamespace(
                    freebusy=lambda: SimpleNamespace(query=calendar.query), events=lambda: SimpleNamespace(insert=calendar.insert)
                )
        raise AssertionError(api_name)

    def add_timeline_report(self) -> None:
        """The incident's report document from the template, with an empty timeline section."""
        self.docs.texts[REPORT_DOCUMENT_ID] = f"Incident report\nTimeline\n{TIMELINE_PLACEHOLDER}\n\nTrigger\n"

    def add_incident_report(self, status: str = "Open") -> None:
        """The incident's report document and its row in the incident list sheet."""
        self.docs.texts[REPORT_DOCUMENT_ID] = f"Incident report\nStatus: {status}\nTrigger\n"
        self.drive.add(
            "F0REPORT",
            "2026-10-checkout",
            parent=get_incident_core_settings().folder_id,
            folder=False,
            ic_id="U0OLDIC",
            ol_id="U0OLDOL",
        )
        self.sheet.rows = [
            ["Date", "Name", "Product", "Status", "Channel"],
            [*INCIDENT_SHEET_ROW[:3], status, INCIDENT_SHEET_ROW[4]],
        ]


@dataclass
class IncidentSurface:
    """The legacy handlers and the ``/sre`` command on one Bolt app, over faked incident edges.

    ``slack`` dispatches commands and interactions; ``table``, ``google`` and
    ``slack.client`` are the faked edges whose state the tests read back;
    ``provider`` is the Slack provider ``/sre`` routes through, on which a
    rebuilt plugin registers its commands.
    """

    slack: LegacyHandlerHarness
    table: FakeIncidentTable
    google: FakeGoogleWorkspace
    provider: SlackPlatformProvider

    def sre(self, text: str, channel_name: str = INCIDENT_CHANNEL_NAME) -> BoltResponse:
        """Send ``/sre <text>`` from the incident channel."""
        return self.slack.command("sre", text, channel_name=channel_name)


@pytest.fixture
def legacy_sre_web_client_seam(legacy_handler_harness: LegacyHandlerHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    """Internal legacy seam: the ``/sre`` dispatcher's own Slack client factory.

    ``modules/sre/platforms/slack.py`` builds its WebClient through a private
    factory rather than from Bolt's injected client, so no external edge is
    reachable for the ``/sre incident`` subcommands. The factory is pointed at
    the harness's recording client. Owning rebuild task: TASK-145.13, which
    deletes the legacy ``/sre incident`` dispatcher and the other pins still
    reaching it through this factory; this fixture is deleted there.
    """
    monkeypatch.setattr(sre_slack, "_web_client", lambda: legacy_handler_harness.client)


@pytest.fixture
def incident_surface(
    legacy_handler_harness: LegacyHandlerHarness, legacy_sre_web_client_seam: None, monkeypatch: pytest.MonkeyPatch
) -> Iterator[IncidentSurface]:
    """``/sre`` registered beside the legacy handlers, with the incident module's external edges faked.

    The edges are the boto3 DynamoDB client under the incidents table adapter,
    the Google client factory under the Drive, Docs, Sheets and Calendar calls and, from
    ``legacy_handler_harness``, the Slack Web API, ``response_url`` and Sentinel.
    The ``/sre`` client factory is the one internal legacy seam
    (``legacy_sre_web_client_seam``).
    The spreadsheet provider is cached, so its cache is cleared around the test.
    """
    dynamodb = FakeDynamoDbClient()
    google = FakeGoogleWorkspace()
    monkeypatch.setattr(dynamodb_adapter, "get_aws_client", lambda *args, **kwargs: dynamodb)
    monkeypatch.setattr(google_workspace_client, "_build_service", lambda api_name, *args, **kwargs: google.service(api_name))
    get_spreadsheet_provider.cache_clear()

    settings = SimpleNamespace(app_token=SecretStr("xapp-test"), bot_token=SecretStr("xoxb-test"))
    provider = SlackPlatformProvider(
        settings=cast(SlackSettings, settings),
        formatter=SlackBlockKitFormatter(),
        command_prefix=legacy_handler_harness.command_prefix,
    )
    provider._app = legacy_handler_harness.app
    provider._client = legacy_handler_harness.client
    _register_legacy_slack_commands(provider, structlog.get_logger())
    provider._auto_register_root_commands()

    yield IncidentSurface(slack=legacy_handler_harness, table=FakeIncidentTable(dynamodb), google=google, provider=provider)
    get_spreadsheet_provider.cache_clear()


def attach_rebuilt_listeners_first(surface: IncidentSurface) -> None:
    """Attach the plugins' registered interaction listeners ahead of the legacy handlers, as production orders them.

    Production attaches them in ``initialize_app`` before ``_register_legacy_handlers``
    (server/lifespan.py), and Bolt runs the first listener whose matchers pass, so a
    value-scoped alias answers its values and every other value reaches the legacy
    listener (decisions/transport-slack.md). The harness registers the legacy handlers
    first, so the newly attached listeners are moved to the front of Bolt's list.
    """
    listeners = surface.slack.app._listeners
    legacy = list(listeners)
    surface.provider._attach_interaction_listeners()
    listeners[:] = listeners[len(legacy) :] + legacy


# Reading a recorded view and answering it, so a test never hard-codes a modal-internal id.

_VIEW_CALLS = ("views_open", "views_push", "views_update")


def last_view(client: FakeSlackClient) -> dict[str, Any]:
    """The view of the latest ``views.open``, ``views.push`` or ``views.update`` call."""
    sent = [kwargs for name, kwargs in client.calls if name in _VIEW_CALLS]
    view: dict[str, Any] = sent[-1]["view"]
    return view


def view_elements(view: dict[str, Any]) -> list[dict[str, Any]]:
    """Every interactive element of a view, whether an accessory, an action-block element or an input."""
    elements: list[dict[str, Any]] = []
    for block in view["blocks"]:
        elements.extend(block.get("elements", []))
        for key in ("accessory", "element"):
            if key in block:
                elements.append(block[key])
    return [element for element in elements if "action_id" in element]


def view_button(view: dict[str, Any], *, value: str) -> dict[str, Any]:
    """The button of a view that carries ``value``; its ``action_id`` is the one Slack would send back."""
    return next(element for element in view_elements(view) if element["type"] == "button" and element.get("value") == value)


def view_text(view: dict[str, Any]) -> str:
    """All section and header text of a view, one block per line, for assertions on what a user reads."""
    lines = []
    for block in view["blocks"]:
        lines.append(block.get("text", {}).get("text", ""))
        lines.extend(field_["text"] for field_ in block.get("fields", []))
    return "\n".join(line for line in lines if line)


def click_payload(view: dict[str, Any], button: dict[str, Any]) -> dict[str, Any]:
    """The block_actions payload Slack sends when ``button`` of the open ``view`` is pressed."""
    return {
        "type": "block_actions",
        "trigger_id": "trigger-click",
        "actions": [{"type": "button", "action_id": button["action_id"], "value": button.get("value")}],
        "view": {
            "id": VIEW_ID,
            "root_view_id": ROOT_VIEW_ID,
            "type": "modal",
            "callback_id": view.get("callback_id", ""),
            "private_metadata": view.get("private_metadata", ""),
        },
    }


_ANSWER_STATE = {
    "users_select": lambda answer: {"selected_user": answer},
    "plain_text_input": lambda answer: {"value": answer},
    "static_select": lambda answer: {"selected_option": {"value": answer}},
    "datepicker": lambda answer: {"selected_date": answer},
    "timepicker": lambda answer: {"selected_time": answer},
    "datetimepicker": lambda answer: {"selected_date_time": answer},
    "number_input": lambda answer: {"value": answer},
}


def submission_payload(view: dict[str, Any], answers: Mapping[str, str | int | None]) -> dict[str, Any]:
    """The view_submission payload Slack sends when ``view`` is submitted with ``answers`` by input block id.

    The callback id, private metadata, block ids and action ids all come from
    ``view``; an input left out of ``answers`` keeps its initial value.
    """
    values: dict[str, Any] = {}
    for block in view["blocks"]:
        if block.get("type") != "input":
            continue
        element = block["element"]
        initial = element.get("initial_user") or element.get("initial_value") or element.get("initial_date")
        initial = initial or element.get("initial_time") or element.get("initial_date_time")
        initial = initial or (element.get("initial_option") or {}).get("value")
        answer = answers.get(block["block_id"], initial)
        values[block["block_id"]] = {element["action_id"]: {"type": element["type"], **_ANSWER_STATE[element["type"]](answer)}}
    return {
        "type": "view_submission",
        "trigger_id": "trigger-submit",
        "view": {
            "id": VIEW_ID,
            "root_view_id": ROOT_VIEW_ID,
            "type": "modal",
            "callback_id": view["callback_id"],
            "private_metadata": view.get("private_metadata", ""),
            "blocks": view["blocks"],
            "state": {"values": values},
        },
    }


# The webhook route: POST /hook/{webhook_id} through the production app, over faked external edges.

WEBHOOK_ID = "5e6f7a8b-9c0d-4e1f-a2b3-c4d5e6f7a8b9"
WEBHOOK_CHANNEL = "C0WEBHOOK"
WEBHOOK_SENDER_IP = "203.0.113.7"
OPS_CHANNEL_ID = "C0OPSROOM"
NOTIFY_LEAK_CHANNEL_ID = "C0NOTIFYLEAK"
NOTIFY_ONCALL_GROUP_ID = "S0NOTIFYONCALL"
SNS_CERT_URL = "https://sns.ca-central-1.amazonaws.com/SimpleNotificationService-test.pem"
SNS_SUBSCRIBE_URL = "https://sns.ca-central-1.amazonaws.com/?Action=ConfirmSubscription&Token=token-1"
SNS_TOPIC_ARN = "arn:aws:sns:ca-central-1:123456789012:sre-alerts"
SNS_TIMESTAMP = "2026-11-20T12:00:00.000Z"
_SNS_CONFIRMATION_TYPES = ("SubscriptionConfirmation", "UnsubscribeConfirmation")


class FakeWebhooksDynamoDbClient:
    """In-memory stand-in for the boto3 DynamoDB client the webhooks table adapter wraps.

    Serves ``get_item`` by id and the ``SET <counter> = if_not_exists(...) + :inc`` counter
    update. ``read_error`` and ``counter_error`` are raised by the matching request, the
    way a throttled or rejected table answers.
    """

    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}
        self.reads = 0
        self.read_error: ClientError | None = None
        self.counter_error: ClientError | None = None

    def get_item(self, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["TableName"] == "webhooks"
        self.reads += 1
        if self.read_error is not None:
            raise self.read_error
        item = self.items.get(kwargs["Key"]["id"]["S"])
        return {"Item": dict(item)} if item is not None else {}

    def update_item(self, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["TableName"] == "webhooks"
        if self.counter_error is not None:
            raise self.counter_error
        counter = re.match(r"SET (\w+) = if_not_exists", kwargs["UpdateExpression"])
        assert counter is not None, kwargs["UpdateExpression"]
        item = self.items[kwargs["Key"]["id"]["S"]]
        current = int(item.get(counter.group(1), {"N": "0"})["N"])
        item[counter.group(1)] = {"N": str(current + 1)}
        return {}


class WebhookRecords:
    """The webhook records the route looks up and counts, seeded and read back through domain values."""

    def __init__(self, client: FakeWebhooksDynamoDbClient) -> None:
        self._client = client

    def seed(
        self,
        webhook_id: str = WEBHOOK_ID,
        *,
        channel: str = WEBHOOK_CHANNEL,
        active: bool = True,
        hook_type: str | None = "alert",
    ) -> None:
        """Add one webhook; ``hook_type=None`` stores a record without the attribute, as older webhooks are."""
        item: dict[str, Any] = {
            "id": {"S": webhook_id},
            "channel": {"S": channel},
            "name": {"S": "pinned webhook"},
            "active": {"BOOL": active},
            "invocation_count": {"N": "0"},
        }
        if hook_type is not None:
            item["hook_type"] = {"S": hook_type}
        self._client.items[webhook_id] = item

    def invocation_count(self, webhook_id: str = WEBHOOK_ID) -> int:
        """How many times the route counted an invocation of ``webhook_id``."""
        return int(self._client.items[webhook_id]["invocation_count"]["N"])

    @property
    def reads(self) -> int:
        """How many lookups reached the store."""
        return self._client.reads

    def fail_reads(self, code: str) -> None:
        """Make every later lookup fail with the AWS error ``code``."""
        self._client.read_error = ClientError({"Error": {"Code": code, "Message": f"{code} from the table"}}, "GetItem")

    def fail_counter_writes(self, code: str) -> None:
        """Make every later invocation-counter write fail with the AWS error ``code``."""
        self._client.counter_error = ClientError({"Error": {"Code": code, "Message": f"{code} from the table"}}, "UpdateItem")


@lru_cache(maxsize=1)
def _sns_signing_material() -> tuple[rsa.RSAPrivateKey, bytes]:
    """A test RSA key and the PEM of a self-signed certificate for it, built once per process.

    The SNS validator caches the certificate it fetches by URL for the life of the
    process, so every test must sign with the same key.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "sns.test")])
    issued = datetime(2026, 1, 1, tzinfo=UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(issued)
        .not_valid_after(issued + timedelta(days=3650))
        .sign(key, hashes.SHA256())
    )
    return key, certificate.public_bytes(serialization.Encoding.PEM)


class SnsSigner:
    """Builds AWS SNS HTTP messages signed over the canonical string the way SNS signs them."""

    def message(
        self,
        message_type: str = "Notification",
        *,
        message: str,
        subject: str | None = None,
        topic_arn: str = SNS_TOPIC_ARN,
        signature_version: str = "1",
        signing_cert_url: str = SNS_CERT_URL,
        digest: hashes.HashAlgorithm | None = None,
    ) -> dict[str, str]:
        """A signed SNS message of ``message_type``; ``digest`` defaults to SHA1, the SignatureVersion 1 hash."""
        fields = {
            "Type": message_type,
            "MessageId": "6f1b2c3d-0000-4000-8000-000000000001",
            "TopicArn": topic_arn,
            "Message": message,
            "Timestamp": SNS_TIMESTAMP,
            "SignatureVersion": signature_version,
            "SigningCertURL": signing_cert_url,
        }
        if subject is not None:
            fields["Subject"] = subject
        if message_type in _SNS_CONFIRMATION_TYPES:
            fields["Token"] = "token-1"
            fields["SubscribeURL"] = SNS_SUBSCRIBE_URL
        key, _ = _sns_signing_material()
        # SignatureVersion 1 is SHA1 by definition; the route's validator verifies exactly this.
        algorithm = digest or hashes.SHA1()  # noqa: S303
        signature = key.sign(self._canonical(fields).encode(), padding.PKCS1v15(), algorithm)
        return {**fields, "Signature": base64.b64encode(signature).decode()}

    @staticmethod
    def _canonical(fields: dict[str, str]) -> str:
        if fields["Type"] in _SNS_CONFIRMATION_TYPES:
            names = ("Message", "MessageId", "SubscribeURL", "Timestamp", "Token", "TopicArn", "Type")
        elif "Subject" in fields:
            names = ("Message", "MessageId", "Subject", "Timestamp", "TopicArn", "Type")
        else:
            names = ("Message", "MessageId", "Timestamp", "TopicArn", "Type")
        return "".join(f"{name}\n{fields.get(name)}\n" for name in names)


@dataclass
class SnsEdges:
    """The signer and the HTTP edge SNS validation and subscription confirmation reach."""

    signer: SnsSigner
    http: requests_mock_module.Mocker

    @property
    def subscribe_requests(self) -> list[Any]:
        """The GETs made to the SNS ``SubscribeURL``."""
        return [request for request in self.http.request_history if request.url == SNS_SUBSCRIBE_URL]


@pytest.fixture
def sns(requests_mock: requests_mock_module.Mocker) -> SnsEdges:
    """Real SNS signing over a faked HTTP edge: the signing certificate URL and the ``SubscribeURL``.

    The route's signature validation runs unmodified against a test key; only the two
    SNS hosts it fetches are answered. Any other outbound ``requests`` call is an error.
    """
    _, certificate = _sns_signing_material()
    requests_mock.get(SNS_CERT_URL, content=certificate)
    requests_mock.get(SNS_SUBSCRIBE_URL, text="confirmed")
    return SnsEdges(signer=SnsSigner(), http=requests_mock)


def mount_webhook_routes(app: FastAPI) -> None:
    """Harness step: serve the webhook route on the production app.

    A no-op today: ``create_app()`` includes the legacy routers, which serve the route at
    ``/hook/{webhook_id}`` and ``/api/v1/hook/{webhook_id}``. Owning rebuild task:
    TASK-37.4, which removes the legacy router and rewires this step to the plugin
    manager's ``register_routes``, as the edge route probe does; assertions stay unchanged.
    """


def set_webhook_bot_state(app: FastAPI) -> None:
    """Harness step: give the app the Slack bot state the route reads, as the lifespan does (``app.state.bot``).

    Owning rebuild task: TASK-37.4, which rewires this step to the state the rebuilt
    route reads. The client is a real ``WebClient``; its requests are routed to the
    Slack fake by ``routed_slack_client``.
    """
    app.state.bot = SimpleNamespace(client=WebClient(token="xoxb-test"))


@pytest.fixture(autouse=True)
def reset_webhook_process_state() -> Iterator[None]:
    """Clear the process-wide state the webhook route leaves behind: the rate-limit counters and cached settings."""
    getters = (get_sre_ops_settings, get_notify_api_key_leak_settings, get_notify_settings, get_aws_settings)
    for getter in getters:
        getter.cache_clear()
    get_limiter().reset()
    yield
    get_limiter().reset()
    for getter in getters:
        getter.cache_clear()


class WebhookSurface:
    """The production app serving ``POST /hook/{webhook_id}``, with its external edges faked.

    ``records`` is the webhook store, ``slack`` the Slack Web API (every ``chat.postMessage``
    of the route, the ops channel and the notify channel lands on it) and
    ``sentinel_events`` what reached Sentinel.
    """

    def __init__(self, client: TestClient, records: WebhookRecords, edges: RoutedSlackEdges) -> None:
        self.client = client
        self.records = records
        self.slack = edges.client
        self.sentinel_events = edges.sentinel_events

    def post(
        self,
        body: Any,
        webhook_id: str = WEBHOOK_ID,
        *,
        prefix: str = "/hook",
        headers: dict[str, str] | None = None,
    ) -> Any:
        """POST ``body`` as JSON to the route."""
        return self.client.post(f"{prefix}/{webhook_id}", json=body, headers=headers)

    def post_content(self, content: bytes | str, webhook_id: str = WEBHOOK_ID, *, headers: dict[str, str] | None = None) -> Any:
        """POST a raw request body, so a test controls exactly what is on the wire."""
        return self.client.post(f"/hook/{webhook_id}", content=content, headers=headers)

    def remove_bot(self) -> None:
        """Start the app without the Slack bot, as when the lifespan found no Slack provider."""
        self.client.app.state.bot = None  # type: ignore[attr-defined]

    def channel_posts(self, channel: str) -> list[dict[str, Any]]:
        """Every message posted to ``channel``, in order."""
        return [kwargs for name, kwargs in self.slack.calls if name == "chat_postMessage" and kwargs.get("channel") == channel]

    @property
    def webhook_posts(self) -> list[dict[str, Any]]:
        """The messages posted to the webhook's channel."""
        return self.channel_posts(WEBHOOK_CHANNEL)

    @property
    def ops_messages(self) -> list[str]:
        """The texts posted to the ops channel."""
        return [post["text"] for post in self.channel_posts(OPS_CHANNEL_ID)]

    @property
    def all_posts(self) -> list[dict[str, Any]]:
        """Every ``chat.postMessage`` the request made, whatever the channel."""
        return [kwargs for name, kwargs in self.slack.calls if name == "chat_postMessage"]

    def sentinel_event_names(self) -> list[str]:
        """The names of the events that reached Sentinel."""
        return [event["event"] for event in self.sentinel_events]


@pytest.fixture
def webhook_surface(routed_slack_client: RoutedSlackEdges, monkeypatch: pytest.MonkeyPatch) -> WebhookSurface:
    """The production app, built without its lifespan, serving the webhook route over faked edges.

    The edges are the boto3 DynamoDB client under the webhooks table adapter, the
    Slack Web API and Sentinel (``routed_slack_client``), and the typed settings the
    ops channel and the API-key-leak response read, set the way the suite sets any
    slice. The lifespan is not run (it would post startup messages and boot plugins
    the route never reaches), so the routes and the ``app.state`` the route reads are
    named harness steps, ``mount_webhook_routes`` and ``set_webhook_bot_state``,
    rewired at TASK-37.4. ``slack_bolt``'s own ``App`` constructor is restored because
    the ops message helper builds a Bolt app to reach its client.
    """
    table = FakeWebhooksDynamoDbClient()
    monkeypatch.setattr(dynamodb_adapter, "get_aws_client", lambda *args, **kwargs: table)
    monkeypatch.setattr(App, "__init__", unpatched_app_init())
    monkeypatch.setenv("SRE_OPS__SRE_OPS_CHANNEL_ID", OPS_CHANNEL_ID)
    monkeypatch.setenv("NOTIFY_API_KEY_LEAK__CHANNEL_ID", NOTIFY_LEAK_CHANNEL_ID)
    monkeypatch.setenv("NOTIFY_API_KEY_LEAK__ONCALL_GROUP_ID", NOTIFY_ONCALL_GROUP_ID)
    for getter in (get_sre_ops_settings, get_notify_api_key_leak_settings):
        getter.cache_clear()
    app = create_app()
    mount_webhook_routes(app)
    set_webhook_bot_state(app)
    return WebhookSurface(TestClient(app, client=(WEBHOOK_SENDER_IP, 50000)), WebhookRecords(table), routed_slack_client)
