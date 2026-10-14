"""Coordination contract: the ConditionalWriteStore Protocol, its value types, and the lease and idempotency facades."""

from contracts.coordination.idempotency import IdempotencyStore
from contracts.coordination.lease import LeaseStore
from contracts.coordination.policy import ReadFailurePolicy
from contracts.coordination.store import ClaimOutcome, ClaimResult, ConditionalWriteStore

__all__ = [
    "ClaimOutcome",
    "ClaimResult",
    "ConditionalWriteStore",
    "IdempotencyStore",
    "LeaseStore",
    "ReadFailurePolicy",
]
