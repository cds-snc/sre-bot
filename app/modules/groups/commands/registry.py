"""Command registry for groups module (DEPRECATED).

This module is deprecated. Commands are now registered using the platform-specific
decorator pattern in modules/groups/platforms/{slack,teams,discord}.py

Migration Status:
- [ ] Slack commands migrated to modules/groups/platforms/slack.py
- [ ] Teams commands migrated to modules/groups/platforms/teams.py
- [ ] Discord commands migrated to modules/groups/platforms/discord.py
- [ ] This file can be deleted after migration is complete

TODO: Delete this file once migration is complete.
"""

# This file is being kept for backward compatibility during migration.
# All imports from infrastructure.commands have been removed.
# Direct references to this registry should be updated to use the new
# platform-specific decorators instead.

registry = None  # Placeholder


# All command definitions below are deprecated and should be migrated to
# the platform-specific decorator pattern in modules/groups/platforms/

# Legacy command definitions have been removed.
# Migrate to: modules/groups/platforms/{slack,teams,discord}.py
