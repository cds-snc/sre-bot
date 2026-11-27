"""The webhook ingress route: ``POST /hook/{webhook_id}`` (decisions/webhooks.md 3 Pipeline, 5 Responses).

Verify, decode, persist, process inline, answer. The instance declares its protocol, so the
body is decoded with that protocol only. The answer is 200 once the item is persisted,
whatever processing came to; 503 only when nothing could be persisted (the instance or inbox
store, or the SNS certificate host, was unavailable), with ``Retry-After``. Error bodies are
generic and never say why. The URL token is used for the instance lookup only: it is never
logged, stored or put in a key.

The router is built here and not mounted yet: no hookimpl registers it.
TODO(TASK-37.4.2): register the router through register_routes behind the per-instance flag.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Protocol

import structlog
import svcs
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from capabilities.webhooks.domain.inbox import ProtocolDelivery, Rejection, RejectReason
from capabilities.webhooks.domain.kinds import InstanceState, WebhookInstance
from capabilities.webhooks.entrypoints.http_aws_sns import AwsSnsProtocol
from capabilities.webhooks.entrypoints.http_legacy_slack_json import LegacySlackJsonProtocol
from capabilities.webhooks.interfaces import SnsCertificates, WebhookStore
from capabilities.webhooks.providers import build_processor, build_webhook_store, get_sns_http
from capabilities.webhooks.service import IngestOutcome, WebhookProcessor
from capabilities.webhooks.settings import WebhooksSettings, get_webhooks_settings
from contracts.operations import OperationStatus

logger = structlog.get_logger()


class WireProtocol(Protocol):
    """One wire protocol: its media types, its body cap, and verify-and-decode on the raw body."""

    @property
    def name(self) -> str: ...

    @property
    def content_types(self) -> tuple[str, ...]: ...

    @property
    def max_body_bytes(self) -> int: ...

    async def decode(
        self, body: bytes, headers: Mapping[str, str], instance: WebhookInstance
    ) -> ProtocolDelivery | Rejection: ...


class WebhookAnswer(BaseModel):
    """The generic answer to a webhook delivery; it never says why a delivery was refused."""

    detail: str = Field(description="A fixed word for the outcome.")


@dataclass(frozen=True)
class Ingress:
    """What the route needs: the instance store, the processor and the protocols by name."""

    instances: WebhookStore
    processor: WebhookProcessor
    protocols: Mapping[str, WireProtocol]
    settings: WebhooksSettings


def build_protocols(certificates: SnsCertificates, settings: WebhooksSettings) -> Mapping[str, WireProtocol]:
    """The closed set of wire protocols, by the name an instance declares."""
    protocols: tuple[WireProtocol, ...] = (
        AwsSnsProtocol(certificates, settings, clock=lambda: datetime.now(UTC)),
        LegacySlackJsonProtocol(settings),
    )
    return {protocol.name: protocol for protocol in protocols}


def get_ingress(services: svcs.fastapi.DepContainer) -> Ingress:
    """Build the ingress from the request's service container and the composition root."""
    settings = get_webhooks_settings()
    sns = get_sns_http()
    return Ingress(
        instances=build_webhook_store(services),
        processor=build_processor(services, confirmer=sns),
        protocols=build_protocols(sns, settings),
        settings=settings,
    )


def _answer(status: int, detail: str, *, retry_after: int | None = None) -> JSONResponse:
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
    return JSONResponse(status_code=status, content={"detail": detail}, headers=headers)


def _media_type(request: Request) -> str:
    return request.headers.get("content-type", "").split(";", 1)[0].strip().lower()


async def _read_capped(request: Request, cap: int) -> bytes | None:
    """The body, or None once it passes ``cap``; a declared length past the cap is refused unread."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > cap:
        return None
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > cap:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


_REJECTIONS = {RejectReason.UNDECODABLE: (400, "invalid"), RejectReason.UNAUTHENTIC: (403, "forbidden")}

router = APIRouter(tags=["webhooks"])


@router.post(
    "/hook/{webhook_id}",
    summary="Receive a webhook delivery",
    description="Verifies and persists one delivery for the instance behind the URL, then processes it.",
    response_model=WebhookAnswer,
    responses={
        400: {"model": WebhookAnswer, "description": "The body fails the instance's protocol decode."},
        403: {"model": WebhookAnswer, "description": "The delivery is not authentic."},
        404: {"model": WebhookAnswer, "description": "No active instance has this URL."},
        413: {"model": WebhookAnswer, "description": "The body is over the protocol's cap."},
        415: {"model": WebhookAnswer, "description": "The Content-Type is not one the protocol takes."},
        503: {"model": WebhookAnswer, "description": "Nothing could be persisted; retry after the Retry-After delay."},
    },
)
async def receive_webhook(webhook_id: str, request: Request, ingress: Annotated[Ingress, Depends(get_ingress)]) -> JSONResponse:
    """Verify, decode and persist one delivery, process it inline, and answer."""
    settings = ingress.settings
    unavailable = _answer(503, "unavailable", retry_after=settings.unavailable_retry_after_seconds)
    found = await ingress.instances.by_url_id(webhook_id)
    if found.status is OperationStatus.NOT_FOUND:
        return _answer(404, "not found")
    if not found.is_success or found.data is None:
        return unavailable
    instance = found.data
    log = logger.bind(instance_ref=instance.instance_ref, protocol=instance.protocol)
    protocol = ingress.protocols.get(instance.protocol)
    if instance.state is not InstanceState.ACTIVE or protocol is None:
        if protocol is None:
            log.warning("webhook_protocol_unknown")
        return _answer(404, "not found")
    if _media_type(request) not in protocol.content_types:
        return _answer(415, "unsupported media type")
    body = await _read_capped(request, protocol.max_body_bytes)
    if body is None:
        return _answer(413, "too large")
    decoded = await protocol.decode(body, request.headers, instance)
    if isinstance(decoded, Rejection):
        if decoded.reason is RejectReason.UNAVAILABLE:
            return unavailable
        status, detail = _REJECTIONS[decoded.reason]
        return _answer(status, detail)
    match await ingress.processor.ingest(instance, decoded):
        case IngestOutcome.UNAVAILABLE:
            return unavailable
        case IngestOutcome.TOO_LARGE:
            return _answer(413, "too large")
        case IngestOutcome.PERSISTED | IngestOutcome.DUPLICATE:
            return _answer(200, "accepted")
