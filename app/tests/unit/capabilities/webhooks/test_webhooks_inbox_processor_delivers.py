"""Unit tests for the webhook processor: ingest, inline processing, retries and the sweep.

Stub strategy: ``processor_fakes`` builds the processor on the real inbox store over the
in-memory records fake, with recording posters, consumer and confirmer. Assertions read what
was posted, consumed and persisted.
"""

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from structlog.testing import capture_logs

from capabilities.webhooks.domain.inbox import ItemKind, ItemState, item_key
from capabilities.webhooks.domain.kinds import Destination, InstanceState
from capabilities.webhooks.domain.messages import ChannelMessage, FallbackMessage, PassthroughMessage
from capabilities.webhooks.service import IngestOutcome
from contracts.operations import OperationResult, OperationStatus
from contracts.workplace import WorkplaceSystem
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.unit.capabilities.webhooks.conftest import install_webhooks_files
from tests.unit.capabilities.webhooks.processor_fakes import C2, START, delivery, instance, world

pytestmark = pytest.mark.unit


async def test_a_new_delivery_posts_once_per_destination_and_reaches_its_consumer_once() -> None:
    w = world()

    outcome = await w.processor.ingest(instance(), delivery())

    assert outcome is IngestOutcome.PERSISTED
    assert [conversation for conversation, _ in w.poster.posts] == ["C1", "C2"]
    assert w.poster.sessions == 1
    ((event, context),) = w.consumer.consumed
    assert (event.id, event.source, context.item_id) == ("m-1", "ref-1", item_key("ref-1", "m-1"))
    item = await w.item()
    assert item.state is ItemState.DONE and item.owner is None and item.due_at is None


async def test_a_redelivery_with_the_same_delivery_id_is_persisted_and_processed_once() -> None:
    w = world()

    first = await w.processor.ingest(instance(), delivery())
    second = await w.processor.ingest(instance(), delivery())

    assert (first, second) == (IngestOutcome.PERSISTED, IngestOutcome.DUPLICATE)
    assert len(w.poster.posts) == 2 and len(w.consumer.consumed) == 1


class _Down(InMemoryRecordStore):
    def put_if_not_exists(self, table: Any, item: dict[str, Any]) -> OperationResult:
        return OperationResult.transient_error("throttled")


async def test_an_insert_the_store_cannot_confirm_processes_nothing() -> None:
    w = world(records=_Down())

    assert await w.processor.ingest(instance(), delivery()) is IngestOutcome.UNAVAILABLE
    assert w.poster.posts == [] and w.consumer.consumed == []


async def test_an_envelope_past_the_item_limit_is_too_large_and_never_stored(tmp_path: Path) -> None:
    install_webhooks_files(tmp_path, base="[webhooks]\nmax_envelope_bytes = 64\n")
    w = world()

    assert await w.processor.ingest(instance(), delivery(document={"x": "y" * 100})) is IngestOutcome.TOO_LARGE
    assert (await w.inbox.get(item_key("ref-1", "m-1"))).status is OperationStatus.NOT_FOUND


async def test_only_the_triage_destination_offers_the_consumers_actions() -> None:
    w = world()

    await w.processor.ingest(instance(), delivery())

    by_conversation = {conversation: message for conversation, message in w.poster.posts}
    assert isinstance(by_conversation["C1"], ChannelMessage) and isinstance(by_conversation["C2"], ChannelMessage)
    assert [action.action_id for action in by_conversation["C1"].actions] == ["incident.call"]
    assert by_conversation["C2"].actions == ()


async def test_a_retry_after_sets_the_next_attempt_and_the_retry_repeats_no_finished_target() -> None:
    w = world(jitter=lambda: 0.0)
    w.poster.script["C2"] = [OperationResult.transient_error("rate limited", retry_after=120)]

    await w.processor.ingest(instance(), delivery())
    waiting = await w.item()

    assert waiting.state is ItemState.RETRY
    assert waiting.due_at == int(START.timestamp()) + 120
    assert waiting.done_targets == {"post:slack:T1:C1", "consume:incident"}
    assert len(w.consumer.consumed) == 1

    w.clock.now = START + timedelta(seconds=121)
    assert await w.processor.sweep() == 1

    assert [conversation for conversation, _ in w.poster.posts] == ["C1", "C2", "C2"]
    assert len(w.consumer.consumed) == 1
    done = await w.item()
    assert (done.state, done.attempts) == (ItemState.DONE, 2)


async def test_a_failed_consumer_is_retried_without_reposting() -> None:
    w = world()
    w.consumer.failures = 1

    await w.processor.ingest(instance(), delivery())
    w.clock.now = START + timedelta(hours=1)
    await w.processor.sweep()

    assert len(w.poster.posts) == 2 and len(w.consumer.consumed) == 1
    assert (await w.item()).state is ItemState.DONE


async def test_an_unmatched_delivery_posts_the_fallback_and_is_left_render_failed() -> None:
    w = world()

    with capture_logs() as logs:
        await w.processor.ingest(instance(), delivery(document={"source": "elsewhere"}))

    assert all(isinstance(message, FallbackMessage) for _, message in w.poster.posts)
    assert (await w.item()).state is ItemState.RENDER_FAILED
    assert w.consumer.consumed == []
    assert any(entry["event"] == "webhook_unmatched" for entry in logs)


async def test_attempts_past_the_cap_dead_letter_the_item(tmp_path: Path) -> None:
    install_webhooks_files(tmp_path, base="[webhooks]\nretry_max_attempts = 2\n")
    w = world(jitter=lambda: 0.0)
    w.poster.script["C1"] = [OperationResult.transient_error("down")] * 2

    with capture_logs() as logs:
        await w.processor.ingest(instance(), delivery())
        w.clock.now = START + timedelta(hours=1)
        await w.processor.sweep()

    item = await w.item()
    assert (item.state, item.attempts) == (ItemState.DEAD, 2)
    dead = [entry for entry in logs if entry["event"] == "webhook_dead_lettered"]
    assert dead and dead[0]["instance_ref"] == "ref-1" and "Message" not in str(dead[0])


async def test_a_permanent_post_failure_dead_letters_after_the_other_targets() -> None:
    w = world()
    w.poster.script["C1"] = [OperationResult.permanent_error("not_in_channel")]

    await w.processor.ingest(instance(), delivery())

    assert [conversation for conversation, _ in w.poster.posts] == ["C1", "C2"]
    assert (await w.item()).state is ItemState.DEAD


async def test_an_attempt_past_the_deadline_keeps_its_lease_and_the_sweeper_takes_it_over_once_expired(tmp_path: Path) -> None:
    install_webhooks_files(
        tmp_path, base="[webhooks]\ninline_processing_deadline_seconds = 0.05\nprocessing_lease_margin_seconds = 1\n"
    )
    w = world()
    w.poster.delay = 0.2

    outcome = await w.processor.ingest(instance(), delivery())
    leased = await w.item()
    assert outcome is IngestOutcome.PERSISTED
    assert (leased.state, leased.owner) == (ItemState.PROCESSING, "token-0")

    assert await w.processor.sweep() == 0, "an unexpired lease is never taken"

    w.poster.delay = 0.0
    w.clock.now = START + timedelta(seconds=5)
    assert await w.processor.sweep() == 1
    taken = await w.item()
    assert (taken.state, taken.attempts) == (ItemState.DONE, 2)


async def test_a_subscription_confirmation_is_confirmed_from_its_item() -> None:
    w = world()
    url = "https://sns.ca-central-1.amazonaws.com/?Action=ConfirmSubscription&Token=t"

    await w.processor.ingest(instance(), delivery(kind=ItemKind.SUBSCRIPTION_CONFIRMATION, subscribe_url=url))

    assert w.confirmer.confirmed == [url]
    assert w.poster.posts == []
    assert (await w.item()).state is ItemState.DONE


async def test_a_confirmation_that_could_not_complete_is_retried() -> None:
    w = world()
    w.confirmer.results = [OperationResult.transient_error("timeout")]

    await w.processor.ingest(
        instance(), delivery(kind=ItemKind.SUBSCRIPTION_CONFIRMATION, subscribe_url="https://sns.ca-central-1.amazonaws.com/x")
    )

    assert (await w.item()).state is ItemState.RETRY


async def test_a_passthrough_goes_to_slack_destinations_only() -> None:
    google = Destination(WorkplaceSystem.GOOGLE, "example.com", "space-1")
    instance_ = instance(protocol="legacy_slack_json", sender_kinds=(), destinations=(C2, google))
    w = world(instance_=instance_)

    with capture_logs() as logs:
        await w.processor.ingest(instance_, delivery(document={"text": "deployed", "channel": "C-PAYLOAD"}))

    assert [(conversation, type(message)) for conversation, message in w.poster.posts] == [("C2", PassthroughMessage)]
    assert w.consumer.consumed == []
    assert any(entry["event"] == "webhook_destination_skipped" for entry in logs)
    assert (await w.item()).state is ItemState.DONE


async def test_the_sweeper_dead_letters_the_items_of_a_disabledinstance() -> None:
    w = world(jitter=lambda: 0.0)
    w.poster.script["C1"] = [OperationResult.transient_error("down")]
    await w.processor.ingest(instance(), delivery())
    w.instances.instances["ref-1"] = instance(state=InstanceState.DISABLED)

    w.clock.now = START + timedelta(hours=1)
    await w.processor.sweep()

    assert (await w.item()).state is ItemState.DEAD
