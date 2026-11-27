"""Unit tests for choosing a destination's poster by its workplace system.

The core never names a platform: a destination's ``system`` picks the poster, and the
opaque ``slack.passthrough`` reaches only a Slack destination. Stub strategy: posters are
plain sentinels in the mapping the composition root would build.
"""

from typing import cast

import pytest

from capabilities.webhooks.api import EventType
from capabilities.webhooks.domain.kinds import Destination
from capabilities.webhooks.interfaces import ChannelPoster
from capabilities.webhooks.service import poster_for
from contracts.workplace import WorkplaceSystem

pytestmark = pytest.mark.unit

SLACK_POSTER = cast(ChannelPoster, object())
POSTERS = {WorkplaceSystem.SLACK: SLACK_POSTER}
SLACK = Destination(system=WorkplaceSystem.SLACK, tenant="T1", conversation_id="C1")
GOOGLE = Destination(system=WorkplaceSystem.GOOGLE, tenant="C0abc", conversation_id="spaces/x")


@pytest.mark.parametrize("event_type", [EventType.ALERT, EventType.NOTIFICATION, EventType.SLACK_PASSTHROUGH, None])
def test_a_slack_destination_gets_the_slack_poster(event_type: EventType | None) -> None:
    """None is the fallback rendering, which every platform can show."""
    assert poster_for(POSTERS, SLACK, event_type) is SLACK_POSTER


def test_a_system_without_a_poster_gets_none() -> None:
    assert poster_for(POSTERS, GOOGLE, EventType.ALERT) is None


def test_passthrough_never_reaches_another_platform() -> None:
    assert poster_for({**POSTERS, WorkplaceSystem.GOOGLE: SLACK_POSTER}, GOOGLE, EventType.SLACK_PASSTHROUGH) is None
