"""Tests for the platform-agnostic incident_draft service."""

from __future__ import annotations

import json

import pytest

from infrastructure.operations import OperationResult, OperationStatus
from packages.incident_draft.domain import (
    AI_AUTHOR,
    DocumentSection,
    DraftWriteResult,
    SectionDraft,
    TranscriptMessage,
)
from packages.incident_draft.service import (
    CREATE_FAILED_CODE,
    DOCUMENT_UNREADABLE_CODE,
    DRAFT_UNPARSEABLE_CODE,
    EMPTY_HISTORY_CODE,
    NO_ANSWERS_CODE,
    _parse_answers,
    draft_incident_document,
)

pytestmark = pytest.mark.unit

_MESSAGES = [
    TranscriptMessage(author="Ada", text="prod is down, 500s on checkout"),
    TranscriptMessage(author="Bob", text="rolled back the deploy, recovering"),
]


class _StubSummarizer:
    """Minimal ``Summarizer`` stub capturing what it receives."""

    def __init__(self, result: OperationResult[str]) -> None:
        self._result = result
        self.received_payload: str | None = None
        self.received_instructions: str | None = None
        self.received_max_output_tokens: int | None = None
        self.calls = 0

    async def summarize(
        self,
        transcript: str,
        *,
        instructions: str | None = None,
        max_output_tokens: int | None = None,
    ) -> OperationResult[str]:
        self.calls += 1
        self.received_payload = transcript
        self.received_instructions = instructions
        self.received_max_output_tokens = max_output_tokens
        return self._result


class _StubDocumentPort:
    """Minimal ``IncidentDocumentPort`` stub capturing the drafted sections."""

    def __init__(
        self,
        sections: list[DocumentSection],
        new_document_id: str | None = "NEW1",
        created: bool = True,
    ) -> None:
        self._sections = sections
        self._new_document_id = new_document_id
        self._created = created
        self.created_from: str | None = None
        self.created_drafts: list[SectionDraft] | None = None
        self.written_fields: list = []
        self.written_links: dict = {}

    def read_sections(self, document_id: str) -> list[DocumentSection]:
        return self._sections

    def write_draft_document(self, source_document_id: str, drafts, fields=(), links=None) -> DraftWriteResult | None:
        self.created_from = source_document_id
        self.created_drafts = list(drafts)
        self.written_fields = list(fields)
        self.written_links = dict(links or {})
        if self._new_document_id is None:
            return None
        return DraftWriteResult(document_id=self._new_document_id, created=self._created)


def _sections() -> list[DocumentSection]:
    return [
        DocumentSection(heading="Trigger", instructions="Describe what caused the incident to begin.\n"),
        DocumentSection(heading="Impact", instructions="Describe who and what was affected.\n"),
        DocumentSection(heading="Detection", instructions="How was it detected?\n"),
    ]


class TestDraftIncidentDocument:
    @pytest.mark.asyncio
    async def test_unreadable_document_short_circuits(self):
        documents = _StubDocumentPort(sections=[])
        summarizer = _StubSummarizer(OperationResult.success(data="unused"))

        result = await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == DOCUMENT_UNREADABLE_CODE
        assert summarizer.calls == 0

    @pytest.mark.asyncio
    async def test_empty_history_returns_permanent_error_without_calling_summarizer(self):
        documents = _StubDocumentPort(sections=_sections())
        summarizer = _StubSummarizer(OperationResult.success(data="unused"))

        result = await draft_incident_document("D1", [], documents=documents, summarizer=summarizer)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == EMPTY_HISTORY_CODE
        assert summarizer.calls == 0

    @pytest.mark.asyncio
    async def test_prompt_carries_each_headings_instructions_and_the_transcript(self):
        documents = _StubDocumentPort(sections=_sections())
        summarizer = _StubSummarizer(OperationResult.success(data='{"Trigger": "A bad deploy."}'))

        await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        payload = summarizer.received_payload or ""
        assert "### Trigger" in payload
        assert "Instructions: Describe what caused the incident to begin." in payload
        assert "Ada: prod is down, 500s on checkout" in payload
        assert "Bob: rolled back the deploy, recovering" in payload

    @pytest.mark.asyncio
    async def test_success_creates_new_document_and_reports_headings(self):
        answers = {
            "Trigger": "A bad deploy caused 500s on checkout.",
            "Impact": "Checkout was unavailable to users.",
            "Detection": "",
        }
        documents = _StubDocumentPort(sections=_sections())
        summarizer = _StubSummarizer(OperationResult.success(data=json.dumps(answers)))

        result = await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert result.is_success
        assert result.data.document_id == "NEW1"
        assert result.data.drafted_headings == ("Trigger", "Impact")
        assert result.data.unanswered_headings == ("Detection",)
        assert documents.created_from == "D1"

    @pytest.mark.asyncio
    async def test_unanswered_section_keeps_the_templates_instructions(self):
        documents = _StubDocumentPort(sections=_sections())
        summarizer = _StubSummarizer(OperationResult.success(data='{"Trigger": "A bad deploy."}'))

        await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        drafts = documents.created_drafts or []
        assert drafts[0] == SectionDraft(heading="Trigger", content="A bad deploy.", is_drafted=True)
        # Every section survives into the draft, in document order.
        assert [d.heading for d in drafts] == ["Trigger", "Impact", "Detection"]
        assert drafts[1] == SectionDraft(
            heading="Impact",
            content="Describe who and what was affected.",
            is_drafted=False,
        )

    @pytest.mark.asyncio
    async def test_requests_a_larger_completion_budget_than_the_vendor_default(self):
        """Drafting emits JSON for every section; the 800-token default truncates it."""
        documents = _StubDocumentPort(sections=_sections())
        summarizer = _StubSummarizer(OperationResult.success(data='{"Trigger": "A bad deploy."}'))

        await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert summarizer.received_max_output_tokens == 8000

    @pytest.mark.asyncio
    async def test_json_wrapped_in_prose_is_parsed(self):
        wrapped = 'Sure! Here is the draft:\n{"Trigger": "A bad deploy."}\nLet me know if you need changes.'
        documents = _StubDocumentPort(sections=_sections())
        summarizer = _StubSummarizer(OperationResult.success(data=wrapped))

        result = await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert result.is_success
        assert result.data.drafted_headings == ("Trigger",)

    @pytest.mark.asyncio
    async def test_truncated_response_still_produces_a_partial_draft(self):
        """Every run writes a fresh document, so a fragment costs nothing."""
        truncated = '{"Trigger": "A bad deploy caused 500s.", "Impact": "Checkout was down.", "Lessons Learned": "The team lea'
        documents = _StubDocumentPort(sections=_sections())
        summarizer = _StubSummarizer(OperationResult.success(data=truncated))

        result = await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert result.is_success
        assert result.data.partial is True
        assert result.data.drafted_headings == ("Trigger", "Impact")
        assert documents.created_drafts is not None

    @pytest.mark.asyncio
    async def test_empty_model_response_returns_unparseable(self):
        documents = _StubDocumentPort(sections=_sections())
        summarizer = _StubSummarizer(OperationResult.success(data=""))

        result = await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert result.error_code == DRAFT_UNPARSEABLE_CODE
        assert documents.created_drafts is None

    def test_salvage_still_recovers_escaped_characters(self):
        """Salvage feeds the truncation diagnostics, so it must stay correct."""
        truncated = '{"Trigger": "A \\"bad\\" deploy.\\nRolled back.", "Impact": "Checkout'

        answers, was_truncated = _parse_answers(truncated)

        assert was_truncated is True
        assert answers == {"Trigger": 'A "bad" deploy.\nRolled back.'}

    @pytest.mark.asyncio
    async def test_code_fenced_json_is_parsed(self):
        fenced = '```json\n{"Trigger": "A bad deploy."}\n```'
        documents = _StubDocumentPort(sections=_sections())
        summarizer = _StubSummarizer(OperationResult.success(data=fenced))

        result = await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert result.is_success
        assert result.data.drafted_headings == ("Trigger",)

    @pytest.mark.asyncio
    async def test_unparseable_model_output_returns_error_without_creating(self):
        documents = _StubDocumentPort(sections=_sections())
        summarizer = _StubSummarizer(OperationResult.success(data="not json at all"))

        result = await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == DRAFT_UNPARSEABLE_CODE
        assert documents.created_drafts is None

    @pytest.mark.asyncio
    async def test_all_blank_answers_return_no_answers_without_creating(self):
        documents = _StubDocumentPort(sections=_sections())
        summarizer = _StubSummarizer(OperationResult.success(data='{"Trigger": "", "Impact": "  "}'))

        result = await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == NO_ANSWERS_CODE
        assert documents.created_drafts is None

    @pytest.mark.asyncio
    async def test_summarizer_error_propagates_status_and_code(self):
        documents = _StubDocumentPort(sections=_sections())
        summarizer = _StubSummarizer(OperationResult.transient_error(message="boom", error_code="SERVER_ERROR"))

        result = await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "SERVER_ERROR"
        assert documents.created_drafts is None

    @pytest.mark.asyncio
    async def test_create_failure_returns_transient_error(self):
        documents = _StubDocumentPort(sections=_sections(), new_document_id=None)
        summarizer = _StubSummarizer(OperationResult.success(data='{"Trigger": "A bad deploy."}'))

        result = await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == CREATE_FAILED_CODE


class TestListHeadingDetection:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "heading",
        ["Action Items", "action items", "Follow-up Tasks", "Next Steps", "Detailed Timeline"],
    )
    async def test_list_headings_are_marked_for_bulleting(self, heading):
        documents = _StubDocumentPort(sections=[DocumentSection(heading=heading, instructions="x\n")])
        summarizer = _StubSummarizer(OperationResult.success(data=json.dumps({heading: "- do the thing"})))

        await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert (documents.created_drafts or [])[0].as_list is True

    @pytest.mark.asyncio
    async def test_prose_headings_are_not_marked(self):
        documents = _StubDocumentPort(sections=[DocumentSection(heading="Trigger", instructions="x\n")])
        summarizer = _StubSummarizer(OperationResult.success(data='{"Trigger": "A bad deploy."}'))

        await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert (documents.created_drafts or [])[0].as_list is False


class TestHeadingMatching:
    """Model keys rarely echo headings byte-for-byte; blanks must not follow."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "model_key",
        ["Summary", "summary", "Summary:", "1. Summary", "SUMMARY", " Summary "],
    )
    async def test_key_drift_still_matches_the_heading(self, model_key):
        documents = _StubDocumentPort(sections=[DocumentSection(heading="Summary", instructions="")])
        summarizer = _StubSummarizer(OperationResult.success(data=json.dumps({model_key: "Checkout was down."})))

        result = await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert result.is_success, f"{model_key!r} should have matched the Summary heading"
        assert result.data.drafted_headings == ("Summary",)
        assert (documents.created_drafts or [])[0].content == "Checkout was down."

    @pytest.mark.asyncio
    async def test_numbered_document_heading_matches_plain_model_key(self):
        documents = _StubDocumentPort(sections=[DocumentSection(heading="5. Detection", instructions="")])
        summarizer = _StubSummarizer(OperationResult.success(data='{"Detection": "A bad deploy."}'))

        result = await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert result.data.drafted_headings == ("5. Detection",)

    @pytest.mark.asyncio
    async def test_genuinely_absent_section_stays_unanswered(self):
        documents = _StubDocumentPort(
            sections=[
                DocumentSection(heading="Summary", instructions=""),
                DocumentSection(heading="Detection", instructions=""),
            ]
        )
        summarizer = _StubSummarizer(OperationResult.success(data='{"Summary": "Checkout was down."}'))

        result = await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert result.data.drafted_headings == ("Summary",)
        assert result.data.unanswered_headings == ("Detection",)


class TestTruncationNeverDestroysContent:
    """A degraded run must leave existing content alone."""

    @pytest.mark.asyncio
    async def test_complete_response_still_writes_normally(self):
        documents = _StubDocumentPort(sections=_sections())
        answers = {"Trigger": "A bad deploy.", "Impact": "Checkout was down.", "Lessons Learned": "Add a canary."}
        summarizer = _StubSummarizer(OperationResult.success(data=json.dumps(answers)))

        result = await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert result.is_success
        assert documents.created_drafts is not None

    @pytest.mark.asyncio
    def test_clean_json_is_not_flagged_as_truncated(self):
        answers, was_truncated = _parse_answers('{"Trigger": "A bad deploy."}')

        assert was_truncated is False
        assert answers == {"Trigger": "A bad deploy."}

    def test_prose_wrapped_json_is_not_flagged_as_truncated(self):
        answers, was_truncated = _parse_answers('Here you go:\n{"Trigger": "A bad deploy."}\nHope that helps.')

        assert was_truncated is False
        assert answers == {"Trigger": "A bad deploy."}


class TestMetadataFieldInference:
    """Times come from the model; authors are derived; the rest is left alone."""

    @staticmethod
    def _sections():
        return [DocumentSection(heading="Summary", instructions="")]

    @pytest.mark.asyncio
    async def test_time_fields_are_taken_from_the_model(self):
        answers = {
            "Summary": "Checkout was down.",
            "Detection time": "2026-08-17 10:46",
            "Start-of-impact time": "2026-08-17 10:30",
            "End-of-impact time": "",
        }
        documents = _StubDocumentPort(sections=self._sections())
        summarizer = _StubSummarizer(OperationResult.success(data=json.dumps(answers)))

        await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        written = {f.label: f.value for f in documents.written_fields}
        assert written["Detection time"] == "2026-08-17 10:46"
        assert written["Start-of-impact time"] == "2026-08-17 10:30"
        # An unevidenced time is omitted rather than guessed.
        assert "End-of-impact time" not in written

    @pytest.mark.asyncio
    async def test_the_author_is_the_bot_not_the_responders(self):
        """Responders spoke in the channel; they did not author this draft."""
        documents = _StubDocumentPort(sections=self._sections())
        summarizer = _StubSummarizer(OperationResult.success(data='{"Summary": "Checkout was down."}'))
        messages = [
            TranscriptMessage(author="Sylvia", text="report failing"),
            TranscriptMessage(author="Pat", text="failing query"),
        ]

        await draft_incident_document("D1", messages, documents=documents, summarizer=summarizer)

        written = {f.label: f.value for f in documents.written_fields}
        assert written["Author(s)"] == "SRE Bot (AI generated)"
        assert "Sylvia" not in written["Author(s)"]

    @pytest.mark.asyncio
    async def test_on_call_and_facilitators_are_filled_when_evidenced(self):
        answers = {"Summary": "x", "On-call": "Sylvia", "Facilitators": "Pat"}
        documents = _StubDocumentPort(sections=self._sections())
        summarizer = _StubSummarizer(OperationResult.success(data=json.dumps(answers)))

        await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        written = {f.label: f.value for f in documents.written_fields}
        assert written["On-call"] == "Sylvia"
        assert written["Facilitators"] == "Pat"

    @pytest.mark.asyncio
    async def test_unevidenced_fields_are_left_blank_rather_than_guessed(self):
        answers = {"Summary": "x", "On-call": "", "Facilitators": "   ", "Detection time": ""}
        documents = _StubDocumentPort(sections=self._sections())
        summarizer = _StubSummarizer(OperationResult.success(data=json.dumps(answers)))

        await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        labels = {f.label for f in documents.written_fields}
        assert "On-call" not in labels
        assert "Facilitators" not in labels
        assert "Detection time" not in labels

    @pytest.mark.asyncio
    async def test_metadata_labels_are_offered_to_the_model(self):
        documents = _StubDocumentPort(sections=self._sections())
        summarizer = _StubSummarizer(OperationResult.success(data='{"Summary": "x"}'))

        await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        payload = summarizer.received_payload or ""
        assert "Metadata fields:" in payload
        assert "- Detection time" in payload


class TestPullRequestLinks:
    """PR numbers in prose are matched back to the URLs posted in the channel."""

    @staticmethod
    def _sections():
        return [DocumentSection(heading="Summary", instructions="")]

    async def _run(self, messages):
        documents = _StubDocumentPort(sections=self._sections())
        summarizer = _StubSummarizer(OperationResult.success(data='{"Summary": "PR 1899 fixed it."}'))
        await draft_incident_document("D1", messages, documents=documents, summarizer=summarizer)
        return documents

    @pytest.mark.asyncio
    async def test_links_are_harvested_from_the_transcript(self):
        messages = [
            TranscriptMessage(author="Sylvia", text="PR https://github.com/cds-snc/sre-bot/pull/1899 should fix it"),
            TranscriptMessage(author="Guillaume", text="opened https://github.com/cds-snc/sre-bot/pull/1898"),
        ]

        documents = await self._run(messages)

        assert documents.written_links == {
            "1899": "https://github.com/cds-snc/sre-bot/pull/1899",
            "1898": "https://github.com/cds-snc/sre-bot/pull/1898",
        }

    @pytest.mark.asyncio
    async def test_slack_link_markup_does_not_leak_into_the_url(self):
        messages = [TranscriptMessage(author="Sylvia", text="see <https://github.com/cds-snc/sre-bot/pull/1899|PR 1899>")]

        documents = await self._run(messages)

        assert documents.written_links == {"1899": "https://github.com/cds-snc/sre-bot/pull/1899"}

    @pytest.mark.asyncio
    async def test_no_links_when_the_channel_posted_none(self):
        documents = await self._run([TranscriptMessage(author="Sylvia", text="PR 1899 should fix it")])

        assert documents.written_links == {}


class TestAuthorIsAlwaysTheBot:
    """Author(s) is fixed: it never reflects who spoke, and is never blank."""

    @pytest.mark.asyncio
    async def test_written_even_when_the_model_offers_its_own_author(self):
        answers = {"Summary": "x", "Author(s)": "Sylvia and Pat"}
        documents = _StubDocumentPort(sections=[DocumentSection(heading="Summary", instructions="")])
        summarizer = _StubSummarizer(OperationResult.success(data=json.dumps(answers)))

        await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        written = {f.label: f.value for f in documents.written_fields}
        assert written["Author(s)"] == AI_AUTHOR
        assert "Sylvia" not in written["Author(s)"]

    @pytest.mark.asyncio
    async def test_written_even_when_nothing_else_is_established(self):
        documents = _StubDocumentPort(sections=[DocumentSection(heading="Summary", instructions="")])
        summarizer = _StubSummarizer(OperationResult.success(data='{"Summary": "x"}'))

        await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        written = {f.label: f.value for f in documents.written_fields}
        assert written["Author(s)"] == "SRE Bot (AI generated)"


class TestHumanOnlySections:
    """Five whys and the retrospective are the team's to write, not the bot's."""

    _SKIPPED = (
        "Five whys and Root Cause(s)",
        "Lessons Learned",
        "Root Causes",
        "Retrospective",
    )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("heading", _SKIPPED)
    async def test_the_section_is_never_sent_to_the_model(self, heading):
        documents = _StubDocumentPort(
            sections=[
                DocumentSection(heading="Summary", instructions="Summarize.\n"),
                DocumentSection(heading=heading, instructions="Ask why 5 times.\n"),
            ]
        )
        summarizer = _StubSummarizer(OperationResult.success(data='{"Summary": "Checkout was down."}'))

        await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert heading not in (summarizer.received_payload or "")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("heading", _SKIPPED)
    async def test_nothing_is_written_into_the_section(self, heading):
        documents = _StubDocumentPort(
            sections=[
                DocumentSection(heading="Summary", instructions="Summarize.\n"),
                DocumentSection(heading=heading, instructions="Ask why 5 times.\n"),
            ]
        )
        # Even if the model volunteers content for it, there is no draft to write.
        answers = {"Summary": "Checkout was down.", heading: "Why did it fail?\nBecause X."}
        summarizer = _StubSummarizer(OperationResult.success(data=json.dumps(answers)))

        result = await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        written = {d.heading for d in (documents.created_drafts or [])}
        assert heading not in written
        assert heading not in result.data.drafted_headings
        assert heading not in result.data.unanswered_headings

    @pytest.mark.asyncio
    async def test_other_sections_are_unaffected(self):
        documents = _StubDocumentPort(
            sections=[
                DocumentSection(heading="Summary", instructions="Summarize.\n"),
                DocumentSection(heading="Lessons Learned", instructions="What did we learn?\n"),
            ]
        )
        summarizer = _StubSummarizer(OperationResult.success(data='{"Summary": "Checkout was down."}'))

        result = await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        assert result.data.drafted_headings == ("Summary",)

    @pytest.mark.asyncio
    async def test_the_prompt_no_longer_describes_them(self):
        documents = _StubDocumentPort(sections=[DocumentSection(heading="Summary", instructions="")])
        summarizer = _StubSummarizer(OperationResult.success(data='{"Summary": "x"}'))

        await draft_incident_document("D1", _MESSAGES, documents=documents, summarizer=summarizer)

        instructions = summarizer.received_instructions or ""
        for gone in ("five whys", "What went wrong", "Where we got lucky", "root-cause section"):
            assert gone not in instructions
