"""Tests for rendering incident status updates with the default comms profile.

The profile shows stage, affected service, impact, current action, workaround and
the next update time in America/Toronto as YYYY-MM-DD HH:MM ET (EN) or HE (FR),
and omits the next update line when the stage is resolved.
"""

from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from features.incident.comms.comms_profile import ProfileLabels, render_profile, render_profile_sections
from features.incident.core.api import StatusUpdateStage, StatusUpdateText

pytestmark = pytest.mark.unit


def test_render_profile_shows_all_fields_in_order():
    """A profile contains all fields as lines in order: stage, service, impact, action, workaround, next update."""
    text = StatusUpdateText(
        affected_service="Payment API",
        impact="Users cannot checkout",
        current_action="Rolling back deploy",
        workaround="Try again in 5 minutes",
    )
    stage_names = MappingProxyType(
        {
            StatusUpdateStage.IDENTIFIED: "Identified",
            StatusUpdateStage.INVESTIGATING: "Investigating",
            StatusUpdateStage.MONITORING: "Monitoring",
            StatusUpdateStage.RESOLVED: "Resolved",
        }
    )
    labels = ProfileLabels(
        stage="Stage",
        affected_service="Affected Service",
        impact="Impact",
        current_action="Current Action",
        workaround="Workaround",
        next_update="Next Update",
        time_suffix="ET",
        stage_names=stage_names,
    )
    next_update_at = datetime(2026, 10, 7, 15, 30, tzinfo=UTC)

    profile = render_profile(text, StatusUpdateStage.IDENTIFIED, next_update_at, labels)

    assert "Stage: Identified" in profile
    assert "Affected Service: Payment API" in profile
    assert "Impact: Users cannot checkout" in profile
    assert "Current Action: Rolling back deploy" in profile
    assert "Workaround: Try again in 5 minutes" in profile
    assert "Next Update: 2026-10-07 11:30 ET" in profile


def test_render_profile_omits_next_update_when_stage_is_resolved():
    """When the stage is resolved, the next update line is omitted."""
    text = StatusUpdateText(
        affected_service="Payment API",
        impact="None",
        current_action="Incident resolved",
        workaround="No action needed",
    )
    stage_names = MappingProxyType(
        {
            StatusUpdateStage.IDENTIFIED: "Identified",
            StatusUpdateStage.INVESTIGATING: "Investigating",
            StatusUpdateStage.MONITORING: "Monitoring",
            StatusUpdateStage.RESOLVED: "Resolved",
        }
    )
    labels = ProfileLabels(
        stage="Stage",
        affected_service="Affected Service",
        impact="Impact",
        current_action="Current Action",
        workaround="Workaround",
        next_update="Next Update",
        time_suffix="ET",
        stage_names=stage_names,
    )
    next_update_at = datetime(2026, 10, 7, 15, 30, tzinfo=UTC)

    profile = render_profile(text, StatusUpdateStage.RESOLVED, next_update_at, labels)

    assert "Next Update" not in profile
    assert "Stage: Resolved" in profile


def test_render_profile_converts_time_to_america_toronto_en():
    """UTC time is converted to America/Toronto timezone, formatted as YYYY-MM-DD HH:MM ET."""
    text = StatusUpdateText(
        affected_service="API",
        impact="Degraded",
        current_action="Monitoring",
        workaround="N/A",
    )
    stage_names = MappingProxyType(
        {
            StatusUpdateStage.IDENTIFIED: "Identified",
            StatusUpdateStage.INVESTIGATING: "Investigating",
            StatusUpdateStage.MONITORING: "Monitoring",
            StatusUpdateStage.RESOLVED: "Resolved",
        }
    )
    labels = ProfileLabels(
        stage="Stage",
        affected_service="Affected Service",
        impact="Impact",
        current_action="Current Action",
        workaround="Workaround",
        next_update="Next Update",
        time_suffix="ET",
        stage_names=stage_names,
    )
    # Oct 7, 2026 19:30 UTC is Oct 7, 2026 15:30 EDT (UTC-4 during DST)
    next_update_at = datetime(2026, 10, 7, 19, 30, tzinfo=UTC)

    profile = render_profile(text, StatusUpdateStage.MONITORING, next_update_at, labels)

    assert "2026-10-07 15:30 ET" in profile


def test_render_profile_converts_time_to_america_toronto_across_dst_boundary():
    """Time conversion respects DST transitions in America/Toronto."""
    text = StatusUpdateText(
        affected_service="API",
        impact="Down",
        current_action="Investigating",
        workaround="N/A",
    )
    stage_names = MappingProxyType(
        {
            StatusUpdateStage.IDENTIFIED: "Identified",
            StatusUpdateStage.INVESTIGATING: "Investigating",
            StatusUpdateStage.MONITORING: "Monitoring",
            StatusUpdateStage.RESOLVED: "Resolved",
        }
    )
    labels = ProfileLabels(
        stage="Stage",
        affected_service="Affected Service",
        impact="Impact",
        current_action="Current Action",
        workaround="Workaround",
        next_update="Next Update",
        time_suffix="ET",
        stage_names=stage_names,
    )
    # January 7, 2026 22:30 UTC is Jan 7, 2026 17:30 EST (UTC-5 in winter)
    next_update_at = datetime(2026, 1, 7, 22, 30, tzinfo=UTC)

    profile = render_profile(text, StatusUpdateStage.IDENTIFIED, next_update_at, labels)

    assert "2026-01-07 17:30 ET" in profile


def test_render_profile_with_french_labels_and_he_suffix():
    """French labels and HE (Heure de l'Est) suffix are rendered correctly."""
    text = StatusUpdateText(
        affected_service="API de paiement",
        impact="Utilisateurs ne peuvent pas payer",
        current_action="Déploiement annulé",
        workaround="Réessayez dans 5 minutes",
    )
    stage_names = MappingProxyType(
        {
            StatusUpdateStage.IDENTIFIED: "Identifié",
            StatusUpdateStage.INVESTIGATING: "En cours d'investigation",
            StatusUpdateStage.MONITORING: "Surveillance",
            StatusUpdateStage.RESOLVED: "Résolu",
        }
    )
    labels = ProfileLabels(
        stage="Étape",
        affected_service="Service Affecté",
        impact="Impact",
        current_action="Action Actuelle",
        workaround="Solution de Contournement",
        next_update="Prochain Mise à Jour",
        time_suffix="HE",
        stage_names=stage_names,
    )
    next_update_at = datetime(2026, 10, 7, 19, 30, tzinfo=UTC)

    profile = render_profile(text, StatusUpdateStage.IDENTIFIED, next_update_at, labels)

    assert "Étape: Identifié" in profile
    assert "Service Affecté: API de paiement" in profile
    assert "Prochain Mise à Jour: 2026-10-07 15:30 HE" in profile


def test_render_profile_every_stage():
    """The profile renders correctly for all stages."""
    stages = [
        StatusUpdateStage.IDENTIFIED,
        StatusUpdateStage.INVESTIGATING,
        StatusUpdateStage.MONITORING,
        StatusUpdateStage.RESOLVED,
    ]
    text = StatusUpdateText(
        affected_service="Service",
        impact="Impact",
        current_action="Action",
        workaround="Workaround",
    )
    stage_names = MappingProxyType(
        {
            StatusUpdateStage.IDENTIFIED: "Identified",
            StatusUpdateStage.INVESTIGATING: "Investigating",
            StatusUpdateStage.MONITORING: "Monitoring",
            StatusUpdateStage.RESOLVED: "Resolved",
        }
    )
    labels = ProfileLabels(
        stage="Stage",
        affected_service="Service",
        impact="Impact",
        current_action="Action",
        workaround="Workaround",
        next_update="Next Update",
        time_suffix="ET",
        stage_names=stage_names,
    )
    next_update_at = datetime(2026, 10, 7, 15, 30, tzinfo=UTC)

    for stage in stages:
        profile = render_profile(text, stage, next_update_at, labels)
        assert profile is not None
        assert "Stage:" in profile


def test_render_profile_stage_line_uses_label_from_stage_names():
    """The stage line uses the localized stage name from the ProfileLabels, not from text."""
    text = StatusUpdateText(
        affected_service="API",
        impact="Down",
        current_action="Investigating",
        workaround="N/A",
    )
    stage_names = MappingProxyType(
        {
            StatusUpdateStage.IDENTIFIED: "Problème Identifié",
            StatusUpdateStage.INVESTIGATING: "En cours d'investigation",
            StatusUpdateStage.MONITORING: "Surveillance",
            StatusUpdateStage.RESOLVED: "Résolu",
        }
    )
    labels = ProfileLabels(
        stage="Étape",
        affected_service="Service",
        impact="Impact",
        current_action="Action",
        workaround="Workaround",
        next_update="Next Update",
        time_suffix="HE",
        stage_names=stage_names,
    )
    next_update_at = datetime(2026, 10, 7, 15, 30, tzinfo=UTC)

    profile = render_profile(text, StatusUpdateStage.INVESTIGATING, next_update_at, labels)

    assert "Étape: En cours d'investigation" in profile


class TestRenderProfileSections:
    """Tests for render_profile_sections: returns tuple of profile lines."""

    def test_render_profile_sections_returns_tuple(self):
        """render_profile_sections returns a tuple of strings."""

        text = StatusUpdateText(
            affected_service="API",
            impact="Down",
            current_action="Investigating",
            workaround="N/A",
        )
        stage_names = MappingProxyType(
            {
                StatusUpdateStage.IDENTIFIED: "Identified",
                StatusUpdateStage.INVESTIGATING: "Investigating",
                StatusUpdateStage.MONITORING: "Monitoring",
                StatusUpdateStage.RESOLVED: "Resolved",
            }
        )
        labels = ProfileLabels(
            stage="Stage",
            affected_service="Service",
            impact="Impact",
            current_action="Action",
            workaround="Workaround",
            next_update="Next Update",
            time_suffix="ET",
            stage_names=stage_names,
        )
        next_update_at = datetime(2026, 10, 7, 15, 30, tzinfo=UTC)

        sections = render_profile_sections(text, StatusUpdateStage.IDENTIFIED, next_update_at, labels)

        assert isinstance(sections, tuple)
        assert all(isinstance(s, str) for s in sections)

    def test_render_profile_sections_includes_all_fields(self):
        """render_profile_sections returns a tuple with all fields as lines."""

        text = StatusUpdateText(
            affected_service="API",
            impact="Down",
            current_action="Investigating",
            workaround="N/A",
        )
        stage_names = MappingProxyType(
            {
                StatusUpdateStage.IDENTIFIED: "Identified",
                StatusUpdateStage.INVESTIGATING: "Investigating",
                StatusUpdateStage.MONITORING: "Monitoring",
                StatusUpdateStage.RESOLVED: "Resolved",
            }
        )
        labels = ProfileLabels(
            stage="Stage",
            affected_service="Service",
            impact="Impact",
            current_action="Action",
            workaround="Workaround",
            next_update="Next Update",
            time_suffix="ET",
            stage_names=stage_names,
        )
        next_update_at = datetime(2026, 10, 7, 15, 30, tzinfo=UTC)

        sections = render_profile_sections(text, StatusUpdateStage.IDENTIFIED, next_update_at, labels)

        assert any("Stage:" in s for s in sections)
        assert any("Service:" in s for s in sections)
        assert any("Impact:" in s for s in sections)
        assert any("Action:" in s for s in sections)
        assert any("Workaround:" in s for s in sections)
        assert any("Next Update:" in s for s in sections)

    def test_render_profile_sections_omits_next_update_when_resolved(self):
        """When stage is RESOLVED, render_profile_sections omits the next update line."""

        text = StatusUpdateText(
            affected_service="API",
            impact="None",
            current_action="Resolved",
            workaround="No action needed",
        )
        stage_names = MappingProxyType(
            {
                StatusUpdateStage.IDENTIFIED: "Identified",
                StatusUpdateStage.INVESTIGATING: "Investigating",
                StatusUpdateStage.MONITORING: "Monitoring",
                StatusUpdateStage.RESOLVED: "Resolved",
            }
        )
        labels = ProfileLabels(
            stage="Stage",
            affected_service="Service",
            impact="Impact",
            current_action="Action",
            workaround="Workaround",
            next_update="Next Update",
            time_suffix="ET",
            stage_names=stage_names,
        )
        next_update_at = datetime(2026, 10, 7, 15, 30, tzinfo=UTC)

        sections = render_profile_sections(text, StatusUpdateStage.RESOLVED, next_update_at, labels)

        assert not any("Next Update" in s for s in sections)
        assert any("Stage:" in s and "Resolved" in s for s in sections)

    def test_render_profile_equals_joined_sections(self):
        """render_profile output equals joining render_profile_sections with newlines."""

        text = StatusUpdateText(
            affected_service="Payment API",
            impact="Users cannot checkout",
            current_action="Rolling back deploy",
            workaround="Try again in 5 minutes",
        )
        stage_names = MappingProxyType(
            {
                StatusUpdateStage.IDENTIFIED: "Identified",
                StatusUpdateStage.INVESTIGATING: "Investigating",
                StatusUpdateStage.MONITORING: "Monitoring",
                StatusUpdateStage.RESOLVED: "Resolved",
            }
        )
        labels = ProfileLabels(
            stage="Stage",
            affected_service="Affected Service",
            impact="Impact",
            current_action="Current Action",
            workaround="Workaround",
            next_update="Next Update",
            time_suffix="ET",
            stage_names=stage_names,
        )
        next_update_at = datetime(2026, 10, 7, 15, 30, tzinfo=UTC)

        profile = render_profile(text, StatusUpdateStage.IDENTIFIED, next_update_at, labels)
        sections = render_profile_sections(text, StatusUpdateStage.IDENTIFIED, next_update_at, labels)
        joined = "\n".join(sections)

        assert profile == joined

    def test_render_profile_sections_all_stages(self):
        """render_profile_sections renders correctly for all stages."""

        stages = [
            StatusUpdateStage.IDENTIFIED,
            StatusUpdateStage.INVESTIGATING,
            StatusUpdateStage.MONITORING,
            StatusUpdateStage.RESOLVED,
        ]
        text = StatusUpdateText(
            affected_service="Service",
            impact="Impact",
            current_action="Action",
            workaround="Workaround",
        )
        stage_names = MappingProxyType(
            {
                StatusUpdateStage.IDENTIFIED: "Identified",
                StatusUpdateStage.INVESTIGATING: "Investigating",
                StatusUpdateStage.MONITORING: "Monitoring",
                StatusUpdateStage.RESOLVED: "Resolved",
            }
        )
        labels = ProfileLabels(
            stage="Stage",
            affected_service="Service",
            impact="Impact",
            current_action="Action",
            workaround="Workaround",
            next_update="Next Update",
            time_suffix="ET",
            stage_names=stage_names,
        )
        next_update_at = datetime(2026, 10, 7, 15, 30, tzinfo=UTC)

        for stage in stages:
            sections = render_profile_sections(text, stage, next_update_at, labels)
            assert isinstance(sections, tuple)
            assert len(sections) > 0
