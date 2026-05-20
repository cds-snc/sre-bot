"""Generic DynamoDB storage service for feature packages.

Provides an infrastructure-level abstraction over DynamoDB with automatic
Python ↔ DynamoDB type conversion via boto3's TypeSerializer/TypeDeserializer.
"""

from infrastructure.storage.protocol import StorageService
from infrastructure.storage.service import get_storage_service

__all__ = ["StorageService", "get_storage_service"]
