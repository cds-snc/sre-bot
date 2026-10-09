"""Tests for the review form views after Save draft and Draft with AI.

``build_saved_form_view`` and ``build_filled_form_view`` choose the notice, the
instructions, the security checkbox and the AI section from a
``StatusUpdateFormState``. Each case is compared with the review form built
directly with the expected arguments, so the tests pin the choice and not the
Block Kit layout, which the review view tests cover. Catalogues are loaded by
the directory's conftest.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from contracts.operations.codes import ErrorCode
from features.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from features.incident.scribe.domain import StatusUpdateFormState, StatusUpdateOutcomeKind
from features.incident.scribe.entrypoints.slack_views import (
    build_filled_form_view,
    build_review_view,
    build_saved_form_view,
    generate_notice,
    save_notice,
)
from features.incident.scribe.status_update import DRAFT_UNPARSEABLE_CODE

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 9, 15, 0, tzinfo=UTC)
_TEXT = StatusUpdateText(affected_service="service", impact="impact", current_action="action", workaround="none")
_UPDATE = StatusUpdate(
    incident_id="inc-1",
    sequence=4,
    state=StatusUpdateState.DRAFT,
    stage=StatusUpdateStage.INVESTIGATING,
    en=_TEXT,
    fr=_TEXT,
    next_update_at=_NOW,
    author="U1",
    transcript_cutoff=_NOW,
    transcript_fingerprint="v1:sha256:abc",
    created_at=_NOW,
)
_METADATA = '{"sequence": 4}'


def _expected(key: str, *, notice: Any = save_notice, **kwargs: Any) -> dict[str, Any]:
    return build_review_view(_UPDATE, "fr-FR", _METADATA, notice=notice(key, "fr-FR"), **kwargs)


@pytest.mark.parametrize(
    ("state", "key", "with_ai"),
    [
        (StatusUpdateFormState(update=_UPDATE, ai_available=True), "saved_note", True),
        (StatusUpdateFormState(update=_UPDATE, ai_available=False), "saved_note", False),
        (StatusUpdateFormState(update=_UPDATE, ai_available=True, kept=True, failure_code="X"), "save_failed", True),
    ],
)
def test_saved_form_notice_and_ai_section(state: StatusUpdateFormState, key: str, with_ai: bool) -> None:
    """A save shows the saved notice and a kept draft the failure notice; the AI section follows the flag."""
    assert build_saved_form_view(state, "fr-FR", _METADATA) == _expected(key, with_ai=with_ai)


@pytest.mark.parametrize(
    ("kind", "key"),
    [
        (StatusUpdateOutcomeKind.DRAFTED, "generated_note"),
        (StatusUpdateOutcomeKind.CARRIED_FORWARD, "generate_carried_forward"),
    ],
)
def test_filled_form_shows_the_fill_notice_without_instructions(kind: StatusUpdateOutcomeKind, key: str) -> None:
    """A fill or carry forward shows its notice; the instructions are not carried into the new draft's form."""
    state = StatusUpdateFormState(update=_UPDATE, ai_available=True, kind=kind)

    view = build_filled_form_view(state, "fr-FR", _METADATA, instructions="be brief")

    assert view == _expected(key, notice=generate_notice, with_ai=True)


@pytest.mark.parametrize(
    ("code", "key", "security_confirm", "with_ai"),
    [
        (ErrorCode.SECURITY_CONFIRMATION_REQUIRED, "generate_security", True, True),
        (ErrorCode.TEXT_GENERATION_UNAVAILABLE, "generate_unavailable", False, False),
        (ErrorCode.EMPTY_HISTORY, "generate_empty_history", False, True),
        (DRAFT_UNPARSEABLE_CODE, "generate_unparseable", False, True),
        (ErrorCode.RATE_LIMITED, "generate_failed", False, True),
        (None, "generate_failed", False, True),
    ],
)
def test_filled_form_after_a_refusal_keeps_the_instructions(
    code: str | None, key: str, security_confirm: bool, with_ai: bool
) -> None:
    """A kept draft shows the refusal's notice and the instructions; the checkbox appears only after a security refusal."""
    state = StatusUpdateFormState(update=_UPDATE, ai_available=with_ai, kept=True, failure_code=code)

    view = build_filled_form_view(state, "fr-FR", _METADATA, instructions="be brief")

    expected = _expected(
        key,
        notice=generate_notice,
        instructions="be brief",
        security_confirm=security_confirm,
        with_ai=with_ai,
    )
    assert view == expected
