from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AWSLowLevelClient(Protocol):
    """Protocol for low-level boto3-like clients used by infrastructure.

    Implementations should provide service-specific methods (e.g., put_item,
    get_item, list_accounts) depending on the AWS service. This protocol is
    intentionally permissive and is used for typing and dependency declarations.
    """

    def __getattr__(self, name: str) -> Any:  # pragma: no cover - typing helper
        ...


@runtime_checkable
class DynamoDBClientWrapper(Protocol):
    """Protocol for the DynamoDB wrapper module.

    The wrapper exposes functions such as `get_item`, `put_item`, `query`, and
    `scan` that return `OperationResult` objects.
    """

    def get_item(
        self, table_name: str, key: dict, **kwargs
    ) -> Any:  # pragma: no cover - typing helper
        ...

    def put_item(
        self, table_name: str, item: dict, **kwargs
    ) -> Any:  # pragma: no cover - typing helper
        ...

    def query(
        self, table_name: str, key_condition_expression: Any, **kwargs
    ) -> Any:  # pragma: no cover
        ...

    def scan(self, table_name: str, **kwargs) -> Any:  # pragma: no cover
        ...
