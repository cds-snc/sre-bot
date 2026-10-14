"""Enrollment check for the ConditionalWriteStore conformance suite.

``conditional_write_store`` and ``expiring_conditional_write_store`` are parametrized over
the implementations listed in ``conditional_write_store_implementations``. This test
compares that list with every concrete production class that explicitly
subclasses ConditionalWriteStore, so a new adapter or fake that is not added to the
fixtures fails here rather than silently skipping the conformance cases.
"""

from contracts.coordination import ConditionalWriteStore
from tests.fixtures.conformance import concrete_production_subclasses


def test_conformance_fixture_covers_every_conditional_write_store_implementation(conditional_write_store_implementations):
    assert set(conditional_write_store_implementations) == concrete_production_subclasses(ConditionalWriteStore)
