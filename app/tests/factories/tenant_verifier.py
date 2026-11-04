"""Fake TenantVerifier for tests: a fixed result per system, recording every call."""

from collections.abc import Mapping

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.workplace import WorkplaceSystem


class FakeTenantVerifier:
    """Returns the configured result for a system, else UNSUPPORTED_OPERATION, and records each system asked."""

    def __init__(self, results: Mapping[WorkplaceSystem, OperationResult[str]]) -> None:
        self._results = dict(results)
        self.calls: list[WorkplaceSystem] = []

    def verified_tenant(self, system: WorkplaceSystem) -> OperationResult[str]:
        self.calls.append(system)
        if system in self._results:
            return self._results[system]
        return OperationResult.permanent_error(f"no tenant verifier for {system.value}", ErrorCode.UNSUPPORTED_OPERATION)
