"""Google Workspace session provider for authentication and service creation."""

import json
from typing import List, Optional

import structlog
from google.oauth2 import service_account
from googleapiclient.discovery import Resource, build

logger = structlog.get_logger()


class SessionProvider:
    """Manages Google Workspace API authentication and service creation.

    Centralizes credential management, service account delegation, and API discovery
    for all Google Workspace services.

    Args:
        credentials_json: Service account JSON key file content
        default_delegated_email: Default email for domain-wide delegation
        default_scopes: Default OAuth scopes for services

    Thread Safety:
        This class is thread-safe. However, Resource objects returned by
        get_service() are NOT thread-safe per Google API client library
        documentation. Each thread must call get_service() to create its
        own service instance.

    References:
        https://googleapis.github.io/google-api-python-client/docs/thread_safety.html
    """

    def __init__(
        self,
        credentials_json: str,
        default_delegated_email: Optional[str] = None,
        default_scopes: Optional[List[str]] = None,
    ) -> None:
        self._credentials_json: str = credentials_json
        self._default_delegated_email: Optional[str] = default_delegated_email
        self._default_scopes: List[str] = default_scopes or []
        self._logger = logger.bind(component="google_session_provider")

    def get_service(
        self,
        service_name: str,
        version: str,
        scopes: Optional[List[str]] = None,
        delegated_user_email: Optional[str] = None,
    ) -> Resource:
        """Create an authenticated Google API service resource.

        Args:
            service_name: Google service name (e.g., "admin", "drive", "docs")
            version: API version (e.g., "directory_v1", "v3")
            scopes: OAuth scopes (uses default if None)
            delegated_user_email: Email for delegation (uses default if None)

        Returns:
            Authenticated Google API service resource

        Raises:
            ValueError: If credentials are invalid

        Thread Safety:
            This method is thread-safe, but the returned Resource is NOT.
            Each thread must call this method to get its own service instance.
        """
        try:
            creds_info = json.loads(self._credentials_json)
            creds = service_account.Credentials.from_service_account_info(creds_info)

            # Apply delegation
            delegation_email = delegated_user_email or self._default_delegated_email
            if delegation_email:
                creds = creds.with_subject(delegation_email)

            # Apply scopes
            service_scopes = scopes or self._default_scopes
            if service_scopes:
                creds = creds.with_scopes(service_scopes)

            # Build service with static discovery (cached, no network calls)
            return build(
                service_name,
                version,
                credentials=creds,
                cache_discovery=False,
                static_discovery=False,
            )

        except json.JSONDecodeError as e:
            self._logger.error("invalid_credentials_json", error=str(e))
            raise ValueError("Invalid credentials JSON") from e
        except Exception as e:
            self._logger.error("service_creation_failed", error=str(e))
            raise
