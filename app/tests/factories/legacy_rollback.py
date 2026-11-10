"""Marker-2 incident items as the upgrade job leaves them, and DynamoDB's number typing, for rollback-guard tests."""

from typing import Any

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

from contracts.records import SetAttribute
from features.incident.core.adapters.item_upgrade import ItemUpgrade, plan_item_upgrade
from tests.factories.legacy_upgrade import TENANTS, legacy_item


def through_dynamodb(item: dict[str, Any]) -> dict[str, Any]:
    """Return ``item`` as a reader gets it back from DynamoDB: numbers become ``Decimal``."""
    serializer = TypeSerializer()
    deserializer = TypeDeserializer()
    return {name: deserializer.deserialize(serializer.serialize(value)) for name, value in item.items()}


def upgraded_item(incident_id: str = "inc-1", **legacy_overrides: Any) -> dict[str, Any]:
    """A legacy item after the real upgrade plan is applied, read back from DynamoDB."""
    item = legacy_item(incident_id, **legacy_overrides)
    planned = plan_item_upgrade(item, TENANTS)
    assert isinstance(planned, ItemUpgrade)
    for change in planned.changes:
        assert isinstance(change, SetAttribute)
        item[change.attribute] = change.value
    return through_dynamodb(item)
