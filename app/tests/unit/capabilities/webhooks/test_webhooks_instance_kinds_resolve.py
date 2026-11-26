"""Unit tests for resolving an instance's sender kinds against the loaded kinds.

A stored instance is untrusted: unknown, repeated or excess ids are skipped and reported.
"""

import pytest

from capabilities.webhooks.domain.kinds import AuthTier, Destination, Owner, SenderKind, WebhookInstance, resolve_kinds
from tests.unit.capabilities.webhooks.conftest import build_kind, kind_document

pytestmark = pytest.mark.unit


def _instance(*kind_ids: str) -> WebhookInstance:
    return WebhookInstance(
        instance_ref="inst-1",
        name="Billing",
        owner=Owner(team="sre", contact="sre@example.com"),
        auth_tier=AuthTier.LEGACY,
        protocol="aws_sns",
        sender_kinds=kind_ids,
        destinations=(Destination(channel="C123", triage=True),),
    )


def _kinds() -> dict[str, SenderKind]:
    return {kind_id: build_kind(kind_document(id=kind_id)) for kind_id in ("a", "b", "c")}


def test_kinds_resolve_in_the_instance_order() -> None:
    kinds, skipped = resolve_kinds(_instance("c", "a"), _kinds(), max_kinds=20)

    assert ([kind.id for kind in kinds], skipped) == (["c", "a"], ())


def test_an_unknown_kind_is_skipped_and_reported_never_raised() -> None:
    kinds, skipped = resolve_kinds(_instance("a", "gone", "b"), _kinds(), max_kinds=20)

    assert ([kind.id for kind in kinds], skipped) == (["a", "b"], ("gone",))


def test_repeated_and_excess_kinds_are_skipped() -> None:
    kinds, skipped = resolve_kinds(_instance("a", "a", "b", "c"), _kinds(), max_kinds=2)

    assert ([kind.id for kind in kinds], skipped) == (["a", "b"], ("a", "c"))
