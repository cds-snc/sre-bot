"""Generic DynamoDB storage service for feature packages.

Provides an infrastructure-level abstraction over DynamoDB with automatic
Python ↔ DynamoDB type conversion via boto3's TypeSerializer/TypeDeserializer.

Usage::

    from infrastructure.services import StorageServiceDep

    class MyRepository:
        def __init__(self, storage: StorageService) -> None:
            self._storage = storage
"""

from infrastructure.storage.protocol import StorageService

__all__ = ["StorageService"]
