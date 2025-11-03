"""Idempotency key management for Groups module.

Stage 1: In-memory cache with TTL
Stage 2: DynamoDB persistence (see Stage 2 implementation)
"""

import threading
import time
from typing import Dict, Optional
from core.logging import get_module_logger
from modules.groups import schemas

logger = get_module_logger()

# In-memory cache: {idempotency_key: (response, expiry_timestamp)}
_IDEMPOTENCY_CACHE: Dict[str, tuple] = {}
_CACHE_LOCK = threading.Lock()

# Configuration
_CACHE_TTL_SECONDS = 3600  # 1 hour


def cleanup_expired_entries() -> None:
    """Remove expired cache entries.

    This function is called periodically by jobs/scheduled_tasks.py.
    It performs a single cleanup pass and returns immediately.
    """
    try:
        now = time.time()
        with _CACHE_LOCK:
            expired_keys = [
                key for key, (_, expiry) in _IDEMPOTENCY_CACHE.items()
                if expiry < now
            ]
            for key in expired_keys:
                _IDEMPOTENCY_CACHE.pop(key, None)

            if expired_keys:
                logger.debug(
                    "idempotency_cache_cleanup",
                    expired_count=len(expired_keys),
                    remaining_count=len(_IDEMPOTENCY_CACHE),
                )
    except Exception as e:
        logger.error("idempotency_cleanup_error", error=str(e))


def get_cached_response(idempotency_key: str) -> Optional[schemas.ActionResponse]:
    """Check if response is cached for this idempotency key.

    Args:
        idempotency_key: Unique key for the request

    Returns:
        Cached ActionResponse if found and not expired, None otherwise
    """
    with _CACHE_LOCK:
        cached = _IDEMPOTENCY_CACHE.get(idempotency_key)
        if cached is None:
            return None

        response, expiry = cached

        # Check expiration
        if time.time() > expiry:
            _IDEMPOTENCY_CACHE.pop(idempotency_key, None)
            logger.debug("idempotency_cache_expired", key=idempotency_key)
            return None

        logger.info("idempotency_cache_hit", key=idempotency_key)
        return response


def cache_response(
    idempotency_key: str,
    response: schemas.ActionResponse,
    ttl_seconds: int = _CACHE_TTL_SECONDS,
) -> None:
    """Cache a successful response for the given idempotency key.

    Args:
        idempotency_key: Unique key for the request
        response: ActionResponse to cache
        ttl_seconds: Time-to-live in seconds (default: 3600)
    """
    expiry = time.time() + ttl_seconds

    with _CACHE_LOCK:
        _IDEMPOTENCY_CACHE[idempotency_key] = (response, expiry)
        logger.info(
            "idempotency_cache_stored",
            key=idempotency_key,
            ttl_seconds=ttl_seconds,
            cache_size=len(_IDEMPOTENCY_CACHE),
        )


def clear_cache() -> None:
    """Clear all cached responses (for testing)."""
    with _CACHE_LOCK:
        _IDEMPOTENCY_CACHE.clear()
        logger.debug("idempotency_cache_cleared")


def get_cache_stats() -> dict:
    """Get cache statistics (for monitoring/debugging)."""
    with _CACHE_LOCK:
        now = time.time()
        expired_count = sum(
            1 for _, expiry in _IDEMPOTENCY_CACHE.values() if expiry < now
        )
        return {
            "total_entries": len(_IDEMPOTENCY_CACHE),
            "expired_entries": expired_count,
            "active_entries": len(_IDEMPOTENCY_CACHE) - expired_count,
        }
