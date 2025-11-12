"""Internal type hints for orchestration workflows.

This module defines Protocol and TypedDict definitions used for type-safe
internal data flows and orchestration result contracts. These are NOT Pydantic
models and do NOT provide runtime validation—they are purely for type hints.

Key distinction from schemas.py:
  - types.py: Internal protocol contracts for business logic layers
  - schemas.py: API validation contracts with Pydantic and OpenAPI support

Usage:
  - Imported by orchestration.py and orchestration_responses.py
  - Used to type-hint internal operation results and response structures
  - Do NOT use for API request/response serialization (use schemas.py instead)
"""

from typing import TypedDict, Any, Optional, Dict, Protocol


class OperationResultLike(Protocol):
    """Protocol for objects representing an operation result.

    Used to type-hint internal orchestration results without requiring a
    specific concrete class. This duck-typing approach allows different
    orchestration layers to return heterogeneous result types while
    maintaining type safety.

    Examples: OperationResult, ProviderOperationResult, etc.
    """

    status: Any
    message: str
    data: Optional[dict]
    error_code: Optional[str]
    retry_after: Optional[int]


class PrimaryDataTypedDict(TypedDict, total=False):
    """TypedDict for primary operation data in orchestration responses.

    Represents the main result of an operation execution. Used internally
    by orchestration_responses.py to type-hint response formatting.
    NOT for API serialization (use schemas.ActionResponse instead).
    """

    status: Optional[str]
    message: str
    data: Any
    error_code: Optional[str]
    retry_after: Optional[int]


class ReadResponseTypedDict(TypedDict):
    """TypedDict for a read operation response.

    Represents the standard structure of a single operation read response.
    Used internally for orchestration workflows to ensure consistent
    response structure across providers.
    """

    success: bool
    action: str
    primary: PrimaryDataTypedDict
    timestamp: str
    group_id: Optional[str]
    member_email: Optional[str]


class OrchestrationResponseTypedDict(ReadResponseTypedDict, total=False):
    """TypedDict for a complete orchestration response.

    Extends ReadResponseTypedDict with additional orchestration-specific
    fields such as correlation tracking and multi-provider propagation.

    Key distinction from schemas.BulkOperationResponse:
      - This: Internal orchestration contract (TypedDict, no validation)
      - schemas: API contract (Pydantic BaseModel with validation)
    """

    correlation_id: str
    propagation: Dict[str, PrimaryDataTypedDict]
    partial_failures: bool
