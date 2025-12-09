"""Idempotency key builder for consistent key generation."""

import hashlib
from typing import Any


class IdempotencyKeyBuilder:
    """Build deterministic idempotency keys.

    Provides consistent key format across all features with namespace
    isolation and collision prevention.

    Example:
        >>> builder = IdempotencyKeyBuilder(namespace="groups_notifications")
        >>> key = builder.build(
        ...     operation="send_notification",
        ...     entity_id="eng-team",
        ...     user_id="user@example.com",
        ...     action="add_member",
        ... )
        >>> key
        'groups_notifications:send_notification:a1b2c3d4e5f6g7h8'
    """

    def __init__(self, namespace: str):
        """Initialize key builder.

        Args:
            namespace: Namespace for key isolation (e.g., "groups_notifications")
        """
        self.namespace = namespace

    def build(self, operation: str, **components: Any) -> str:
        """Build idempotency key from components.

        Args:
            operation: Operation type (e.g., "send_notification", "add_member")
            **components: Key components (entity_id, user_id, action, etc.)

        Returns:
            Idempotency key string
        """
        sorted_components = sorted(components.items())

        key_parts = [self.namespace, operation]
        key_parts.extend(f"{k}={v}" for k, v in sorted_components)
        key_string = "|".join(str(part) for part in key_parts)

        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]

        return f"{self.namespace}:{operation}:{key_hash}"
