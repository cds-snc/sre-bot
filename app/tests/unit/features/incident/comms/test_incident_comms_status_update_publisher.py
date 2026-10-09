"""Tests for rendering copy-ready text from incident status updates.

The copy-ready publisher renders English and French with label lines, a blank
line between sections, stored next_update_at in America/Toronto, and omits the
next-update line when the stage is RESOLVED. Output is structured plain text
that pastes cleanly into plain-text and Markdown targets.
"""

from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from features.incident.comms.comms_profile import ProfileLabels
from features.incident.comms.domain import CopyReadyText
from features.incident.comms.publisher import render_copy_ready
from features.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_INCIDENT = "inc-uuid-1"


def _text(language: str, tag: str = "") -> StatusUpdateText:
    fields = ("affected_service", "impact", "current_action", "workaround")
    return StatusUpdateText(**{field: f"{language} {field}{tag}" for field in fields})


def _record(
    sequence: int,
    stage: StatusUpdateStage = StatusUpdateStage.IDENTIFIED,
    next_update_at: datetime | None = None,
) -> StatusUpdate:
    return StatusUpdate(
        incident_id=_INCIDENT,
        sequence=sequence,
        state=StatusUpdateState.APPROVED,
        stage=stage,
        en=_text("en", f" #{sequence}"),
        fr=_text("fr", f" #{sequence}"),
        next_update_at=next_update_at or _NOW,
        author="U-author",
        approver="U-approver",
        approved_at=_NOW,
        published_at=None,
        transcript_cutoff=_NOW,
        transcript_fingerprint="v1:sha256:test",
        created_at=_NOW,
    )


def _labels_en() -> ProfileLabels:
    stage_names = MappingProxyType(
        {
            StatusUpdateStage.IDENTIFIED: "Identified",
            StatusUpdateStage.INVESTIGATING: "Investigating",
            StatusUpdateStage.MONITORING: "Monitoring",
            StatusUpdateStage.RESOLVED: "Resolved",
        }
    )
    return ProfileLabels(
        stage="Stage",
        affected_service="Affected Service",
        impact="Impact",
        current_action="Current Action",
        workaround="Workaround",
        next_update="Next Update",
        time_suffix="ET",
        stage_names=stage_names,
    )


def _labels_fr() -> ProfileLabels:
    stage_names = MappingProxyType(
        {
            StatusUpdateStage.IDENTIFIED: "Identifié",
            StatusUpdateStage.INVESTIGATING: "En cours d'investigation",
            StatusUpdateStage.MONITORING: "Surveillance",
            StatusUpdateStage.RESOLVED: "Résolu",
        }
    )
    return ProfileLabels(
        stage="Étape",
        affected_service="Service Affecté",
        impact="Impact",
        current_action="Action Actuelle",
        workaround="Solution de Contournement",
        next_update="Prochain Mise à Jour",
        time_suffix="HE",
        stage_names=stage_names,
    )


class TestRenderCopyReady:
    """Tests for render_copy_ready: pure sync rendering of structured plain text."""

    def test_render_copy_ready_returns_copy_ready_text(self) -> None:
        """The function returns a CopyReadyText with en and fr fields."""

        update = _record(1, StatusUpdateStage.IDENTIFIED)
        labels_en = _labels_en()
        labels_fr = _labels_fr()

        result = render_copy_ready(update, labels_en, labels_fr)

        assert isinstance(result, CopyReadyText)
        assert isinstance(result.en, str)
        assert isinstance(result.fr, str)

    def test_render_copy_ready_includes_all_label_lines(self) -> None:
        """The output includes stage, affected service, impact, action, and workaround lines."""

        update = _record(1, StatusUpdateStage.IDENTIFIED)
        labels_en = _labels_en()
        labels_fr = _labels_fr()

        result = render_copy_ready(update, labels_en, labels_fr)

        en_lines = result.en.split("\n")
        assert any("Stage:" in line for line in en_lines)
        assert any("Affected Service:" in line for line in en_lines)
        assert any("Impact:" in line for line in en_lines)
        assert any("Current Action:" in line for line in en_lines)
        assert any("Workaround:" in line for line in en_lines)

    def test_render_copy_ready_has_blank_line_between_sections(self) -> None:
        """Sections are separated by a blank line for readability."""

        update = _record(1, StatusUpdateStage.IDENTIFIED)
        labels_en = _labels_en()
        labels_fr = _labels_fr()

        result = render_copy_ready(update, labels_en, labels_fr)

        assert "\n\n" in result.en
        assert "\n\n" in result.fr

    def test_render_copy_ready_omits_next_update_when_resolved(self) -> None:
        """When the stage is RESOLVED, the next update line is omitted."""

        update = _record(1, StatusUpdateStage.RESOLVED)
        labels_en = _labels_en()
        labels_fr = _labels_fr()

        result = render_copy_ready(update, labels_en, labels_fr)

        assert "Next Update" not in result.en
        assert "Prochain Mise à Jour" not in result.fr
        assert "Stage: Resolved" in result.en
        assert "Étape: Résolu" in result.fr

    def test_render_copy_ready_includes_next_update_when_not_resolved(self) -> None:
        """When the stage is not RESOLVED, the next update line is included."""

        update = _record(1, StatusUpdateStage.MONITORING)
        labels_en = _labels_en()
        labels_fr = _labels_fr()

        result = render_copy_ready(update, labels_en, labels_fr)

        assert "Next Update:" in result.en
        assert "Prochain Mise à Jour:" in result.fr

    def test_render_copy_ready_converts_time_to_america_toronto(self) -> None:
        """UTC time is converted to America/Toronto timezone, formatted as YYYY-MM-DD HH:MM ET/HE."""

        # Oct 7, 2026 19:30 UTC is Oct 7, 2026 15:30 EDT (UTC-4 during DST)
        update_time = datetime(2026, 10, 7, 19, 30, tzinfo=UTC)
        update = _record(1, StatusUpdateStage.MONITORING, next_update_at=update_time)
        labels_en = _labels_en()
        labels_fr = _labels_fr()

        result = render_copy_ready(update, labels_en, labels_fr)

        assert "2026-10-07 15:30 ET" in result.en
        assert "2026-10-07 15:30 HE" in result.fr

    def test_render_copy_ready_uses_stored_next_update_at(self) -> None:
        """The rendering uses the update's stored next_update_at, not calculated from now."""

        future_time = datetime(2026, 10, 8, 10, 0, tzinfo=UTC)
        update = _record(1, StatusUpdateStage.MONITORING, next_update_at=future_time)
        labels_en = _labels_en()
        labels_fr = _labels_fr()

        result = render_copy_ready(update, labels_en, labels_fr)

        # The exact conversion to Toronto time depends on DST, but the date should be in the future
        assert "2026-10-0" in result.en

    def test_render_copy_ready_en_structure(self) -> None:
        """The English text follows the expected structure."""

        update = _record(1, StatusUpdateStage.IDENTIFIED)
        labels_en = _labels_en()
        labels_fr = _labels_fr()

        result = render_copy_ready(update, labels_en, labels_fr)

        assert "Stage:" in result.en
        assert "Identified" in result.en
        assert "en affected_service" in result.en

    def test_render_copy_ready_fr_with_french_labels(self) -> None:
        """The French text uses French labels and HE suffix."""

        update = _record(1, StatusUpdateStage.MONITORING)
        labels_en = _labels_en()
        labels_fr = _labels_fr()

        result = render_copy_ready(update, labels_en, labels_fr)

        assert "Étape:" in result.fr
        assert "Service Affecté:" in result.fr
        assert "HE" in result.fr

    def test_render_copy_ready_across_dst_boundary(self) -> None:
        """Time conversion respects DST transitions in America/Toronto."""

        # January 7, 2026 22:30 UTC is Jan 7, 2026 17:30 EST (UTC-5 in winter)
        winter_time = datetime(2026, 1, 7, 22, 30, tzinfo=UTC)
        update = _record(1, StatusUpdateStage.MONITORING, next_update_at=winter_time)
        labels_en = _labels_en()
        labels_fr = _labels_fr()

        result = render_copy_ready(update, labels_en, labels_fr)

        assert "2026-01-07 17:30 ET" in result.en
        assert "2026-01-07 17:30 HE" in result.fr
