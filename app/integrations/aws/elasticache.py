"""AWS ElastiCache Redis/Valkey client for state persistence.

This module provides a Redis CLIENT connection to ElastiCache clusters for
storing and retrieving application state (circuit breaker state, cache, etc.).

IMPORTANT: This is NOT using AWS API (boto3/client_next.py pattern) because:
- We need to CONNECT TO ElastiCache as a Redis database client
- We're storing/retrieving data (key-value operations)
- This is analogous to connecting to a database, not calling AWS APIs

For AWS ElastiCache API operations (describe clusters, manage infrastructure),
see integrations.aws.elasticache_management which uses the client_next.py pattern.

Features:
- Connection pooling with automatic retry
- Standardized error handling via OperationResult
- Type-safe key/value operations
- TTL support for automatic expiration
- JSON serialization helpers

Usage:
    from integrations.aws.elasticache import set_value, get_value

    # Store circuit breaker state
    result = set_value("circuit_breaker:google", {"state": "OPEN"}, ttl_seconds=3600)
    if result.is_success:
        print("State saved")

    # Retrieve circuit breaker state
    result = get_value("circuit_breaker:google")
    if result.is_success and result.data:
        state = result.data
"""

import json
from typing import Any, Optional
from redis import Redis, ConnectionPool, RedisError  # type: ignore
from redis.exceptions import ConnectionError, TimeoutError  # type: ignore

from core.config import settings
from core.logging import get_module_logger
from infrastructure.operations.result import OperationResult

logger = get_module_logger()

# Global connection pool (initialized on first use)
_connection_pool: Optional[ConnectionPool] = None
_redis_client: Optional[Redis] = None


def get_elasticache_client() -> Redis:
    """Get or create ElastiCache (Redis) client with connection pooling.

    Returns:
        Redis: Redis client instance with connection pooling

    Raises:
        ConnectionError: If unable to connect to ElastiCache
    """
    global _connection_pool, _redis_client

    if _redis_client is not None:
        return _redis_client

    try:
        # Create connection pool on first access
        if _connection_pool is None:
            _connection_pool = ConnectionPool(
                host=settings.elasticache.ELASTICACHE_ENDPOINT,
                port=settings.elasticache.ELASTICACHE_PORT,
                db=0,
                decode_responses=True,  # Auto-decode bytes to strings
                max_connections=10,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            logger.info(
                "elasticache_connection_pool_created",
                host=settings.elasticache.ELASTICACHE_ENDPOINT,
                port=settings.elasticache.ELASTICACHE_PORT,
            )

        _redis_client = Redis(connection_pool=_connection_pool)

        # Test connection
        _redis_client.ping()
        logger.info("elasticache_client_connected")

        return _redis_client

    except (ConnectionError, TimeoutError, RedisError) as e:
        logger.error(
            "elasticache_connection_failed",
            error=str(e),
            host=settings.elasticache.ELASTICACHE_ENDPOINT,
        )
        raise


def set_value(
    key: str,
    value: Any,
    ttl_seconds: Optional[int] = None,
) -> OperationResult:
    """Set a key-value pair in ElastiCache with optional TTL.

    Args:
        key: The key to set
        value: The value (will be JSON-serialized if dict/list)
        ttl_seconds: Optional expiration time in seconds

    Returns:
        OperationResult: Success/failure result
    """
    try:
        client = get_elasticache_client()

        # Serialize complex types to JSON
        if isinstance(value, (dict, list)):
            serialized_value = json.dumps(value)
        else:
            serialized_value = str(value)

        # Set with TTL if provided
        if ttl_seconds:
            client.setex(key, ttl_seconds, serialized_value)
            logger.debug(
                "elasticache_set_with_ttl",
                key=key,
                ttl_seconds=ttl_seconds,
            )
        else:
            client.set(key, serialized_value)
            logger.debug("elasticache_set", key=key)

        return OperationResult.success(
            message=f"Value set for key: {key}",
        )

    except (ConnectionError, TimeoutError) as e:
        logger.error(
            "elasticache_set_connection_error",
            key=key,
            error=str(e),
        )
        return OperationResult.transient_error(
            message=f"Connection error setting key {key}: {str(e)}",
            error_code="CONNECTION_ERROR",
        )

    except RedisError as e:
        logger.error(
            "elasticache_set_error",
            key=key,
            error=str(e),
        )
        return OperationResult.permanent_error(
            message=f"Error setting key {key}: {str(e)}",
            error_code="REDIS_ERROR",
        )


def get_value(key: str, deserialize_json: bool = True) -> OperationResult:
    """Get a value from ElastiCache by key.

    Args:
        key: The key to retrieve
        deserialize_json: Attempt to deserialize as JSON (default: True)

    Returns:
        OperationResult: Result with data=value or data=None if not found
    """
    try:
        client = get_elasticache_client()
        value = client.get(key)

        if value is None:
            logger.debug("elasticache_key_not_found", key=key)
            return OperationResult.success(
                message=f"Key not found: {key}",
                data=None,
            )

        # Try to deserialize JSON
        if deserialize_json:
            try:
                deserialized = json.loads(value)
                logger.debug("elasticache_get_success", key=key)
                return OperationResult.success(
                    message=f"Value retrieved for key: {key}",
                    data=deserialized,
                )
            except json.JSONDecodeError:
                # Not JSON, return as string
                pass

        logger.debug("elasticache_get_success", key=key)
        return OperationResult.success(
            message=f"Value retrieved for key: {key}",
            data=value,
        )

    except (ConnectionError, TimeoutError) as e:
        logger.error(
            "elasticache_get_connection_error",
            key=key,
            error=str(e),
        )
        return OperationResult.transient_error(
            message=f"Connection error getting key {key}: {str(e)}",
            error_code="CONNECTION_ERROR",
        )

    except RedisError as e:
        logger.error(
            "elasticache_get_error",
            key=key,
            error=str(e),
        )
        return OperationResult.permanent_error(
            message=f"Error getting key {key}: {str(e)}",
            error_code="REDIS_ERROR",
        )


def delete_value(key: str) -> OperationResult:
    """Delete a key from ElastiCache.

    Args:
        key: The key to delete

    Returns:
        OperationResult: Success/failure result
    """
    try:
        client = get_elasticache_client()
        deleted_count = client.delete(key)

        logger.debug(
            "elasticache_delete",
            key=key,
            deleted=deleted_count > 0,
        )

        return OperationResult.success(
            message=(
                f"Key deleted: {key}" if deleted_count > 0 else f"Key not found: {key}"
            ),
            data={"deleted": deleted_count > 0},
        )

    except (ConnectionError, TimeoutError) as e:
        logger.error(
            "elasticache_delete_connection_error",
            key=key,
            error=str(e),
        )
        return OperationResult.transient_error(
            message=f"Connection error deleting key {key}: {str(e)}",
            error_code="CONNECTION_ERROR",
        )

    except RedisError as e:
        logger.error(
            "elasticache_delete_error",
            key=key,
            error=str(e),
        )
        return OperationResult.permanent_error(
            message=f"Error deleting key {key}: {str(e)}",
            error_code="REDIS_ERROR",
        )


def exists(key: str) -> OperationResult:
    """Check if a key exists in ElastiCache.

    Args:
        key: The key to check

    Returns:
        OperationResult: Result with data=True/False
    """
    try:
        client = get_elasticache_client()
        exists_count = client.exists(key)

        logger.debug(
            "elasticache_exists",
            key=key,
            exists=exists_count > 0,
        )

        return OperationResult.success(
            message=f"Key existence checked: {key}",
            data=exists_count > 0,
        )

    except (ConnectionError, TimeoutError) as e:
        logger.error(
            "elasticache_exists_connection_error",
            key=key,
            error=str(e),
        )
        return OperationResult.transient_error(
            message=f"Connection error checking key {key}: {str(e)}",
            error_code="CONNECTION_ERROR",
        )

    except RedisError as e:
        logger.error(
            "elasticache_exists_error",
            key=key,
            error=str(e),
        )
        return OperationResult.permanent_error(
            message=f"Error checking key {key}: {str(e)}",
            error_code="REDIS_ERROR",
        )


def get_ttl(key: str) -> OperationResult:
    """Get remaining TTL for a key in seconds.

    Args:
        key: The key to check

    Returns:
        OperationResult: Result with data=seconds (-1 if no TTL, -2 if key doesn't exist)
    """
    try:
        client = get_elasticache_client()
        ttl = client.ttl(key)

        logger.debug(
            "elasticache_ttl",
            key=key,
            ttl_seconds=ttl,
        )

        return OperationResult.success(
            message=f"TTL retrieved for key: {key}",
            data=ttl,
        )

    except (ConnectionError, TimeoutError) as e:
        logger.error(
            "elasticache_ttl_connection_error",
            key=key,
            error=str(e),
        )
        return OperationResult.transient_error(
            message=f"Connection error getting TTL for key {key}: {str(e)}",
            error_code="CONNECTION_ERROR",
        )

    except RedisError as e:
        logger.error(
            "elasticache_ttl_error",
            key=key,
            error=str(e),
        )
        return OperationResult.permanent_error(
            message=f"Error getting TTL for key {key}: {str(e)}",
            error_code="REDIS_ERROR",
        )


def health_check() -> OperationResult:
    """Check ElastiCache connection health.

    Returns:
        OperationResult: Success if healthy, error otherwise
    """
    try:
        client = get_elasticache_client()
        client.ping()

        logger.debug("elasticache_health_check_success")

        return OperationResult.success(
            message="ElastiCache connection healthy",
        )

    except (ConnectionError, TimeoutError) as e:
        logger.error(
            "elasticache_health_check_connection_error",
            error=str(e),
        )
        return OperationResult.transient_error(
            message=f"ElastiCache connection error: {str(e)}",
            error_code="CONNECTION_ERROR",
        )

    except RedisError as e:
        logger.error(
            "elasticache_health_check_error",
            error=str(e),
        )
        return OperationResult.permanent_error(
            message=f"ElastiCache health check failed: {str(e)}",
            error_code="REDIS_ERROR",
        )
