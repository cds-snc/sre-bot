"""Behavior tests for the StatusUpdate record and its state and stage vocabularies.

Plain value tests: no store or stub is involved. They pin the record's
invariants (a named incident, a positive sequence, timezone-aware times) and
the only state moves a store may perform.
"""

import dataclasses
from datetime import UTC, datetime

import pytest

from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText

pytestmark = pytest.mark.unit

AT = datetime(2026, 10, 7, 14, 0, tzinfo=UTC)
TEXT = StatusUpdateText(
    affected_service="GC Notify", impact="Emails are delayed.", current_action="Restarting workers.", workaround=""
)


def _update(**overrides: object) -> StatusUpdate:
    fields: dict[str, object] = {
        "incident_id": "7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11",
        "sequence": 1,
        "state": StatusUpdateState.DRAFT,
        "stage": StatusUpdateStage.INVESTIGATING,
        "en": TEXT,
        "fr": TEXT,
        "next_update_at": AT,
        "author": "U0AUTHOR",
        "transcript_cutoff": AT,
        "transcript_fingerprint": "fp-1",
        "created_at": AT,
    }
    fields.update(overrides)
    return StatusUpdate(**fields)  # type: ignore[arg-type]


def test_a_draft_record_is_frozen_and_starts_without_an_approver() -> None:
    """A new draft carries no approval or publication; the record is an immutable value."""
    update = _update()

    assert update.approver is None
    assert update.approved_at is None
    assert update.published_at is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        update.sequence = 2  # type: ignore[misc]


@pytest.mark.parametrize("incident_id", ["", "   "])
def test_a_blank_incident_id_is_rejected(incident_id: str) -> None:
    """Every record lives under an incident; a blank id is a programmer error."""
    with pytest.raises(ValueError, match="incident_id"):
        _update(incident_id=incident_id)


def test_a_sequence_below_one_is_rejected() -> None:
    """Sequences count from 1 so that the zero-padded key orders updates chronologically."""
    with pytest.raises(ValueError, match="sequence"):
        _update(sequence=0)


@pytest.mark.parametrize("field", ["next_update_at", "transcript_cutoff", "created_at", "approved_at", "published_at"])
def test_a_naive_time_is_rejected(field: str) -> None:
    """Every stored time is an instant; a naive datetime cannot be rendered in ET or compared safely."""
    with pytest.raises(ValueError, match=field):
        _update(**{field: datetime(2026, 10, 7, 14, 0)})


@pytest.mark.parametrize(
    ("current", "target", "allowed"),
    [
        (StatusUpdateState.DRAFT, StatusUpdateState.APPROVED, True),
        (StatusUpdateState.APPROVED, StatusUpdateState.PUBLISHED, True),
        (StatusUpdateState.DRAFT, StatusUpdateState.PUBLISHED, False),
        (StatusUpdateState.DRAFT, StatusUpdateState.DRAFT, False),
        (StatusUpdateState.APPROVED, StatusUpdateState.DRAFT, False),
        (StatusUpdateState.PUBLISHED, StatusUpdateState.DRAFT, False),
        (StatusUpdateState.PUBLISHED, StatusUpdateState.APPROVED, False),
        (StatusUpdateState.PUBLISHED, StatusUpdateState.PUBLISHED, False),
    ],
)
def test_state_moves_only_one_step_forward(current: StatusUpdateState, target: StatusUpdateState, allowed: bool) -> None:
    """Nothing is published unapproved and nothing goes back to draft."""
    assert current.can_move_to(target) is allowed


def test_stages_are_declared_in_their_public_forward_order() -> None:
    """Consumers rank stages by declaration order; the values are the stored strings."""
    assert [stage.value for stage in StatusUpdateStage] == ["investigating", "identified", "monitoring", "resolved"]
