"""JWT token validation and JWKS management for API authentication.

This module provides JWKS client management and JWT token validation
with support for multiple issuers.
"""

from functools import lru_cache
from typing import Any, Dict, Optional

import structlog
from jwt import PyJWKClient, PyJWKClientError

from infrastructure.configuration.infrastructure.server import (
    get_server_settings,
)

logger = structlog.get_logger()


def get_issuer_config() -> Dict[str, Dict[str, Any]] | None:
    """Return the JWKS settings slice from the unified security settings."""
    settings = get_server_settings()
    if settings.ISSUER_CONFIG is not None:
        return settings.ISSUER_CONFIG

    log = logger.bind()
    log.warning(
        "issuer_config_not_set",
        detail="ISSUER_CONFIG is not set in server settings",
    )
    return {}


class JWKSManager:
    """Manage JWKS clients for different issuers.

    Initializes a JWKS client for each issuer in the provided configuration.

    Attributes:
        issuer_config: Dictionary containing issuer configurations with jwks_uri
        jwks_clients: Cache of JWKS clients for each issuer
    """

    def __init__(
        self, issuer_config: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> None:
        """Initialize JWKS manager.

        Args:
            issuer_config: Optional issuer configuration dictionary.
                          If None, uses settings.server.ISSUER_CONFIG.
        """
        if issuer_config is None:
            raise ValueError(
                "issuer_config must be provided explicitly. "
                "Use get_jwks_manager() provider for DI."
            )
        self.issuer_config = issuer_config
        self.jwks_clients: Dict[str, PyJWKClient] = {}

    def get_jwks_client(self, issuer: str) -> Optional[PyJWKClient]:
        """Get or create JWKS client for the specified issuer.

        Args:
            issuer: The issuer for which to get the JWKS client

        Returns:
            The JWKS client for the specified issuer, or None if not found

        Raises:
            No exceptions raised; errors are logged and None returned
        """
        if not self.issuer_config or issuer not in self.issuer_config:
            log = logger.bind(issuer=issuer)
            log.warning("issuer_not_configured")
            return None

        if issuer not in self.jwks_clients:
            try:
                cfg = self.issuer_config[issuer]
                jwks_uri = cfg.get("jwks_uri")
                if not jwks_uri:
                    log = logger.bind(issuer=issuer)
                    log.warning("issuer_missing_jwks_uri")
                    return None

                self.jwks_clients[issuer] = PyJWKClient(
                    jwks_uri, cache_jwk_set=True, lifespan=3600, timeout=10
                )
                log = logger.bind(issuer=issuer)
                log.info("jwks_client_initialized")
            except PyJWKClientError as e:
                log = logger.bind(issuer=issuer, error=str(e))
                log.warning("jwks_client_initialization_failed")
                return None

        return self.jwks_clients[issuer]

    def clear_cache(self, issuer: Optional[str] = None) -> None:
        """Clear JWKS client cache.

        Args:
            issuer: Optional issuer to clear. If None, clears all.
        """
        if issuer:
            self.jwks_clients.pop(issuer, None)
        else:
            self.jwks_clients.clear()

    def warmup(self) -> None:
        """Pre-initialize JWKS clients for all configured issuers.

        Called during application startup to eagerly construct a PyJWKClient
        for every issuer in the configuration.  Keys are not fetched from the
        JWKS URI here; that happens on the first token validation.  Warmup only
        ensures the client objects are created and cached so there is no
        object-construction overhead on the first authenticated request.
        """
        if self.issuer_config is None:
            log = logger.bind()
            log.warning("jwks_warmup_skipped_no_issuer_config")
            return
        for issuer in list(self.issuer_config.keys()):
            self.get_jwks_client(issuer)
        log = logger.bind(issuer_count=len(self.issuer_config))
        log.info("jwks_clients_warmed_up")


@lru_cache(maxsize=1)
def get_jwks_manager() -> JWKSManager:
    """Singleton accessor for JWKSManager.

    Args:
        issuer_config: Optional issuer configuration dictionary.
    Returns:
        The singleton JWKSManager instance.
    """
    log = logger.bind()
    log.info("initializing_jwks_manager")
    issuer_config = get_issuer_config()
    if not issuer_config:
        log.warning("jwks_manager_initialized_with_empty_issuer_config")
    return JWKSManager(issuer_config=issuer_config)
