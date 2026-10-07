"""Tests for the copy-ready publisher adapter.

The adapter implements the StatusPagePublisher protocol, refusing draft updates
with STATUS_UPDATE_NOT_APPROVED and returning CopyReadyText that equals the
render_copy_ready output, with no side effects on the store.
"""

from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from contracts.operations import OperationStatus
from contracts.operations.codes import ErrorCode
from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from packages.incident.scribe.adapters.copy_ready import CopyReadyPublisher
from packages.incident.scribe.comms_profile import ProfileLabels
from packages.incident.scribe.domain import CopyReadyText
from packages.incident.scribe.ports import StatusPagePublisher
from packages.incident.scribe.providers import get_status_page_publisher
from packages.incident.scribe.publisher import render_copy_ready

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_INCIDENT = "inc-uuid-1"


def _text(language: str, tag: str = "") -> StatusUpdateText:
    fields = ("affected_service", "impact", "current_action", "workaround")
    return StatusUpdateText(**{field: f"{language} {field}{tag}" for field in fields})


def _record(
    sequence: int,
    state: StatusUpdateState = StatusUpdateState.APPROVED,
    stage: StatusUpdateStage = StatusUpdateStage.IDENTIFIED,
) -> StatusUpdate:
    return StatusUpdate(
        incident_id=_INCIDENT,
        sequence=sequence,
        state=state,
        stage=stage,
        en=_text("en", f" #{sequence}"),
        fr=_text("fr", f" #{sequence}"),
        next_update_at=_NOW,
        author="U-author",
        approver="U-approver" if state in (StatusUpdateState.APPROVED, StatusUpdateState.PUBLISHED) else None,
        approved_at=_NOW if state in (StatusUpdateState.APPROVED, StatusUpdateState.PUBLISHED) else None,
        published_at=_NOW if state is StatusUpdateState.PUBLISHED else None,
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


class TestCopyReadyPublisher:
    """Tests for the CopyReadyPublisher adapter implementing StatusPagePublisher."""

    @pytest.mark.asyncio
    async def test_publish_approved_returns_copy_ready_text(self) -> None:
        """Publishing an approved update returns a CopyReadyText result."""

        publisher = CopyReadyPublisher()
        update = _record(1, StatusUpdateState.APPROVED)
        labels_en = _labels_en()
        labels_fr = _labels_fr()

        result = await publisher.publish(update, labels_en=labels_en, labels_fr=labels_fr)

        assert result.is_success
        assert isinstance(result.data, CopyReadyText)
        assert isinstance(result.data.en, str)
        assert isinstance(result.data.fr, str)

    @pytest.mark.asyncio
    async def test_publish_equals_render_copy_ready(self) -> None:
        """The published output equals calling render_copy_ready directly."""

        publisher = CopyReadyPublisher()
        update = _record(1, StatusUpdateState.APPROVED)
        labels_en = _labels_en()
        labels_fr = _labels_fr()

        result = await publisher.publish(update, labels_en=labels_en, labels_fr=labels_fr)
        direct = render_copy_ready(update, labels_en, labels_fr)

        assert result.is_success
        assert result.data == direct

    @pytest.mark.asyncio
    async def test_publish_draft_refused_with_status_update_not_approved(self) -> None:
        """Publishing a draft update is refused with STATUS_UPDATE_NOT_APPROVED."""

        publisher = CopyReadyPublisher()
        update = _record(1, StatusUpdateState.DRAFT)
        labels_en = _labels_en()
        labels_fr = _labels_fr()

        result = await publisher.publish(update, labels_en=labels_en, labels_fr=labels_fr)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == ErrorCode.STATUS_UPDATE_NOT_APPROVED

    @pytest.mark.asyncio
    async def test_publish_no_side_effects(self) -> None:
        """Publishing has no side effects on any external state."""

        publisher = CopyReadyPublisher()
        update = _record(1, StatusUpdateState.APPROVED)
        labels_en = _labels_en()
        labels_fr = _labels_fr()

        result = await publisher.publish(update, labels_en=labels_en, labels_fr=labels_fr)

        assert result.is_success
        # Test idempotency: running again should return the same result
        result2 = await publisher.publish(update, labels_en=labels_en, labels_fr=labels_fr)
        assert result2.is_success
        assert result.data == result2.data

    @pytest.mark.asyncio
    async def test_publish_different_updates_produce_different_output(self) -> None:
        """Different updates produce different copy-ready output."""

        publisher = CopyReadyPublisher()
        update1 = _record(1, StatusUpdateState.APPROVED, stage=StatusUpdateStage.IDENTIFIED)
        update2 = _record(2, StatusUpdateState.APPROVED, stage=StatusUpdateStage.RESOLVED)
        labels_en = _labels_en()
        labels_fr = _labels_fr()

        result1 = await publisher.publish(update1, labels_en=labels_en, labels_fr=labels_fr)
        result2 = await publisher.publish(update2, labels_en=labels_en, labels_fr=labels_fr)

        assert result1.is_success
        assert result2.is_success
        assert result1.data != result2.data
        assert "Next Update:" in result1.data.en
        assert "Next Update:" not in result2.data.en


class TestStatusPagePublisher:
    """Tests for the status page publisher provider."""

    def test_get_status_page_publisher_returns_status_page_publisher(self) -> None:
        """get_status_page_publisher returns an instance of StatusPagePublisher."""

        publisher = get_status_page_publisher()

        assert isinstance(publisher, StatusPagePublisher)
        assert hasattr(publisher, "publish")
        assert callable(publisher.publish)
