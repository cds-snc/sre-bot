"""Records contract: the RecordStore protocol, its value types and DynamoDB provider.

Provides an infrastructure-level abstraction over DynamoDB with automatic
Python ↔ DynamoDB type conversion via boto3's TypeSerializer/TypeDeserializer.
"""

from infrastructure.records.protocol import (
    KeySchema,
    KeyValue,
    RecordIndex,
    RecordQuery,
    RecordStore,
    RecordTable,
    SortCondition,
    SortOperator,
    SortOrder,
)
from infrastructure.records.service import get_record_store

__all__ = [
    "KeySchema",
    "KeyValue",
    "RecordIndex",
    "RecordQuery",
    "RecordStore",
    "RecordTable",
    "SortCondition",
    "SortOperator",
    "SortOrder",
    "get_record_store",
]
