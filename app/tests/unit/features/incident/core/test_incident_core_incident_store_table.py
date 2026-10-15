"""Behavior tests for the incidents table declaration.

The declaration is what the store queries through; its key and index names must
match the deployed table in terraform/dynamodb.tf, which this test reads as text
rather than duplicating the names.
"""

import re
from pathlib import Path

import pytest

from contracts.records import KeySchema
from features.incident.core.store import OPEN_BUCKET, RECORD_VERSION, incidents_table

pytestmark = pytest.mark.unit

TERRAFORM = Path(__file__).resolve().parents[6] / "terraform" / "dynamodb.tf"


def _incidents_resource() -> str:
    text = TERRAFORM.read_text(encoding="utf-8")
    match = re.search(r'resource "aws_dynamodb_table" "incidents_table" \{(.*?)\n\}', text, re.DOTALL)
    assert match is not None
    return match.group(1)


def test_the_table_is_keyed_by_incident_id_under_the_given_name() -> None:
    table = incidents_table("incidents")

    assert table.name == "incidents"
    assert table.key == KeySchema(partition="id")


def test_the_indexes_match_the_deployed_table() -> None:
    """by_channel is keyed by channel_id; open by open_bucket then opened_at, as terraform declares them."""
    table = incidents_table("incidents")
    resource = _incidents_resource()

    assert table.indexes["by_channel"].key == KeySchema(partition="channel_id")
    assert table.indexes["open"].key == KeySchema(partition="open_bucket", sort="opened_at")
    for index in table.indexes.values():
        assert f'name            = "{index.physical_name}"' in resource
        assert f'attribute_name = "{index.key.partition}"' in resource
    assert set(table.indexes) == {"by_channel", "open"}


def test_the_writer_constants_are_fixed() -> None:
    """Writers stamp end-state items with this version and open items with this bucket."""
    assert RECORD_VERSION == 1
    assert OPEN_BUCKET == "OPEN"
