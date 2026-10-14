"""DynamoDB-backed records provider.

The RecordStore Protocol and its value types live in ``contracts.records``;
this package holds the DynamoDB implementation, the in-memory fake and the
``get_record_store`` provider.
"""

from infrastructure.records.service import get_record_store

__all__ = ["get_record_store"]
