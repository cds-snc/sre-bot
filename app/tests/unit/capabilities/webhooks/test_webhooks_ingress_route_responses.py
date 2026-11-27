"""Unit tests for the ingress route's responses table (decisions/webhooks.md 5 Responses).

The router runs on a bare FastAPI app with ``get_ingress`` overridden: the processor comes
from ``processor_fakes`` (the real inbox store over the in-memory records fake), the protocols
are the real ones with a fixed clock and a static certificate port, and the instance store is a
dictionary by URL token. Each test asserts the status, the generic body and what was persisted.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from capabilities.webhooks.domain.inbox import ItemState, item_key
from capabilities.webhooks.domain.kinds import InstanceState, WebhookInstance
from capabilities.webhooks.entrypoints.http import Ingress, get_ingress, router
from capabilities.webhooks.entrypoints.http_aws_sns import AwsSnsProtocol
from capabilities.webhooks.entrypoints.http_legacy_slack_json import LegacySlackJsonProtocol
from capabilities.webhooks.settings import get_webhooks_settings
from contracts.operations import OperationResult, OperationStatus
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.unit.capabilities.webhooks.processor_fakes import World, instance, world
from tests.unit.capabilities.webhooks.sns_signing import SENT_AT, StaticCertificates, encoded, signed_message

pytestmark = pytest.mark.unit

TOKEN = "url-token-secret-1"
SNS_HEADERS = {"content-type": "text/plain; charset=UTF-8"}


@dataclass
class _UrlInstances:
    instances: dict[str, WebhookInstance]
    failure: OperationResult[WebhookInstance] | None = None

    async def by_url_id(self, webhook_id: str) -> OperationResult[WebhookInstance]:
        if self.failure is not None:
            return self.failure
        found = self.instances.get(webhook_id)
        return OperationResult.success(data=found) if found else OperationResult.error(OperationStatus.NOT_FOUND, "none")

    async def by_ref(self, instance_ref: str) -> OperationResult[WebhookInstance]:
        raise AssertionError("the route looks up by URL token only")


@dataclass
class _Harness:
    client: TestClient
    world: World
    instances: _UrlInstances
    certificates: StaticCertificates


def _harness(*, records: Any = None, legacy: bool = False) -> Iterator[_Harness]:
    settings = get_webhooks_settings()
    target = instance(protocol="legacy_slack_json", sender_kinds=()) if legacy else instance()
    w = world(records=records, instance_=target)
    certificates = StaticCertificates()
    instances = _UrlInstances({TOKEN: target})
    ingress = Ingress(
        instances=instances,
        processor=w.processor,
        protocols={
            "aws_sns": AwsSnsProtocol(certificates, settings, clock=lambda: SENT_AT + timedelta(minutes=1)),
            "legacy_slack_json": LegacySlackJsonProtocol(settings),
        },
        settings=settings,
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_ingress] = lambda: ingress
    with TestClient(app) as client:
        yield _Harness(client, w, instances, certificates)


@pytest.fixture
def sns() -> Iterator[_Harness]:
    yield from _harness()


@pytest.fixture
def legacy() -> Iterator[_Harness]:
    yield from _harness(legacy=True)


def _sns_alert() -> bytes:
    return encoded(signed_message(message='{"source": "aws.budgets", "detail": {"name": "sandbox"}}'))


def test_a_verified_delivery_is_persisted_and_answered_200(sns: _Harness) -> None:
    response = sns.client.post(f"/hook/{TOKEN}", content=_sns_alert(), headers=SNS_HEADERS)

    assert (response.status_code, response.json()) == (200, {"detail": "accepted"})
    assert sns.world.poster.posts


def test_a_duplicate_is_answered_200_with_no_work(sns: _Harness) -> None:
    sns.client.post(f"/hook/{TOKEN}", content=_sns_alert(), headers=SNS_HEADERS)
    posts = len(sns.world.poster.posts)

    response = sns.client.post(f"/hook/{TOKEN}", content=_sns_alert(), headers=SNS_HEADERS)

    assert response.status_code == 200 and len(sns.world.poster.posts) == posts


def test_a_downstream_failure_is_still_answered_200_and_left_for_retry(sns: _Harness) -> None:
    sns.world.poster.script["C1"] = [OperationResult.transient_error("slack down")]

    response = sns.client.post(f"/hook/{TOKEN}", content=_sns_alert(), headers=SNS_HEADERS)

    assert response.status_code == 200
    stored = sns.client.portal.call(sns.world.inbox.get, item_key("ref-1", "6f2b-4c1a-9d8e"))
    assert stored.data is not None and stored.data.state is ItemState.RETRY


@pytest.mark.parametrize(
    ("body", "status", "detail"),
    [
        pytest.param(b"{not json", 400, "invalid", id="undecodable"),
        pytest.param(encoded({**signed_message(), "Message": "tampered"}), 403, "forbidden", id="bad-signature"),
    ],
)
def test_a_refused_body_gets_a_generic_answer_and_nothing_is_persisted(
    sns: _Harness, body: bytes, status: int, detail: str
) -> None:
    response = sns.client.post(f"/hook/{TOKEN}", content=body, headers=SNS_HEADERS)

    assert (response.status_code, response.json()) == (status, {"detail": detail})
    assert sns.world.poster.posts == []


def test_an_unknown_or_disabled_instance_is_404(sns: _Harness) -> None:
    unknown = sns.client.post("/hook/nope", content=_sns_alert(), headers=SNS_HEADERS)
    sns.instances.instances[TOKEN] = instance(state=InstanceState.DISABLED)
    disabled = sns.client.post(f"/hook/{TOKEN}", content=_sns_alert(), headers=SNS_HEADERS)

    assert (unknown.status_code, disabled.status_code) == (404, 404)


def test_an_instance_with_an_unknown_protocol_is_404(sns: _Harness) -> None:
    sns.instances.instances[TOKEN] = instance(protocol="carrier_pigeon")

    assert sns.client.post(f"/hook/{TOKEN}", content=_sns_alert(), headers=SNS_HEADERS).status_code == 404


def test_only_post_is_routed(sns: _Harness) -> None:
    assert sns.client.get(f"/hook/{TOKEN}").status_code == 405


def test_an_unexpected_content_type_is_415(sns: _Harness) -> None:
    response = sns.client.post(f"/hook/{TOKEN}", content=_sns_alert(), headers={"content-type": "application/xml"})

    assert response.status_code == 415


def test_a_declared_length_over_the_cap_is_413_unread(sns: _Harness) -> None:
    cap = get_webhooks_settings().aws_sns_max_body_bytes
    response = sns.client.post(f"/hook/{TOKEN}", content=b"x" * (cap + 1), headers=SNS_HEADERS)

    assert response.status_code == 413


def test_a_streamed_body_without_a_length_over_the_cap_is_413(legacy: _Harness) -> None:
    cap = get_webhooks_settings().legacy_slack_json_max_body_bytes

    def chunks() -> Iterator[bytes]:
        for _ in range(cap // 1024 + 2):
            yield b" " * 1024

    response = legacy.client.post(f"/hook/{TOKEN}", content=chunks(), headers={"content-type": "application/json"})

    assert response.status_code == 413


class _InboxDown(InMemoryRecordStore):
    def put_if_not_exists(self, table: Any, item: dict[str, Any]) -> OperationResult:
        return OperationResult.transient_error("throttled")


@pytest.fixture
def inbox_down() -> Iterator[_Harness]:
    yield from _harness(records=_InboxDown())


def test_an_unavailable_inbox_is_503_with_retry_after(inbox_down: _Harness) -> None:
    harness = inbox_down

    response = harness.client.post(f"/hook/{TOKEN}", content=_sns_alert(), headers=SNS_HEADERS)

    assert response.status_code == 503
    assert response.headers["retry-after"] == str(get_webhooks_settings().unavailable_retry_after_seconds)
    assert harness.world.poster.posts == []


def test_an_unavailable_instance_store_or_certificate_host_is_503(sns: _Harness) -> None:
    sns.certificates.result = OperationResult.transient_error("timeout")
    no_certificate = sns.client.post(f"/hook/{TOKEN}", content=_sns_alert(), headers=SNS_HEADERS)
    sns.instances.failure = OperationResult.transient_error("throttled")
    no_instances = sns.client.post(f"/hook/{TOKEN}", content=_sns_alert(), headers=SNS_HEADERS)

    assert (no_certificate.status_code, no_instances.status_code) == (503, 503)


def test_a_legacy_delivery_is_accepted_and_passed_through(legacy: _Harness) -> None:
    response = legacy.client.post(f"/hook/{TOKEN}", json={"text": "deployed"}, headers={"idempotency-key": "d-1"})

    assert response.status_code == 200
    assert [conversation for conversation, _ in legacy.world.poster.posts] == ["C1", "C2"]


def test_the_url_token_never_reaches_a_log(sns: _Harness) -> None:
    with capture_logs() as logs:
        sns.client.post(f"/hook/{TOKEN}", content=_sns_alert(), headers=SNS_HEADERS)
        sns.client.post(f"/hook/{TOKEN}", content=encoded({**signed_message(), "Message": "x"}), headers=SNS_HEADERS)

    assert logs and TOKEN not in repr(logs)
