"""Pins how ``POST /hook/{webhook_id}`` looks up, limits and answers a request, through the production ASGI app.

The webhook record store (a DynamoDB client), the Slack Web API and Sentinel are faked
at their external edges; the real middleware stack, rate limiter, route and legacy
payload pipeline run. Assertions are the HTTP answer, what reached Slack and the record
counter. ``test_legacy_only_webhook_*`` tests pin behaviour the webhooks rebuild ends and
are deleted by the task named in each docstring.
"""

import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from integrations.aws.settings import get_aws_settings
from server.configuration import get_server_settings
from tests.integration.legacy_surface.conftest import (
    WEBHOOK_ID,
    WEBHOOK_SENDER_IP,
    WebhookSurface,
)

pytestmark = pytest.mark.integration

OTHER_WEBHOOK_ID = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"
TEXT_PAYLOAD = {"text": "disk usage at 91 percent on the batch host"}


def invocation_events(entries: list[dict]) -> list[dict]:
    """The ``webhook_invocation`` fingerprint events among captured log entries."""
    return [entry for entry in entries if entry.get("event") == "webhook_invocation"]


def test_webhook_route_bare_hook_path_posts_the_message_and_counts_the_invocation(webhook_surface: WebhookSurface) -> None:
    """The durable ``/hook/{id}`` entry answers ``{"ok": true}``, posts to the record's channel and counts once."""
    webhook_surface.records.seed()

    response = webhook_surface.post(TEXT_PAYLOAD)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert [post["text"] for post in webhook_surface.webhook_posts] == [TEXT_PAYLOAD["text"]]
    assert webhook_surface.records.invocation_count() == 1


def test_webhook_route_api_v1_mount_serves_route(webhook_surface: WebhookSurface) -> None:
    """The versioned mount serves the same route: same answer, same post, same count.

    Retention of this mount is decided by the webhooks architecture review and the cutover
    task's AC #6 (a production access-log check); until then both mounts stay served.
    """
    webhook_surface.records.seed()

    response = webhook_surface.post(TEXT_PAYLOAD, prefix="/api/v1/hook")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert [post["text"] for post in webhook_surface.webhook_posts] == [TEXT_PAYLOAD["text"]]
    assert webhook_surface.records.invocation_count() == 1


def test_webhook_route_unknown_webhook_answers_404_and_posts_nothing(webhook_surface: WebhookSurface) -> None:
    """A webhook id with no record answers 404 and reaches no Slack or Sentinel edge."""
    response = webhook_surface.post(TEXT_PAYLOAD, webhook_id="not-a-webhook")

    assert response.status_code == 404
    assert response.json() == {"detail": "Webhook not found"}
    assert webhook_surface.all_posts == []
    assert webhook_surface.sentinel_events == []


def test_webhook_route_inactive_webhook_answers_404_without_counting(webhook_surface: WebhookSurface) -> None:
    """An inactive webhook answers 404, posts nothing and leaves the invocation counter untouched."""
    webhook_surface.records.seed(active=False)

    response = webhook_surface.post(TEXT_PAYLOAD)

    assert response.status_code == 404
    assert response.json() == {"detail": "Webhook not active"}
    assert webhook_surface.all_posts == []
    assert webhook_surface.records.invocation_count() == 0


@pytest.mark.parametrize(
    ("error_code", "configured_retry_after", "expected_retry_after"),
    [
        ("ThrottlingException", "5", "5"),
        ("ThrottlingException", "60", "60"),
        ("ValidationException", None, None),
    ],
    ids=["throttled-5s", "throttled-60s", "rejected-no-hint"],
)
def test_webhook_route_unavailable_store_answers_503_with_retry_after(
    webhook_surface: WebhookSurface,
    monkeypatch: pytest.MonkeyPatch,
    error_code: str,
    configured_retry_after: str | None,
    expected_retry_after: str | None,
) -> None:
    """A failed record lookup answers a generic 503, never 404, so a sender such as SNS redelivers.

    The store fake raises a throttling error (classified transient, the retry hint is the
    configured whole-second delay) or a rejection the adapter does not classify (no hint).
    The body never carries the provider's error code, Retry-After is sent only when a delay
    is known, and the invocation counter stays untouched.
    """
    if configured_retry_after is not None:
        monkeypatch.setenv("AWS__TRANSIENT_RETRY_AFTER_SECONDS", configured_retry_after)
        get_aws_settings.cache_clear()
    webhook_surface.records.seed()
    webhook_surface.records.fail_reads(error_code)

    response = webhook_surface.post(TEXT_PAYLOAD)

    assert response.status_code == 503
    assert response.json() == {"detail": "Service temporarily unavailable"}
    assert error_code not in response.text
    assert response.headers.get("retry-after") == expected_retry_after
    assert webhook_surface.all_posts == []
    assert webhook_surface.records.invocation_count() == 0


@pytest.mark.parametrize("error_code", ["ThrottlingException", "ValidationException"], ids=["classified", "unclassified"])
def test_webhook_route_counter_write_failure_still_delivers(webhook_surface: WebhookSurface, error_code: str) -> None:
    """A failed invocation-counter write is dropped: the message is still posted and the sender gets 200."""
    webhook_surface.records.seed()
    webhook_surface.records.fail_counter_writes(error_code)

    response = webhook_surface.post(TEXT_PAYLOAD)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert [post["text"] for post in webhook_surface.webhook_posts] == [TEXT_PAYLOAD["text"]]


def test_webhook_route_oversized_body_answers_413_before_any_lookup(webhook_surface: WebhookSurface) -> None:
    """A body whose Content-Length is over the configured cap is refused before the record is read."""
    webhook_surface.records.seed()
    cap = get_server_settings().webhook_max_body_bytes

    response = webhook_surface.post_content(b"x" * (cap + 1), headers={"content-type": "application/json"})

    assert response.status_code == 413
    assert webhook_surface.records.reads == 0
    assert webhook_surface.all_posts == []


def test_webhook_route_body_just_under_the_cap_is_served(webhook_surface: WebhookSurface) -> None:
    """A body that stays just under the cap is still served and its text posted unchanged.

    The bulk is a field the route does not scan, so the test measures the cap, not the
    text-rewriting passes.
    """
    webhook_surface.records.seed(hook_type="info")
    cap = get_server_settings().webhook_max_body_bytes

    response = webhook_surface.post({"text": "padded sender", "username": "u" * (cap - 1024)})

    assert response.status_code == 200
    assert [post["text"] for post in webhook_surface.webhook_posts] == ["padded sender"]


def test_webhook_route_json_string_that_is_not_json_answers_400(webhook_surface: WebhookSurface) -> None:
    """A JSON string body is parsed as JSON itself; text that is not JSON answers 400 before any lookup."""
    webhook_surface.records.seed()

    response = webhook_surface.post('{"invalid_json": "missing_end_quote}')

    assert response.status_code == 400
    assert webhook_surface.records.reads == 0
    assert webhook_surface.all_posts == []


def test_webhook_route_json_string_holding_an_object_is_served(webhook_surface: WebhookSurface) -> None:
    """A JSON string whose content is a JSON object is accepted as that object."""
    webhook_surface.records.seed(hook_type="info")

    response = webhook_surface.post('{"text": "sent as a string"}')

    assert response.status_code == 200
    assert [post["text"] for post in webhook_surface.webhook_posts] == ["sent as a string"]


@pytest.mark.parametrize(
    "content",
    [b'{"text": "cut off', b"[1, 2, 3]"],
    ids=["invalid-json-on-the-wire", "json-array"],
)
def test_webhook_route_body_that_is_neither_object_nor_string_answers_422(
    webhook_surface: WebhookSurface, content: bytes
) -> None:
    """Invalid JSON on the wire and a JSON array fail request validation with 422, before any lookup."""
    webhook_surface.records.seed()

    response = webhook_surface.post_content(content, headers={"content-type": "application/json"})

    assert response.status_code == 422
    assert webhook_surface.records.reads == 0
    assert webhook_surface.all_posts == []


def test_webhook_route_slack_bot_absent_answers_503_and_posts_nothing(webhook_surface: WebhookSurface) -> None:
    """With no Slack bot on the app a payload that should be posted answers 503 and reaches no Slack edge."""
    webhook_surface.records.seed()
    webhook_surface.remove_bot()

    response = webhook_surface.post(TEXT_PAYLOAD)

    assert response.status_code == 503
    assert response.json() == {"detail": "Slack bot not initialized"}
    assert webhook_surface.all_posts == []
    assert webhook_surface.sentinel_events == []


def test_webhook_route_failed_slack_post_answers_500_and_logs_no_sentinel_event(webhook_surface: WebhookSurface) -> None:
    """A chat.postMessage failure answers 500 with a generic body and no ``webhook_sent`` event."""
    webhook_surface.records.seed()
    webhook_surface.slack.replies["chat_postMessage"] = RuntimeError("slack is down")

    response = webhook_surface.post(TEXT_PAYLOAD)

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to send message"}
    assert "slack is down" not in response.text
    assert webhook_surface.sentinel_event_names() == []


def test_webhook_route_successful_post_is_recorded_in_sentinel(webhook_surface: WebhookSurface) -> None:
    """Each delivered message sends one ``webhook_sent`` event to Sentinel."""
    webhook_surface.records.seed()

    webhook_surface.post(TEXT_PAYLOAD)

    assert webhook_surface.sentinel_event_names() == ["webhook_sent"]


def test_webhook_route_answers_429_on_the_301st_request_in_a_window(webhook_surface: WebhookSurface) -> None:
    """The route admits 300 requests a minute from one address; the 301st answers 429 with the rate-limit body."""
    webhook_surface.records.seed(hook_type="info")

    statuses = [webhook_surface.post(TEXT_PAYLOAD).status_code for _ in range(300)]
    limited = webhook_surface.post(TEXT_PAYLOAD)

    assert set(statuses) == {200}
    assert limited.status_code == 429
    assert limited.json() == {"message": "Rate limit exceeded"}


def test_webhook_route_rate_limit_bucket_is_separate_for_each_webhook_id(webhook_surface: WebhookSurface) -> None:
    """Exhausting the limit on one webhook id leaves another id, from the same address, admitted."""
    webhook_surface.records.seed(WEBHOOK_ID, hook_type="info")
    webhook_surface.records.seed(OTHER_WEBHOOK_ID, hook_type="info")
    for _ in range(300):
        webhook_surface.post(TEXT_PAYLOAD)

    same_id = webhook_surface.post(TEXT_PAYLOAD)
    other_id = webhook_surface.post(TEXT_PAYLOAD, webhook_id=OTHER_WEBHOOK_ID)

    assert (same_id.status_code, other_id.status_code) == (429, 200)


def test_legacy_only_webhook_rate_limit_bucket_is_kept_per_sender_address(webhook_surface: WebhookSurface) -> None:
    """The limit counts requests per sender address: a second address is admitted while the first is limited.

    Ended by TASK-49, which keys the limit by webhook id (with per-webhook overrides), so
    after it every address shares the webhook's bucket and the second address is limited too.
    """
    webhook_surface.records.seed(hook_type="info")
    for _ in range(300):
        webhook_surface.post(TEXT_PAYLOAD)
    second_address = TestClient(webhook_surface.client.app, client=("198.51.100.9", 50000))

    first = webhook_surface.post(TEXT_PAYLOAD)
    second = second_address.post(f"/hook/{WEBHOOK_ID}", json=TEXT_PAYLOAD)

    assert (first.status_code, second.status_code) == (429, 200)


def test_webhook_route_unmatched_object_answers_400(webhook_surface: WebhookSurface) -> None:
    """An object no payload family accepts, such as an Opsgenie alert, answers 400 and posts nothing to the webhook channel."""
    webhook_surface.records.seed()

    response = webhook_surface.post({"alert": {"alertId": "a-1", "message": "disk full"}, "action": "Create"})

    assert response.status_code == 400
    assert response.json() == {"detail": "No matching model found for payload"}
    assert webhook_surface.webhook_posts == []


def test_legacy_only_webhook_unmatched_object_is_counted_before_it_is_refused(webhook_surface: WebhookSurface) -> None:
    """An unmatched object is refused with 400 only after the invocation counter was incremented.

    Ended by TASK-37.2, whose source-declared parsing decides acceptance from the webhook
    record, so an unmatched object stops being a 400 and the count follows the new rule.
    """
    webhook_surface.records.seed()

    response = webhook_surface.post({"alert": {"alertId": "a-1"}, "action": "Create"})

    assert response.status_code == 400
    assert webhook_surface.records.invocation_count() == 1


@pytest.mark.parametrize(
    "headers",
    [
        {"x-hub-signature": "sha1=abc"},
        {"x-hub-signature-256": "sha256=abc"},
        {"x-webhook-signature": "abc"},
        {"x-vendor-request-signature": "abc"},
    ],
    ids=["hub-sha1", "hub-sha256", "webhook-signature", "any-header-with-signature-in-its-name"],
)
def test_webhook_route_signature_header_is_recorded_in_the_fingerprint_and_not_verified(
    webhook_surface: WebhookSurface, headers: dict[str, str]
) -> None:
    """A signature header marks the fingerprint ``signing_indicator_present`` and is accepted unverified."""
    webhook_surface.records.seed(hook_type="info")

    with capture_logs() as entries:
        response = webhook_surface.post(TEXT_PAYLOAD, headers=headers)

    assert response.status_code == 200
    assert [event["signing_indicator_present"] for event in invocation_events(entries)] == [True]


def test_webhook_route_request_without_a_signature_header_has_no_signing_indicator(webhook_surface: WebhookSurface) -> None:
    """A request with no signature header is accepted and its fingerprint carries ``signing_indicator_present`` false."""
    webhook_surface.records.seed(hook_type="info")

    with capture_logs() as entries:
        response = webhook_surface.post(TEXT_PAYLOAD)

    assert response.status_code == 200
    assert [event["signing_indicator_present"] for event in invocation_events(entries)] == [False]


def test_webhook_route_delivered_request_logs_one_fingerprint_without_the_body(webhook_surface: WebhookSurface) -> None:
    """A delivered request logs one ``webhook_invocation`` event naming the webhook, sender address and agent, never the body."""
    webhook_surface.records.seed(hook_type="info")

    with capture_logs() as entries:
        webhook_surface.post(TEXT_PAYLOAD, headers={"user-agent": "fingerprint-agent/1.0"})

    [event] = invocation_events(entries)
    assert event["webhook_id"] == WEBHOOK_ID
    assert event["ip_address"] == WEBHOOK_SENDER_IP
    assert event["user_agent"] == "fingerprint-agent/1.0"
    assert "payload" not in event
    assert "body" not in event


@pytest.mark.parametrize(
    ("setup", "status"),
    [("unknown", 404), ("inactive", 404), ("not-json", 400), ("store-down", 503)],
)
def test_webhook_route_refused_request_still_logs_the_fingerprint(
    webhook_surface: WebhookSurface, setup: str, status: int
) -> None:
    """Every refusal path logs one ``webhook_invocation`` event for the webhook id the sender used."""
    webhook_surface.records.seed(active=setup != "inactive")
    if setup == "store-down":
        webhook_surface.records.fail_reads("ValidationException")
    webhook_id = "not-a-webhook" if setup == "unknown" else WEBHOOK_ID
    body = "{not json" if setup == "not-json" else TEXT_PAYLOAD

    with capture_logs() as entries:
        response = webhook_surface.post(body, webhook_id=webhook_id)

    assert response.status_code == status
    [event] = invocation_events(entries)
    assert event["webhook_id"] == webhook_id
    assert "payload" not in event
    assert "body" not in event


def test_legacy_only_webhook_fingerprint_names_the_guessed_payload_type(webhook_surface: WebhookSurface) -> None:
    """The fingerprint's ``matched_payload_type`` is the model the legacy scorer picked, and null when none matched.

    Ended by TASK-37.2, which replaces payload guessing with a declared source: the field
    then carries the source, and the query in the route's docstring changes with it.
    """
    webhook_surface.records.seed(hook_type="info")
    sender_bodies = {
        "WebhookPayload": {"text": "with a block list", "blocks": []},
        "SimpleTextPayload": {"text": "plain text"},
        "AccessRequest": {
            "account": "prod",
            "reason": "fix",
            "startDate": "2026-11-20T10:00:00",
            "endDate": "2026-11-20T12:00:00",
        },
        None: {"alert": {"alertId": "a-1"}, "action": "Create"},
    }

    seen = {}
    for expected, body in sender_bodies.items():
        with capture_logs() as entries:
            webhook_surface.post(body)
        [event] = invocation_events(entries)
        seen[expected] = event["matched_payload_type"]

    assert seen == {name: name for name in sender_bodies}
