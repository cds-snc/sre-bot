"""Read-only smoke test for the Slack shield.

Exercises `SlackShield.execute()` end-to-end against a sandbox Slack
workspace configured via `SLACK_SMOKE_BOT_TOKEN`. Skips cleanly when
that variable is unset. The test is read-only: no `chat.postMessage`,
no state mutation, no message sending.
"""

from __future__ import annotations

import os
import dotenv

import pytest

from infrastructure.operations.status import OperationStatus
from integrations.slack.settings import SlackSettings
from integrations.slack.shield import SlackShield

dotenv.load_dotenv()  # for local development; CI sets env vars directly
pytestmark = [pytest.mark.smoke]

_SMOKE_TOKEN = os.environ.get("SLACK_SMOKE_BOT_TOKEN")

if _SMOKE_TOKEN is None:
    pytest.skip(
        "SLACK_SMOKE_BOT_TOKEN not set; skipping Slack smoke tests.",
        allow_module_level=True,
    )


@pytest.fixture
def shield() -> SlackShield:
    assert _SMOKE_TOKEN is not None  # narrowed at module load by pytest.skip
    return SlackShield(settings=SlackSettings(SLACK_BOT_TOKEN=_SMOKE_TOKEN))


class TestSlackShieldAgainstSandbox:
    """End-to-end smoke against a sandbox Slack workspace."""

    async def test_auth_test_succeeds(self, shield: SlackShield) -> None:
        result = await shield.execute(shield.web.auth_test())

        assert result.is_success
        assert result.data is not None
        assert result.data.get("ok") is True

    async def test_conversations_list_returns_channels(
        self, shield: SlackShield
    ) -> None:
        result = await shield.execute(
            shield.web.conversations_list(limit=1, types="public_channel")
        )

        assert result.is_success
        assert "channels" in (result.data or {})

    async def test_unknown_channel_classifies_as_not_found(
        self, shield: SlackShield
    ) -> None:
        result = await shield.execute(
            shield.web.conversations_info(channel="C_DOES_NOT_EXIST")
        )

        assert not result.is_success
        assert result.status == OperationStatus.NOT_FOUND

