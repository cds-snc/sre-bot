"""Read-failure policy for a claim the store reports as INDETERMINATE."""

from enum import Enum
from typing import assert_never

from contracts.coordination.store import ClaimOutcome, ClaimResult


class ReadFailurePolicy(Enum):
    """How a facade treats a claim whose contended re-read failed.

    FAIL_CLOSED treats the unreadable record as held by someone else: the caller
    does not proceed.
    """

    FAIL_CLOSED = "fail_closed"


def resolve_indeterminate(outcome: ClaimOutcome, policy: ReadFailurePolicy) -> ClaimOutcome:
    """Map an INDETERMINATE claim to a determinate one under policy; pass any other outcome through."""
    if outcome.result is not ClaimResult.INDETERMINATE:
        return outcome
    match policy:
        case ReadFailurePolicy.FAIL_CLOSED:
            return ClaimOutcome(result=ClaimResult.IN_PROGRESS)
        case _:
            assert_never(policy)
