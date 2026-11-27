"""SNS certificate fetches and subscription confirmations on async httpx.

Both calls go only to an SNS host (checked again here, beside the protocol's check), never
follow a redirect, and carry a per-attempt timeout from the factory (integrations/aws_sns).
Fetched certificates are kept per process, by URL, within a TTL and a size cap: the cache
can vanish at any time (decisions/cloud-portability.md contract 3). A failure is classified,
never retried here.
"""

import time
from collections import OrderedDict
from collections.abc import Callable

import httpx
import structlog

from capabilities.webhooks.domain.sns import is_sns_host_url
from capabilities.webhooks.interfaces import SnsCertificates, SubscriptionConfirmer
from capabilities.webhooks.settings import WebhooksSettings
from contracts.operations import ErrorCode, OperationResult
from integrations.aws_sns import build_sns_http_client, classify_sns_http_error

logger = structlog.get_logger()

# A PEM certificate is a few KiB; anything larger is not a certificate.
MAX_CERTIFICATE_BYTES = 65536


class AwsSnsHttp(SnsCertificates, SubscriptionConfirmer):
    """The SNS port on one httpx client."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        cache_ttl_seconds: int,
        cache_size: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._ttl = cache_ttl_seconds
        self._size = cache_size
        self._clock = clock
        self._cache: OrderedDict[str, tuple[float, bytes]] = OrderedDict()

    async def certificate(self, url: str) -> OperationResult[bytes]:
        """The PEM certificate at ``url``, from the cache while it is fresh."""
        if not is_sns_host_url(url, pem_path=True):
            return OperationResult.permanent_error("not an SNS certificate URL", ErrorCode.INVALID_RESPONSE)
        cached = self._cache.get(url)
        if cached is not None and cached[0] > self._clock():
            self._cache.move_to_end(url)
            return OperationResult.success(data=cached[1])
        try:
            response = await self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            status, code, retry_after = classify_sns_http_error(exc)
            logger.warning("webhook_sns_certificate_fetch_failed", status=status.value, error_code=code)
            return OperationResult.error(
                status=status, message="certificate fetch failed", error_code=code, retry_after=retry_after
            )
        body = response.content
        if len(body) > MAX_CERTIFICATE_BYTES:
            return OperationResult.permanent_error("certificate too large", ErrorCode.INVALID_RESPONSE)
        self._cache[url] = (self._clock() + self._ttl, body)
        self._cache.move_to_end(url)
        while len(self._cache) > self._size:
            self._cache.popitem(last=False)
        return OperationResult.success(data=body)

    async def aclose(self) -> None:
        """Close the client."""
        await self._client.aclose()

    async def confirm(self, subscribe_url: str) -> OperationResult[None]:
        """Visit ``subscribe_url`` once."""
        if not is_sns_host_url(subscribe_url):
            return OperationResult.permanent_error("not an SNS subscribe URL", ErrorCode.INVALID_RESPONSE)
        try:
            response = await self._client.get(subscribe_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            status, code, retry_after = classify_sns_http_error(exc)
            return OperationResult.error(
                status=status, message="subscription confirmation failed", error_code=code, retry_after=retry_after
            )
        return OperationResult.success()


def build_aws_sns_http(settings: WebhooksSettings) -> AwsSnsHttp:
    """The SNS port on a new client; the caller closes it with ``aclose``."""
    client = build_sns_http_client(
        timeout_seconds=settings.sns_fetch_timeout_seconds, connect_retries=settings.sns_connect_retries
    )
    return AwsSnsHttp(
        client, cache_ttl_seconds=settings.sns_certificate_cache_ttl_seconds, cache_size=settings.sns_certificate_cache_size
    )
