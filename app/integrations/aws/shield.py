"""AWS shield: resilience boundary around the boto3 SDK.

Exposes `AWSShield`, a service that constructs boto3 clients with native
retry wired in (`Config(retries={...})`) and provides `execute(thunk)`,
the synchronous resilience boundary that classifies `ClientError` and
`BotoCoreError` into the closed `OperationStatus` set.

Adapter call shape:

    result = shield.execute(
        lambda: shield.client("dynamodb").get_item(TableName=..., Key=...)
    )

Per-service boto3 clients are constructed lazily on first request and
cached for the lifetime of the shield instance.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

import boto3
from boto3.session import Session
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus
from integrations.aws.settings import AWSSettings

if TYPE_CHECKING:
    from botocore.config import _RetryDict


R = TypeVar("R")

_PROVIDER = "aws"


class AWSShield:
    """Resilience boundary around boto3.

    Owns SDK construction with native retry configured per
    `docs/adr/outbound-retry-policy.md`, caches one client per service
    name, and converts SDK exceptions raised by callables passed to
    `execute()` into `OperationResult` envelopes using the error-code
    catalogues carried on `AWSSettings`.
    """

    def __init__(self, settings: AWSSettings) -> None:
        self._settings = settings
        retries: _RetryDict = {
            "max_attempts": settings.RETRY_MAX_ATTEMPTS,
            "mode": settings.RETRY_MODE,
        }
        self._config = Config(
            retries=retries,
            connect_timeout=settings.CONNECT_TIMEOUT_SECONDS,
            read_timeout=settings.READ_TIMEOUT_SECONDS,
        )
        self._session: Session = boto3.session.Session()
        self._clients: dict[str, BaseClient] = {}

        self._not_found_codes: frozenset[str] = frozenset(settings.NOT_FOUND_CODES)
        self._unauthorized_codes: frozenset[str] = frozenset(settings.UNAUTHORIZED_CODES)
        self._transient_codes: frozenset[str] = frozenset(settings.TRANSIENT_CODES)

    def client(self, service_name: str) -> BaseClient:
        """Return a cached boto3 client for `service_name`, building it on first use."""
        cached = self._clients.get(service_name)
        if cached is not None:
            return cached

        # boto3-stubs models Session.client() with one Literal[...] overload per
        # AWS service so call sites get a service-specific typed client. A
        # shield that accepts a runtime str cannot be expressed in those
        # overloads, so the dispatch is intentionally typed against the
        # underlying botocore return type (BaseClient).
        built: BaseClient = self._session.client(  # type: ignore[call-overload]
            service_name,
            region_name=self._settings.AWS_REGION,
            config=self._config,
            endpoint_url=self._settings.AWS_ENDPOINT_URL,
        )
        self._clients[service_name] = built
        return built

    def execute(self, func: Callable[[], R]) -> OperationResult[R]:
        """Invoke `func()` and classify any boto3 exception into `OperationResult`."""
        try:
            return OperationResult.success(data=func(), provider=_PROVIDER)
        except ClientError as exc:
            return self._classify_client_error(exc)
        except BotoCoreError as exc:
            return OperationResult.transient_error(
                message=str(exc) or "botocore transport error",
                error_code=type(exc).__name__,
            )

    def _classify_client_error(self, exc: ClientError) -> OperationResult[Any]:
        """Map a `ClientError` to an `OperationResult` using its AWS error code."""
        response = getattr(exc, "response", None) or {}
        error: dict[str, Any] = response.get("Error", {}) if isinstance(response, dict) else {}
        code: str = error.get("Code") or ""
        message: str = error.get("Message") or str(exc)

        if code in self._not_found_codes:
            status = OperationStatus.NOT_FOUND
        elif code in self._unauthorized_codes:
            status = OperationStatus.UNAUTHORIZED
        elif code in self._transient_codes:
            status = OperationStatus.TRANSIENT_ERROR
        else:
            status = OperationStatus.PERMANENT_ERROR

        return OperationResult.error(
            status=status,
            message=message,
            error_code=code or None,
            provider=_PROVIDER,
        )
