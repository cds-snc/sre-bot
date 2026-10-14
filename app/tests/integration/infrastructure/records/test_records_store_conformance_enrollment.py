"""Enrollment check for the RecordStore conformance suites.

``any_record_store`` is parametrized over the implementations listed in
``record_store_implementations``. This test compares that list with every
concrete production class that explicitly subclasses RecordStore, so a new
adapter or fake that is not added to the fixture fails here rather than
silently skipping the conformance cases.
"""

from contracts.records import RecordStore
from tests.fixtures.conformance import concrete_production_subclasses


def test_conformance_fixture_covers_every_record_store_implementation(record_store_implementations):
    assert set(record_store_implementations) == concrete_production_subclasses(RecordStore)
