from typing import TypedDict, Any, Optional, Dict, Protocol


class OperationResultLike(Protocol):
    status: Any
    message: str
    data: Optional[dict]
    error_code: Optional[str]
    retry_after: Optional[int]


class PrimaryDataTypedDict(TypedDict, total=False):
    status: Optional[str]
    message: str
    data: Any
    error_code: Optional[str]
    retry_after: Optional[int]


class ReadResponseTypedDict(TypedDict):
    success: bool
    action: str
    primary: PrimaryDataTypedDict
    timestamp: str
    group_id: Optional[str]
    member_email: Optional[str]


class OrchestrationResponseTypedDict(ReadResponseTypedDict, total=False):
    correlation_id: str
    propagation: Dict[str, PrimaryDataTypedDict]
    partial_failures: bool
