"""Behavior tests for the bindings table declaration.

The declaration is what the store queries through; its key, index and name must
match the deployed table in terraform/dynamodb.tf, which this test reads as text
rather than duplicating the names, and the configured default must name that table.
"""

import re
import tomllib
from pathlib import Path

import pytest

from contracts.records import KeySchema
from features.incident.common.settings import IncidentCoreSettings
from features.incident.core.store import bindings_table

pytestmark = pytest.mark.unit

REPOSITORY = Path(__file__).resolve().parents[6]
TERRAFORM = REPOSITORY / "terraform" / "dynamodb.tf"
BASE_CONFIG = REPOSITORY / "app" / "config" / "base.toml"


def _bindings_resource() -> str:
    text = TERRAFORM.read_text(encoding="utf-8")
    match = re.search(r'resource "aws_dynamodb_table" "sre_bot_incident_bindings" \{(.*?)\n\}', text, re.DOTALL)
    assert match is not None
    return match.group(1)


def test_the_table_is_keyed_by_incident_and_binding_key_under_the_given_name() -> None:
    table = bindings_table("bindings")
    resource = _bindings_resource()

    assert table.name == "bindings"
    assert table.key == KeySchema(partition="incident_id", sort="binding_key")
    assert f'hash_key       = "{table.key.partition}"' in resource
    assert f'range_key      = "{table.key.sort}"' in resource


def test_the_index_matches_the_deployed_table() -> None:
    """by_conversation is keyed by conversation_id alone and projects every attribute, as terraform declares it."""
    table = bindings_table("bindings")
    resource = _bindings_resource()
    index = table.indexes["by_conversation"]

    assert set(table.indexes) == {"by_conversation"}
    assert index.key == KeySchema(partition="conversation_id")
    assert f'name            = "{index.physical_name}"' in resource
    assert f'attribute_name = "{index.key.partition}"' in resource
    assert 'projection_type = "ALL"' in resource


def test_the_configured_default_and_base_value_name_the_deployed_table() -> None:
    name = re.search(
        r'resource "aws_dynamodb_table" "sre_bot_incident_bindings" \{\s*name\s*=\s*"([^"]+)"', TERRAFORM.read_text("utf-8")
    )
    assert name is not None
    base = tomllib.loads(BASE_CONFIG.read_text(encoding="utf-8"))

    assert IncidentCoreSettings().bindings_table == name.group(1)
    assert base["incident_core"]["bindings_table"] == name.group(1)
