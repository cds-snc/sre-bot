"""Records contract: the RecordStore protocol and its DynamoDB provider.

Provides an infrastructure-level abstraction over DynamoDB with automatic
Python ↔ DynamoDB type conversion via boto3's TypeSerializer/TypeDeserializer.
"""

from infrastructure.records.protocol import RecordStore
from infrastructure.records.service import get_record_store

__all__ = ["RecordStore", "get_record_store"]
