"""Feature-local dependency wiring for the rant package.

Resolves the default implementations of the Protocols the handlers depend on,
keeping ``platforms/`` free of adapter (and therefore ``integrations``) lookups.
"""

from functools import lru_cache

from packages.rant.adapters.slack import build_user_identity_lookup
from packages.rant.service import UserIdentityLookup


@lru_cache(maxsize=1)
def get_user_identity_lookup() -> UserIdentityLookup:
    """Return the process-wide Slack-backed ``UserIdentityLookup``."""
    return build_user_identity_lookup()
