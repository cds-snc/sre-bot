"""The tenant verifier: the tenant a workplace system's vendor confirms for this instance's credentials.

The configured-systems read says which tenant an instance is configured for; this
contract asks the vendor which tenant the credentials actually act in, and judges
the answer by the same rule as inbound requests (``decisions/workplace-systems.md``
rule 3). The check is host-owned, so vendor packages export no tenant code. A batch
writer verifies once before it stamps the tenant on records.
"""

from typing import Protocol

from contracts.operations.result import OperationResult
from contracts.workplace.systems import WorkplaceSystem


class TenantVerifier(Protocol):
    """Confirms, with one vendor call, the tenant a configured system's credentials act in."""

    def verified_tenant(self, system: WorkplaceSystem) -> OperationResult[str]:
        """Return the tenant id the vendor confirmed for the configured entry.

        Success carries the tenant id, equal to ``ConfiguredSystems.tenants()[system]``.
        UNAUTHORIZED with TENANT_MISMATCH, naming the expected and received ids, when the
        vendor reports another tenant; the classified status with TENANT_CHECK_FAILED when
        the call fails; PERMANENT_ERROR with CONFIG_NOT_CONFIGURED when the system has no
        tenant entry, and with UNSUPPORTED_OPERATION when no verifier exists for it. The
        call is synchronous and blocking: callers run it in a worker thread.
        """
        ...
