"""JWT token validation and JWKS management for API authentication.

This module provides JWKS client management and JWT token validation
with support for multiple issuers.
"""

from typing import Any, Dict, Optional

import structlog
from jwt import PyJWKClient, PyJWKClientError

from infrastructure.configuration import settings

logger = structlog.get_logger()


class JWKSManager:
    """Manage JWKS clients for different issuers.

    Initializes a JWKS client for each issuer in the provided configuration.

    Attributes:
        issuer_config: Dictionary containing issuer configurations with jwks_uri
        jwks_clients: Cache of JWKS clients for each issuer
    """

    def __init__(self, issuer_config: Optional[Dict[str, Dict[str, Any]]] = None):
        """Initialize JWKS manager.

        Args:
            issuer_config: Optional issuer configuration dictionary.
                          If None, uses settings.server.ISSUER_CONFIG.
        """
        self.issuer_config = issuer_config or getattr(
            settings.server, "ISSUER_CONFIG", None
        )
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
            except Exception as e:
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
