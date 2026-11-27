"""The webhooks composition root: it builds the platform adapters behind the capability's ports.

Only entrypoints and jobs import this module, so no core module reaches a platform SDK,
even indirectly (decisions/webhooks.md Checks; import-linter contract (p)).
"""

from collections.abc import Mapping
from functools import lru_cache
from types import MappingProxyType

from capabilities.webhooks.adapters.slack import build_slack_poster
from capabilities.webhooks.interfaces import ChannelPoster
from capabilities.webhooks.settings import get_webhooks_settings
from contracts.workplace import WorkplaceSystem


@lru_cache(maxsize=1)
def get_channel_posters() -> Mapping[WorkplaceSystem, ChannelPoster]:
    """One poster per configured platform, keyed by the system a destination names."""
    posters: dict[WorkplaceSystem, ChannelPoster] = {}
    if (slack := build_slack_poster(get_webhooks_settings())) is not None:
        posters[WorkplaceSystem.SLACK] = slack
    return MappingProxyType(posters)
