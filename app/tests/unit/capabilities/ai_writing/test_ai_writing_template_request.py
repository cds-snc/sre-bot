"""Tests for the request a template fill sends to the model.

Pure rendering; assertions are on the composed text the writer receives.
"""

import pytest

from capabilities.ai_writing.domain import TemplateField, TemplateSection
from capabilities.ai_writing.service import build_request

pytestmark = pytest.mark.unit


def test_sections_render_with_their_instructions_then_the_source_last() -> None:
    request = build_request(
        "Source:\nline one",
        [TemplateSection("Trigger", "  What began it?\n"), TemplateSection("Impact")],
        [],
    )

    assert request == (
        "Template sections:\n\n### Trigger\nInstructions: What began it?\n\n"
        "### Impact\nInstructions: (no instructions given)\n\nSource:\nline one"
    )


def test_fields_render_between_the_sections_and_the_source() -> None:
    request = build_request(
        "the source",
        [TemplateSection("Trigger", "What began it?")],
        [TemplateField("On-call"), TemplateField("Detection time", " YYYY-MM-DD HH:MM ")],
    )

    assert request.endswith("Metadata fields:\n- On-call\n- Detection time: YYYY-MM-DD HH:MM\n\nthe source")


def test_no_fields_means_no_fields_block() -> None:
    assert "Metadata fields:" not in build_request("the source", [TemplateSection("Trigger")], [])
