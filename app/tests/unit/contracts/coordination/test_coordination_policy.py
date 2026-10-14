"""Unit tests for the read-failure policy that resolves an INDETERMINATE claim.

Pure-function tests: resolve_indeterminate takes a ClaimOutcome and a policy and
returns a ClaimOutcome, so no store stub is needed. They pin that FAIL_CLOSED turns
an INDETERMINATE claim into a tokenless IN_PROGRESS and leaves every other result,
including a COMPLETED outcome payload, untouched.
"""

import pytest

from contracts.coordination import ClaimOutcome, ClaimResult, ReadFailurePolicy
from contracts.coordination.policy import resolve_indeterminate

pytestmark = pytest.mark.unit


def test_policy_has_only_fail_closed() -> None:
    assert list(ReadFailurePolicy) == [ReadFailurePolicy.FAIL_CLOSED]


def test_fail_closed_maps_indeterminate_to_in_progress_without_token_or_outcome() -> None:
    resolved = resolve_indeterminate(ClaimOutcome(result=ClaimResult.INDETERMINATE), ReadFailurePolicy.FAIL_CLOSED)

    assert resolved == ClaimOutcome(result=ClaimResult.IN_PROGRESS)


@pytest.mark.parametrize(
    "outcome",
    [
        ClaimOutcome(result=ClaimResult.NEW, claim_token="a" * 32),
        ClaimOutcome(result=ClaimResult.COMPLETED, outcome={"status": "done"}),
        ClaimOutcome(result=ClaimResult.IN_PROGRESS),
    ],
    ids=["new", "completed", "in_progress"],
)
def test_fail_closed_passes_determinate_outcomes_through_unchanged(outcome: ClaimOutcome) -> None:
    assert resolve_indeterminate(outcome, ReadFailurePolicy.FAIL_CLOSED) is outcome
