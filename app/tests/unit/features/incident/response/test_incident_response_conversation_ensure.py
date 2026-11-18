"""``ensure_conversation``: one conversation per incident, the five rules of decisions/incident-management.md.

Runs over the core in-memory incident store and conversation (held to the Slack
adapter's rules by the core parity suite) and real claims: ``ThreadedClaims`` over
the in-memory conditional-write store. A test-local conversation subclass scripts
what one create attempt does (fail transiently, raise, or create the channel and
then fail, as a timeout after the call landed does). Assertions read the returned
reference, the channels the fake holds by name and the claims, since rule 2's
claim and rule 3's ``find_own`` are what keep a retry from opening a second
channel.

Rules: (1) a record that names a conversation never creates one; (2) each name is
claimed for the incident before the call, a name another incident claimed is
skipped; (3) after any create that did not succeed, ``find_own`` comes first and
the bot's own channel bound to this incident, or unbound while this incident holds
the claim, is reused; (4) the next name only when the channel is proven another
incident's or not the bot's; (5) an unknown outcome with nothing found is reported
without moving on. A taken name is logged at info, never as a warning.
"""

from dataclasses import replace
from datetime import date
from typing import Literal

import pytest
from structlog.testing import capture_logs

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from features.incident.core.adapters.in_memory import InMemoryIncidentConversation, InMemoryIncidentStore
from features.incident.core.adapters.slack import slack_channel_name
from features.incident.core.api import ConversationName, ConversationReference, incident_conversation_names
from features.incident.response.adapters.claims import ThreadedClaims
from features.incident.response.service.conversation import ensure_conversation, name_claim_key
from infrastructure.coordination.in_memory import InMemoryConditionalWriteStore
from tests.factories.incident import SLACK_TENANT, binding_on, declared_incident, slack_conversation

pytestmark = pytest.mark.unit

OPENED_ON = date(2026, 11, 18)
NAMES = incident_conversation_names("Payments down", OPENED_ON, production=True)
FIRST = slack_channel_name(NAMES[0])

Script = Literal["transient", "raise", "created_then_transient"]


class ScriptedConversation(InMemoryIncidentConversation):
    """Scripts each create attempt by its name's attempt number; unscripted attempts create as the fake does."""

    def __init__(self, script: dict[int, Script] | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._script = dict(script or {})
        self.attempts: list[int] = []

    async def create(self, name: ConversationName, *, private: bool) -> OperationResult[ConversationReference]:
        self.attempts.append(name.attempt)
        match self._script.get(name.attempt):
            case "transient":
                return OperationResult.transient_error("Slack create timed out")
            case "raise":
                raise RuntimeError("unclassified")
            case "created_then_transient":
                await super().create(name, private=private)
                return OperationResult.transient_error("Slack create timed out after the call landed")
            case None:
                return await super().create(name, private=private)


def _claims() -> ThreadedClaims:
    return ThreadedClaims(InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=300))


async def _ensure(
    conversations: InMemoryIncidentConversation,
    *,
    incident_id: str = "inc-1",
    store: InMemoryIncidentStore | None = None,
    claims: ThreadedClaims | None = None,
) -> OperationResult[ConversationReference]:
    store = store if store is not None else InMemoryIncidentStore()
    return await ensure_conversation(
        declared_incident(incident_id),
        incidents=store,
        conversations=conversations,
        claims=claims if claims is not None else _claims(),
        names=NAMES,
        tenant=SLACK_TENANT,
    )


async def test_a_record_that_names_a_conversation_never_creates_one() -> None:
    conversations = ScriptedConversation(tenant=SLACK_TENANT, open_ids=["C0OLD"])
    incident = replace(declared_incident("inc-1"), conversation=slack_conversation("C0OLD"))

    result = await ensure_conversation(
        incident,
        incidents=InMemoryIncidentStore(),
        conversations=conversations,
        claims=_claims(),
        names=NAMES,
        tenant=SLACK_TENANT,
    )

    assert result.data == slack_conversation("C0OLD")
    assert conversations.attempts == []


async def test_a_free_first_name_creates_the_conversation() -> None:
    conversations = ScriptedConversation(tenant=SLACK_TENANT)

    result = await _ensure(conversations)

    assert result.is_success
    assert result.data == slack_conversation("C0NEW1")
    assert conversations.attempts == [1]


async def test_a_name_another_incident_claimed_is_skipped_without_a_call() -> None:
    claims = _claims()
    other = await claims.claim(name_claim_key(SLACK_TENANT, NAMES[0]))
    assert other.claim_token is not None
    await claims.complete(name_claim_key(SLACK_TENANT, NAMES[0]), {"incident_id": "inc-other"}, other.claim_token)
    conversations = ScriptedConversation(tenant=SLACK_TENANT)

    result = await _ensure(conversations, claims=claims)

    assert result.is_success
    assert conversations.attempts == [2]


async def test_a_name_this_incident_claimed_earlier_is_tried_again() -> None:
    claims = _claims()
    conversations = ScriptedConversation({1: "transient"}, tenant=SLACK_TENANT)
    first = await _ensure(conversations, claims=claims)
    assert not first.is_success

    retried = await _ensure(ScriptedConversation(tenant=SLACK_TENANT), claims=claims)

    assert retried.is_success


async def test_a_create_that_landed_before_failing_reuses_the_unbound_channel_this_incident_claimed() -> None:
    conversations = ScriptedConversation({1: "created_then_transient"}, tenant=SLACK_TENANT)

    result = await _ensure(conversations)

    assert result.data == slack_conversation("C0NEW1")
    assert conversations.attempts == [1]


async def test_the_bots_channel_already_bound_to_this_incident_is_reused() -> None:
    store = InMemoryIncidentStore()
    store.seed(declared_incident("inc-1"))
    await store.attach_conversation("inc-1", binding_on("C0MINE", "inc-1"))
    conversations = ScriptedConversation(tenant=SLACK_TENANT, open_ids=["C0MINE"], names={FIRST: "C0MINE"})

    result = await _ensure(conversations, store=store)

    assert result.data == slack_conversation("C0MINE")


async def test_the_bots_channel_bound_to_another_incident_moves_to_the_next_name() -> None:
    store = InMemoryIncidentStore()
    store.seed(declared_incident("inc-other"))
    await store.attach_conversation("inc-other", binding_on("C0THEIRS", "inc-other"))
    conversations = ScriptedConversation(tenant=SLACK_TENANT, open_ids=["C0THEIRS"], names={FIRST: "C0THEIRS"})

    result = await _ensure(conversations, store=store)

    assert result.data == slack_conversation("C0NEW1")
    assert conversations.attempts == [1, 2]


async def test_a_name_taken_by_a_channel_that_is_not_the_bots_moves_to_the_next_name_logged_at_info() -> None:
    conversations = ScriptedConversation(tenant=SLACK_TENANT, foreign_names=[FIRST])

    with capture_logs() as logs:
        result = await _ensure(conversations)

    assert result.is_success
    assert conversations.attempts == [1, 2]
    taken = [entry for entry in logs if entry["event"] == "incident_conversation_name_taken"]
    assert [entry["log_level"] for entry in taken] == ["info"]
    assert not [entry for entry in logs if entry["log_level"] == "warning"]


@pytest.mark.parametrize("script", ["transient", "raise"])
async def test_an_unknown_outcome_with_nothing_found_is_reported_without_moving_on(script: Script) -> None:
    conversations = ScriptedConversation({1: script}, tenant=SLACK_TENANT)

    result = await _ensure(conversations)

    assert not result.is_success
    assert conversations.attempts == [1]


async def test_every_name_taken_is_conversation_name_taken() -> None:
    conversations = ScriptedConversation(tenant=SLACK_TENANT, foreign_names=[slack_channel_name(n) for n in NAMES])

    result = await _ensure(conversations)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.CONVERSATION_NAME_TAKEN
    assert conversations.attempts == [1, 2, 3, 4, 5]


async def test_a_name_held_in_progress_by_another_run_is_skipped() -> None:
    claims = _claims()
    held = await claims.claim(name_claim_key(SLACK_TENANT, NAMES[0]))
    assert held.claim_token is not None
    conversations = ScriptedConversation(tenant=SLACK_TENANT)

    result = await _ensure(conversations, claims=claims)

    assert result.is_success
    assert conversations.attempts == [2]
