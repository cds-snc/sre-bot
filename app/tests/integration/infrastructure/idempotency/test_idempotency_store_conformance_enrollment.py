"""Enrollment check for the IdempotencyStore conformance suite.

``idempotency_store`` and ``expiring_idempotency_store`` are parametrized over
the implementations listed in ``idempotency_store_implementations``. This test
compares that list with every concrete production class that explicitly
subclasses IdempotencyStore, so a new adapter or fake that is not added to the
fixtures fails here rather than silently skipping the conformance cases.
"""

from infrastructure.idempotency.protocol import IdempotencyStore
from tests.fixtures.conformance import concrete_production_subclasses


def test_conformance_fixture_covers_every_idempotency_store_implementation(idempotency_store_implementations):
    assert set(idempotency_store_implementations) == concrete_production_subclasses(IdempotencyStore)
