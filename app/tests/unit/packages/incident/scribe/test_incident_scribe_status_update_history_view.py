"""Tests for the approved-updates list and the reopened copy-ready view of the status-updates modal.

``format_profile_time`` renders a moment in America/Toronto as
``YYYY-MM-DD HH:MM`` plus the language's zone suffix, and the comms profile's
next-update line uses it unchanged. ``build_overview_view`` shows the pending
draft as the command always has, then an approved-updates header and one row
per approved or published update with an Open button, a localized empty state,
or the first 50 rows and a localized truncation note. ``build_copy_ready_view``
keeps the approval view exactly when no update is given, and for a reopened
update adds a status line above it and a Back button below it.

The view builders are pure and called directly; only the command test stubs
the overview read and records the sent view with a reply fake. The scribe catalogue is not loaded
in unit tests, so wording is the in-code EN or FR fallback, pinned literally.
Assertions navigate blocks by type and block id and decode every button value
from JSON, because those are what Slack renders and the listeners read back.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from contracts.operations import OperationResult
from contracts.slack.models import CommandPayload
from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from packages.incident.scribe.comms_profile import format_profile_time, render_profile, render_profile_sections
from packages.incident.scribe.domain import CopyReadyText, StatusUpdateOverview
from packages.incident.scribe.platforms import slack as platform_slack
from packages.incident.scribe.platforms.slack import (
    DRAFT_ACTION_ID,
    HISTORY_ACTION_ID,
    OPEN_ACTION_ID,
    PUBLISHED_ACTION_ID,
    REVIEW_ACTION_ID,
    WRITE_ACTION_ID,
    build_copy_ready_view,
    build_overview_view,
    build_profile_labels,
    handle_status_update_command,
)
from tests.factories.slack import FakeSlackReply

pytestmark = pytest.mark.unit

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_APPROVER = "U0APPROVER"
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_METADATA = json.dumps({"channel_id": _CHANNEL, "locale": "en-US"})
_FR_METADATA = json.dumps({"channel_id": _CHANNEL, "locale": "fr-FR"})
_COPY = CopyReadyText(en="Stage: Identified\n\nImpact: en impact", fr="Étape : Identified\n\nIncidence : fr impact")
_ROW_CAP = 50


def _text(language: str) -> StatusUpdateText:
    return StatusUpdateText(
        affected_service=f"{language} service",
        impact=f"{language} impact",
        current_action=f"{language} action",
        workaround=f"{language} workaround",
    )


_DRAFT = StatusUpdate(
    incident_id=_INCIDENT,
    sequence=3,
    state=StatusUpdateState.DRAFT,
    stage=StatusUpdateStage.MONITORING,
    en=_text("en"),
    fr=_text("fr"),
    next_update_at=_NOW + timedelta(minutes=30),
    author="U999",
    transcript_cutoff=_NOW,
    transcript_fingerprint="v1:sha256:abc123",
    created_at=_NOW,
)
_APPROVED = replace(
    _DRAFT,
    sequence=2,
    state=StatusUpdateState.APPROVED,
    stage=StatusUpdateStage.IDENTIFIED,
    approver=_APPROVER,
    approved_at=_NOW,
)
_PUBLISHED = replace(
    _DRAFT,
    sequence=1,
    state=StatusUpdateState.PUBLISHED,
    stage=StatusUpdateStage.INVESTIGATING,
    approver="U0FIRST",
    approved_at=datetime(2026, 10, 7, 13, 5, tzinfo=UTC),
    published_at=datetime(2026, 10, 7, 13, 10, tzinfo=UTC),
)


def _approved(sequence: int) -> StatusUpdate:
    return replace(_APPROVED, sequence=sequence, approved_at=_NOW + timedelta(minutes=sequence))


def _decoded(node: Any) -> Any:
    """Deep copy of ``node`` with every button ``value`` decoded from JSON."""
    if isinstance(node, list):
        return [_decoded(item) for item in node]
    if isinstance(node, dict):
        copied = {key: _decoded(value) for key, value in node.items()}
        if node.get("type") == "button" and "value" in node:
            copied["value"] = json.loads(node["value"])
        return copied
    return node


def _blocks(view: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = _decoded(view["blocks"])
    return blocks


def _block(view: dict[str, Any], block_id: str) -> dict[str, Any]:
    (block,) = [block for block in _blocks(view) if block.get("block_id") == block_id]
    return block


def _row_blocks(view: dict[str, Any]) -> list[dict[str, Any]]:
    return [block for block in _blocks(view) if str(block.get("block_id", "")).startswith("approved_update.")]


def _frame(view: dict[str, Any]) -> dict[str, Any]:
    """The view without its blocks: type, title, metadata and buttons of the modal itself."""
    return {key: value for key, value in view.items() if key != "blocks"}


def _row(update: StatusUpdate, text: str, button: str = "Open") -> dict[str, Any]:
    return {
        "type": "section",
        "block_id": f"approved_update.{update.sequence}",
        "text": {"type": "mrkdwn", "text": text},
        "accessory": {
            "type": "button",
            "action_id": OPEN_ACTION_ID,
            "text": {"type": "plain_text", "text": button},
            "value": {"incident_id": _INCIDENT, "sequence": update.sequence},
        },
    }


def _header(text: str = "Approved updates") -> dict[str, Any]:
    return {"type": "header", "block_id": "approved_updates", "text": {"type": "plain_text", "text": text}}


class TestFormatProfileTime:
    @pytest.mark.parametrize(
        ("moment", "expected"),
        [
            (datetime(2026, 10, 7, 15, 0, tzinfo=UTC), "2026-10-07 11:00 ET"),
            (datetime(2026, 1, 15, 15, 0, tzinfo=UTC), "2026-01-15 10:00 ET"),
            (datetime(2026, 3, 8, 6, 59, tzinfo=UTC), "2026-03-08 01:59 ET"),
            (datetime(2026, 3, 8, 7, 0, tzinfo=UTC), "2026-03-08 03:00 ET"),
            (datetime(2026, 10, 7, 17, 0, tzinfo=timezone(timedelta(hours=2))), "2026-10-07 11:00 ET"),
        ],
        ids=["daylight", "standard", "before-dst-start", "at-dst-start", "non-utc-input"],
    )
    def test_english_time_in_toronto_with_et(self, moment: datetime, expected: str) -> None:
        """The moment is shown in Toronto local time, minutes precision, followed by ET."""
        assert format_profile_time(moment, build_profile_labels("en-US")) == expected

    def test_french_time_uses_he(self) -> None:
        """French labels carry the HE suffix after the same Toronto time."""
        assert format_profile_time(_NOW, build_profile_labels("fr-FR")) == "2026-10-07 11:00 HE"

    def test_profile_sections_are_unchanged(self) -> None:
        """The comms profile renders the same lines, its next-update time formatted as above."""
        sections = render_profile_sections(_DRAFT.en, StatusUpdateStage.IDENTIFIED, _NOW, build_profile_labels("en-US"))

        assert sections == (
            "Stage: Identified",
            "Affected service: en service",
            "Impact: en impact",
            "Current action: en action",
            "Workaround: en workaround",
            "Next update: 2026-10-07 11:00 ET",
        )


class TestOverviewPendingPart:
    def test_pending_draft_then_draft_write_and_review_buttons(self) -> None:
        """With a pending draft the view opens with its EN and FR profile and the Draft, Write it myself and Review buttons."""
        view = build_overview_view(StatusUpdateOverview(pending=_DRAFT, approved=(_APPROVED,)), "en-US", _METADATA)

        assert _blocks(view)[:5] == [
            {"type": "header", "text": {"type": "plain_text", "text": "English"}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": render_profile(_DRAFT.en, _DRAFT.stage, _DRAFT.next_update_at, build_profile_labels("en-US")),
                },
            },
            {"type": "header", "text": {"type": "plain_text", "text": "Français"}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": render_profile(_DRAFT.fr, _DRAFT.stage, _DRAFT.next_update_at, build_profile_labels("fr-FR")),
                },
            },
            {
                "type": "actions",
                "block_id": "draft_button",
                "elements": [
                    {
                        "type": "button",
                        "action_id": DRAFT_ACTION_ID,
                        "text": {"type": "plain_text", "text": "Draft"},
                        "style": "primary",
                    },
                    {
                        "type": "button",
                        "action_id": WRITE_ACTION_ID,
                        "text": {"type": "plain_text", "text": "Write it myself"},
                    },
                    {
                        "type": "button",
                        "action_id": REVIEW_ACTION_ID,
                        "text": {"type": "plain_text", "text": "Review"},
                        "value": {"incident_id": _INCIDENT, "sequence": _DRAFT.sequence},
                    },
                ],
            },
        ]

    def test_no_pending_notice_then_draft_and_write_buttons(self) -> None:
        """Without a pending draft the view opens with the no-draft notice, then Draft and Write it myself."""
        view = build_overview_view(StatusUpdateOverview(pending=None, approved=(_APPROVED,)), "en-US", _METADATA)

        assert _blocks(view)[:2] == [
            {"type": "section", "text": {"type": "mrkdwn", "text": "There is no status update draft for this incident yet."}},
            {
                "type": "actions",
                "block_id": "draft_button",
                "elements": [
                    {
                        "type": "button",
                        "action_id": DRAFT_ACTION_ID,
                        "text": {"type": "plain_text", "text": "Draft"},
                        "style": "primary",
                    },
                    {
                        "type": "button",
                        "action_id": WRITE_ACTION_ID,
                        "text": {"type": "plain_text", "text": "Write it myself"},
                    },
                ],
            },
        ]

    def test_modal_frame(self) -> None:
        """The view is the status-updates modal with Close, no submit, and the given metadata verbatim."""
        view = build_overview_view(StatusUpdateOverview(pending=None, approved=()), "en-US", _METADATA)

        assert _frame(view) == {
            "type": "modal",
            "title": {"type": "plain_text", "text": "Status updates"},
            "private_metadata": _METADATA,
            "close": {"type": "plain_text", "text": "Close"},
        }


class TestOverviewApprovedRows:
    def test_section_follows_the_pending_part(self) -> None:
        """After the pending draft's buttons come the approved-updates header and one row per update."""
        view = build_overview_view(StatusUpdateOverview(pending=_DRAFT, approved=(_APPROVED, _PUBLISHED)), "en-US", _METADATA)

        assert [block.get("block_id") for block in _blocks(view)[4:]] == [
            "draft_button",
            "approved_updates",
            "approved_update.2",
            "approved_update.1",
        ]

    def test_header_is_localized(self) -> None:
        """The section header reads Approved updates in English and Mises à jour approuvées in French."""
        overview = StatusUpdateOverview(pending=None, approved=(_APPROVED,))

        assert (
            _block(build_overview_view(overview, "en-US", _METADATA), "approved_updates"),
            _block(build_overview_view(overview, "fr-FR", _FR_METADATA), "approved_updates"),
        ) == (_header(), _header("Mises à jour approuvées"))

    def test_approved_row_in_english(self) -> None:
        """An approved row shows the bold stage, the ET approval time, the approver mention and Not published."""
        view = build_overview_view(StatusUpdateOverview(pending=None, approved=(_APPROVED,)), "en-US", _METADATA)

        assert _row_blocks(view) == [
            _row(_APPROVED, "*Identified* - 2026-10-07 11:00 ET - approved by <@U0APPROVER> - Not published")
        ]

    def test_published_row_in_english(self) -> None:
        """A published row ends with Published and shows its own approval time and approver."""
        view = build_overview_view(StatusUpdateOverview(pending=None, approved=(_PUBLISHED,)), "en-US", _METADATA)

        assert _row_blocks(view) == [
            _row(_PUBLISHED, "*Investigating* - 2026-10-07 09:05 ET - approved by <@U0FIRST> - Published")
        ]

    def test_rows_in_french(self) -> None:
        """French rows use the French stage names, HE, approuvée par, Publiée or Non publiée, and Ouvrir."""
        names = build_profile_labels("fr-FR").stage_names
        view = build_overview_view(StatusUpdateOverview(pending=None, approved=(_APPROVED, _PUBLISHED)), "fr-FR", _FR_METADATA)

        assert _row_blocks(view) == [
            _row(
                _APPROVED,
                f"*{names[StatusUpdateStage.IDENTIFIED]}* - 2026-10-07 11:00 HE - approuvée par <@U0APPROVER> - Non publiée",
                "Ouvrir",
            ),
            _row(
                _PUBLISHED,
                f"*{names[StatusUpdateStage.INVESTIGATING]}* - 2026-10-07 09:05 HE - approuvée par <@U0FIRST> - Publiée",
                "Ouvrir",
            ),
        ]

    def test_missing_approver_segment_is_omitted(self) -> None:
        """A record without an approver shows no approved-by segment."""
        anonymous = replace(_APPROVED, approver=None)
        view = build_overview_view(StatusUpdateOverview(pending=None, approved=(anonymous,)), "en-US", _METADATA)

        assert _row_blocks(view) == [_row(anonymous, "*Identified* - 2026-10-07 11:00 ET - Not published")]

    def test_rows_keep_the_overview_order(self) -> None:
        """Rows follow the overview's newest-first order, each Open button naming its own update."""
        approved = (_approved(7), _approved(5), _approved(4))
        view = build_overview_view(StatusUpdateOverview(pending=None, approved=approved), "en-US", _METADATA)

        assert [block["accessory"]["value"] for block in _row_blocks(view)] == [
            {"incident_id": _INCIDENT, "sequence": 7},
            {"incident_id": _INCIDENT, "sequence": 5},
            {"incident_id": _INCIDENT, "sequence": 4},
        ]


class TestOverviewEmptyState:
    @pytest.mark.parametrize("pending", [_DRAFT, None], ids=["with-draft", "without-draft"])
    def test_english_empty_state_ends_the_view(self, pending: StatusUpdate | None) -> None:
        """With no approved update the header is followed by the empty-state line, draft or not."""
        view = build_overview_view(StatusUpdateOverview(pending=pending, approved=()), "en-US", _METADATA)

        assert _blocks(view)[-2:] == [
            _header(),
            {
                "type": "section",
                "block_id": "approved_updates_empty",
                "text": {"type": "mrkdwn", "text": "No status update has been approved for this incident yet."},
            },
        ]

    def test_french_empty_state(self) -> None:
        """The empty-state line is in French for a French invoker."""
        view = build_overview_view(StatusUpdateOverview(pending=None, approved=()), "fr-FR", _FR_METADATA)

        assert _block(view, "approved_updates_empty") == {
            "type": "section",
            "block_id": "approved_updates_empty",
            "text": {"type": "mrkdwn", "text": "Aucune mise à jour de statut n'a encore été approuvée pour cet incident."},
        }

    def test_no_rows_and_no_truncation_note(self) -> None:
        """An empty list has neither rows nor the truncation note."""
        view = build_overview_view(StatusUpdateOverview(pending=None, approved=()), "en-US", _METADATA)

        assert [block.get("block_id") for block in _blocks(view)[2:]] == ["approved_updates", "approved_updates_empty"]


class TestOverviewCap:
    @staticmethod
    def _overview(count: int) -> StatusUpdateOverview:
        return StatusUpdateOverview(pending=_DRAFT, approved=tuple(_approved(sequence) for sequence in range(count, 0, -1)))

    def test_fifty_rows_show_without_a_note(self) -> None:
        """Exactly 50 approved updates show as 50 rows and no truncation note."""
        view = build_overview_view(self._overview(_ROW_CAP), "en-US", _METADATA)

        assert len(_row_blocks(view)) == _ROW_CAP
        assert [block for block in _blocks(view) if block.get("block_id") == "approved_updates_truncated"] == []

    def test_more_than_fifty_shows_the_newest_fifty(self) -> None:
        """With 51 approved updates the rows are the newest 50, newest first."""
        view = build_overview_view(self._overview(_ROW_CAP + 1), "en-US", _METADATA)

        assert [block["block_id"] for block in _row_blocks(view)] == [
            f"approved_update.{sequence}" for sequence in range(_ROW_CAP + 1, 1, -1)
        ]

    def test_truncation_note_ends_the_view_in_english(self) -> None:
        """The last block is a context note saying only the latest 50 are shown."""
        view = build_overview_view(self._overview(_ROW_CAP + 1), "en-US", _METADATA)

        assert _blocks(view)[-1] == {
            "type": "context",
            "block_id": "approved_updates_truncated",
            "elements": [{"type": "mrkdwn", "text": "Showing the latest 50 approved updates."}],
        }

    def test_truncation_note_in_french(self) -> None:
        """The truncation note is in French for a French invoker."""
        view = build_overview_view(self._overview(_ROW_CAP + 1), "fr-FR", _FR_METADATA)

        assert _block(view, "approved_updates_truncated") == {
            "type": "context",
            "block_id": "approved_updates_truncated",
            "elements": [{"type": "mrkdwn", "text": "Affichage des 50 dernières mises à jour approuvées."}],
        }

    def test_view_stays_within_slack_block_limit(self) -> None:
        """However many updates exist, the modal keeps to Slack's 100-block limit with 50 rows."""
        view = build_overview_view(self._overview(150), "en-US", _METADATA)

        assert len(_row_blocks(view)) == _ROW_CAP
        assert len(view["blocks"]) <= 100


class TestCommandShowsOverview:
    def test_command_view_is_the_overview_view(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The status-update command reads the channel's overview and updates its modal to the overview view.

        The overview read is stubbed in the platform module's namespace; the
        reply fake records the view the command sent.
        """
        overview = StatusUpdateOverview(pending=_DRAFT, approved=(_APPROVED, _PUBLISHED))
        reads: list[str] = []

        def read_overview(conversation_id: str) -> OperationResult[StatusUpdateOverview]:
            reads.append(conversation_id)
            return OperationResult.success(data=overview)

        monkeypatch.setattr(platform_slack, "get_status_update_overview", read_overview)
        reply = FakeSlackReply()
        payload = CommandPayload(
            text="", user_id="U9", channel_id=_CHANNEL, user_locale="en-US", platform_metadata={"trigger_id": "T1"}
        )

        handle_status_update_command(payload, {}, reply)

        assert reads == [_CHANNEL]
        assert [call["view"] for call in reply.calls_to("update_view")] == [build_overview_view(overview, "en-US", _METADATA)]


class TestCopyReadyViewWithoutUpdate:
    @pytest.mark.parametrize(
        ("locale", "metadata", "note", "title", "close"),
        [
            (
                "en-US",
                _METADATA,
                "Approved. Proofread, then copy into your product's channel. Nothing was posted.",
                "Status updates",
                "Close",
            ),
            (
                "fr-FR",
                _FR_METADATA,
                "Approuvé. Relisez, puis copiez dans le canal de votre produit. Rien n'a été publié.",
                "Mises à jour de statut",
                "Fermer",
            ),
        ],
    )
    def test_is_the_approval_view_unchanged(self, locale: str, metadata: str, note: str, title: str, close: str) -> None:
        """Without an update the view is exactly the approval view: note, EN and FR text, Close only."""
        view = build_copy_ready_view(_COPY, locale, metadata)

        assert view == {
            "type": "modal",
            "title": {"type": "plain_text", "text": title},
            "private_metadata": metadata,
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": note}},
                {"type": "header", "text": {"type": "plain_text", "text": "English"}},
                {
                    "type": "rich_text",
                    "elements": [{"type": "rich_text_preformatted", "elements": [{"type": "text", "text": _COPY.en}]}],
                },
                {"type": "header", "text": {"type": "plain_text", "text": "Français"}},
                {
                    "type": "rich_text",
                    "elements": [{"type": "rich_text_preformatted", "elements": [{"type": "text", "text": _COPY.fr}]}],
                },
            ],
            "close": {"type": "plain_text", "text": close},
        }

    def test_explicit_none_is_the_approval_view(self) -> None:
        """Passing no update explicitly gives the same view as omitting it."""
        assert build_copy_ready_view(_COPY, "en-US", _METADATA, update=None) == build_copy_ready_view(_COPY, "en-US", _METADATA)


class TestCopyReadyViewWithUpdate:
    def test_approval_view_sits_between_status_and_back(self) -> None:
        """The approval view's blocks appear unchanged between the status line and the Back button."""
        view = build_copy_ready_view(_COPY, "en-US", _METADATA, update=_APPROVED)

        assert view["blocks"][1:-1] == build_copy_ready_view(_COPY, "en-US", _METADATA)["blocks"]

    def test_modal_frame_is_unchanged(self) -> None:
        """Title, metadata and Close match the approval view, with no submit."""
        view = build_copy_ready_view(_COPY, "en-US", _METADATA, update=_APPROVED)

        assert _frame(view) == _frame(build_copy_ready_view(_COPY, "en-US", _METADATA))

    def test_status_line_for_an_approved_update(self) -> None:
        """The first block names the stage, the ET approval time, the approver and Not published, beside the toggle."""
        view = build_copy_ready_view(_COPY, "en-US", _METADATA, update=_APPROVED)

        assert _blocks(view)[0] == {
            "type": "section",
            "block_id": "approved_status",
            "text": {
                "type": "mrkdwn",
                "text": "*Identified* - 2026-10-07 11:00 ET - approved by <@U0APPROVER> - Not published",
            },
            "accessory": {
                "type": "button",
                "action_id": PUBLISHED_ACTION_ID,
                "text": {"type": "plain_text", "text": "Mark as published"},
                "value": {"incident_id": _INCIDENT, "sequence": 2, "published": True},
            },
        }

    def test_status_line_for_a_published_update(self) -> None:
        """A published update's status line ends with Published."""
        view = build_copy_ready_view(_COPY, "en-US", _METADATA, update=_PUBLISHED)

        assert _block(view, "approved_status")["text"] == {
            "type": "mrkdwn",
            "text": "*Investigating* - 2026-10-07 09:05 ET - approved by <@U0FIRST> - Published",
        }

    def test_status_line_in_french(self) -> None:
        """The French status line uses HE and the French wording."""
        names = build_profile_labels("fr-FR").stage_names
        view = build_copy_ready_view(_COPY, "fr-FR", _FR_METADATA, update=_APPROVED)

        assert _block(view, "approved_status")["text"] == {
            "type": "mrkdwn",
            "text": f"*{names[StatusUpdateStage.IDENTIFIED]}* - 2026-10-07 11:00 HE - approuvée par <@U0APPROVER> - Non publiée",
        }

    def test_back_button_returns_to_the_list(self) -> None:
        """The last block is the Back button, valued with the channel id from the metadata."""
        view = build_copy_ready_view(_COPY, "en-US", _METADATA, update=_APPROVED)

        assert _blocks(view)[-1] == {
            "type": "actions",
            "block_id": "history_button",
            "elements": [
                {
                    "type": "button",
                    "action_id": HISTORY_ACTION_ID,
                    "text": {"type": "plain_text", "text": "Back"},
                    "value": {"channel_id": _CHANNEL},
                }
            ],
        }

    def test_back_button_in_french(self) -> None:
        """The Back button reads Retour for a French invoker."""
        view = build_copy_ready_view(_COPY, "fr-FR", _FR_METADATA, update=_APPROVED)

        assert _block(view, "history_button")["elements"][0]["text"] == {"type": "plain_text", "text": "Retour"}


def test_action_ids_carry_the_plugin_prefix() -> None:
    """The Open and Back action ids are the scribe's stable, plugin-prefixed ids."""
    assert (OPEN_ACTION_ID, HISTORY_ACTION_ID) == (
        "incident.scribe.status_update.open",
        "incident.scribe.status_update.history",
    )
