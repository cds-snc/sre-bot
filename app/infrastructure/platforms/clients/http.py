"""Internal HTTP client for platform-to-endpoint communication.

This client handles HTTP calls from platform providers to internal FastAPI endpoints.
All platform interactions (Slack commands, Teams messages, Discord slashes) ultimately
translate to HTTP requests to the FastAPI application running on localhost.

Architecture:
    Platform Event (Slack /command)
        ↓
    Platform Provider (parse + acknowledge)
        ↓
    InternalHttpClient.post("/api/v1/groups/add", {...})
        ↓
    FastAPI Route Handler (business logic)
        ↓
    JSON Response
        ↓
    Platform Provider (format for platform)
        ↓
    Platform Response (Block Kit, Adaptive Cards, etc.)

Benefits:
    - Testable: Test HTTP endpoints directly without mocking platforms
    - Consistent: Same code path for API and platform requests
    - Documented: OpenAPI docs describe all operations
    - Idempotent: Same idempotency mechanism for all interfaces
    - Auditable: Same audit log for all request sources

Usage:
    from infrastructure.platforms.clients.http import InternalHttpClient

    client = InternalHttpClient(base_url="http://localhost:8000")

    # Call internal endpoint
    response = client.post(
        "/api/v1/groups/add",
        json={
            "group_id": "eng-team",
            "member_email": "user@example.com",
            "requestor_email": "admin@example.com",
        }
    )

    if response.is_success:
        data = response.data
        # Format for platform...
"""

import json
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests
import structlog

from infrastructure.operations import OperationResult, OperationStatus

logger = structlog.get_logger(__name__)


class InternalHttpClient:
    """HTTP client for internal endpoint calls from platform providers.

    This client is optimized for localhost connections with:
    - Connection pooling (reuse connections)
    - Reasonable timeouts (fast local calls)
    - Automatic error categorization
    - Structured logging

    Attributes:
        base_url: Base URL for all requests (default: http://localhost:8000)
        timeout: Default timeout in seconds
        session: Requests session with connection pooling
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: int = 30,
    ) -> None:
        """Initialize internal HTTP client.

        Args:
            base_url: Base URL for all requests
            timeout: Default timeout for requests in seconds
        """
        self.base_url = base_url
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "SRE-Bot-Platform-Provider/1.0",
                "Accept": "application/json",
            }
        )
        self._logger = logger.bind(component="internal_http_client")

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> OperationResult:
        """Send GET request to internal endpoint.

        Args:
            path: Endpoint path (e.g., "/api/v1/groups/list")
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout (overrides default)

        Returns:
            OperationResult with response data or error
        """
        return self._request(
            "GET", path, params=params, headers=headers, timeout=timeout
        )

    def post(
        self,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> OperationResult:
        """Send POST request to internal endpoint.

        Args:
            path: Endpoint path (e.g., "/api/v1/groups/add")
            json_data: JSON request body
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout (overrides default)

        Returns:
            OperationResult with response data or error
        """
        return self._request(
            "POST",
            path,
            json_data=json_data,
            params=params,
            headers=headers,
            timeout=timeout,
        )

    def put(
        self,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> OperationResult:
        """Send PUT request to internal endpoint.

        Args:
            path: Endpoint path
            json_data: JSON request body
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout (overrides default)

        Returns:
            OperationResult with response data or error
        """
        return self._request(
            "PUT",
            path,
            json_data=json_data,
            params=params,
            headers=headers,
            timeout=timeout,
        )

    def delete(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> OperationResult:
        """Send DELETE request to internal endpoint.

        Args:
            path: Endpoint path
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout (overrides default)

        Returns:
            OperationResult with response data or error
        """
        return self._request(
            "DELETE", path, params=params, headers=headers, timeout=timeout
        )

    def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> OperationResult:
        """Send HTTP request to internal endpoint.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: Endpoint path
            json_data: JSON request body
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout

        Returns:
            OperationResult with response data or error
        """
        url = urljoin(self.base_url, path)
        timeout = timeout or self.timeout

        log = self._logger.bind(method=method, path=path, url=url)
        log.debug("internal_http_request")

        try:
            # Merge headers
            request_headers = self._session.headers.copy()
            if headers:
                request_headers.update(headers)

            # Send request
            response = self._session.request(
                method=method,
                url=url,
                json=json_data,
                params=params,
                headers=request_headers,
                timeout=timeout,
            )

            # Log response
            log = log.bind(status_code=response.status_code)

            # Parse response body
            response_data: Optional[Dict[str, Any]] = None
            if response.content:
                try:
                    response_data = response.json()
                except json.JSONDecodeError:
                    log.warning("non_json_response", content=response.text[:200])

            # Success (2xx)
            if 200 <= response.status_code < 300:
                log.debug("internal_http_success")
                return OperationResult.success(
                    data=response_data,
                    message=f"{method} {path} succeeded",
                )

            # Client error (4xx) - Permanent error
            if 400 <= response.status_code < 500:
                error_message = self._extract_error_message(
                    response_data, response.text
                )
                log.warning("internal_http_client_error", error=error_message)

                # Map specific statuses
                if response.status_code == 401 or response.status_code == 403:
                    return OperationResult.error(
                        status=OperationStatus.UNAUTHORIZED,
                        message=error_message,
                        error_code=f"HTTP_{response.status_code}",
                    )
                elif response.status_code == 404:
                    return OperationResult.error(
                        status=OperationStatus.NOT_FOUND,
                        message=error_message,
                        error_code="HTTP_404",
                    )
                else:
                    return OperationResult.permanent_error(
                        message=error_message,
                        error_code=f"HTTP_{response.status_code}",
                    )

            # Server error (5xx) - Transient error
            if 500 <= response.status_code < 600:
                error_message = self._extract_error_message(
                    response_data, response.text
                )
                log.error("internal_http_server_error", error=error_message)

                # Check for rate limiting (429 or 503 with Retry-After)
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        retry_after_seconds = int(retry_after)
                    except ValueError:
                        retry_after_seconds = 60

                    return OperationResult.transient_error(
                        message=error_message,
                        error_code=f"HTTP_{response.status_code}",
                        retry_after=retry_after_seconds,
                    )

                return OperationResult.transient_error(
                    message=error_message,
                    error_code=f"HTTP_{response.status_code}",
                )

            # Unexpected status code
            log.error("internal_http_unexpected_status", status=response.status_code)
            return OperationResult.transient_error(
                message=f"Unexpected status code: {response.status_code}",
                error_code=f"HTTP_{response.status_code}",
            )

        except requests.Timeout:
            log.error("internal_http_timeout", timeout=timeout)
            return OperationResult.transient_error(
                message=f"Request timeout after {timeout}s",
                error_code="TIMEOUT",
            )

        except requests.ConnectionError as e:
            log.error("internal_http_connection_error", error=str(e))
            return OperationResult.transient_error(
                message=f"Connection error: {str(e)}",
                error_code="CONNECTION_ERROR",
            )

        except Exception as e:
            log.error("internal_http_unexpected_error", error=str(e), exc_info=True)
            return OperationResult.transient_error(
                message=f"Unexpected error: {str(e)}",
                error_code="UNEXPECTED_ERROR",
            )

    def _extract_error_message(
        self,
        response_data: Optional[Dict[str, Any]],
        response_text: str,
    ) -> str:
        """Extract error message from response.

        Args:
            response_data: Parsed JSON response
            response_text: Raw response text

        Returns:
            Human-readable error message
        """
        if response_data:
            # Try common error fields
            for key in ["detail", "error", "message"]:
                if key in response_data:
                    return str(response_data[key])

        # Fallback to raw text (truncated)
        return response_text[:200] if response_text else "Unknown error"

    def close(self) -> None:
        """Close HTTP session and release connections."""
        self._session.close()
        self._logger.debug("internal_http_client_closed")


__all__ = ["InternalHttpClient"]
