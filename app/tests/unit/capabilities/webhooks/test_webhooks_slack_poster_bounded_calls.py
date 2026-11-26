"""Unit tests for how the Slack poster bounds its calls to one delivery's deadline.

The inbox is the one retry point (decisions/outbound-clients.md, reliability.md), so a post
is never retried or waited on in process: a rate limit comes back with its ``retry_after``.
Stub strategy: a recording stand-in client raises configured Slack errors; the composition
test builds the real clients from environment settings and reads their configuration.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from capabilities.webhooks.adapters.slack import build_slack_poster
from capabilities.webhooks.domain.kinds import Destination
from capabilities.webhooks.domain.messages import ChannelMessage
from capabilities.webhooks.providers import get_channel_posters
from capabilities.webhooks.settings import get_webhooks_settings
from contracts.languages import MultilingualText
from contracts.operations import OperationStatus
from contracts.workplace import WorkplaceSystem
from integrations.slack.settings import get_slack_settings
from tests.unit.capabilities.webhooks.conftest import install_webhooks_files
from tests.unit.capabilities.webhooks.slack_client_fake import TENANT, FakeSlackClient, delivery_poster, slack_error

pytestmark = pytest.mark.unit

DESTINATION = Destination(system=WorkplaceSystem.SLACK, tenant=TENANT, conversation_id="C123")
TEXT = MultilingualText((("en-US", "t"),))
MESSAGE = ChannelMessage(title=TEXT, summary=TEXT)


@pytest.fixture(autouse=True)
def _slack_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    install_webhooks_files(tmp_path, base="[webhooks]\n\n[slack]\n")
    for key in tuple(os.environ):
        if key.startswith("SLACK_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SLACK__TENANT__TEAM_ID", TENANT)
    monkeypatch.setenv("SLACK__BOT_TOKEN", "xoxb-bot-token")
    get_slack_settings.cache_clear()
    get_channel_posters.cache_clear()
    yield
    get_slack_settings.cache_clear()
    get_channel_posters.cache_clear()


async def test_a_rate_limit_returns_its_retry_after_to_the_inbox() -> None:
    client = FakeSlackClient(post_error=slack_error("ratelimited", status=429, headers={"Retry-After": "30"}))

    result = await delivery_poster(client).post(DESTINATION, MESSAGE)

    assert (result.status, result.error_code, result.retry_after) == (OperationStatus.TRANSIENT_ERROR, "ratelimited", 30)
    assert len(client.posts) == 1


async def test_an_unreachable_slack_is_a_transient_failure_posted_once() -> None:
    client = FakeSlackClient(post_error=TimeoutError())

    result = await delivery_poster(client).post(DESTINATION, MESSAGE)

    assert (result.status, result.error_code) == (OperationStatus.TRANSIENT_ERROR, "TIMEOUT")
    assert len(client.posts) == 1


async def test_a_destination_outside_the_configured_tenant_is_not_posted() -> None:
    client = FakeSlackClient()
    elsewhere = Destination(system=WorkplaceSystem.SLACK, tenant="T0OTHER", conversation_id="C123")

    result = await delivery_poster(client).post(elsewhere, MESSAGE)

    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, "TENANT_MISMATCH")
    assert client.posts == []


async def test_a_success_carries_the_message_timestamp() -> None:
    result = await delivery_poster(FakeSlackClient()).post(DESTINATION, MESSAGE)

    assert (result.is_success, result.data) == (True, "1700000000.000100")


def test_the_real_clients_carry_the_attempt_timeout_and_no_in_process_retry() -> None:
    """Built by the composition root from [webhooks] and [slack]."""
    poster = build_slack_poster(get_webhooks_settings())

    assert poster is not None
    writes, reads = poster._writes, poster._reads  # noqa: SLF001 - the composition is what is under test
    assert (writes.timeout, reads.timeout) == (2, 2)
    assert (writes.retry_handlers, reads.retry_handlers) == ([], [])


def test_the_composition_root_keys_posters_by_system() -> None:
    assert set(get_channel_posters()) == {WorkplaceSystem.SLACK}


def test_no_slack_tenant_means_no_slack_poster(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SLACK__TENANT__TEAM_ID")
    monkeypatch.delenv("SLACK__BOT_TOKEN")
    get_slack_settings.cache_clear()

    assert build_slack_poster(get_webhooks_settings()) is None
