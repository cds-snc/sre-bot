"""User identity resolution across platforms.

DEPRECATED: This module is maintained for backward compatibility with legacy feature
modules (incident, roles, aws, opsgenie, trello, atip, etc.). New code should import
from infrastructure.identity instead.

This is a compatibility shim that re-exports the new infrastructure.identity module.

Migration:
    from core.identity import IdentityResolver, UserIdentity  # OLD
    from infrastructure.identity import IdentityResolver, User  # NEW
"""

import warnings

# Re-export everything from new location for backward compatibility
from infrastructure.identity import (
    IdentityResolver,
    IdentitySource,
    User,
    SlackUser,
)

# Deprecation warning on first import
warnings.warn(
    "core.identity is deprecated, use infrastructure.identity instead",
    DeprecationWarning,
    stacklevel=2,
)


# Legacy aliases for compatibility
UserIdentity = User  # Old name for User model

__all__ = [
    "IdentityResolver",
    "IdentitySource",
    "User",
    "UserIdentity",  # Legacy alias
    "SlackUser",
]
