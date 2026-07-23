"""Schema contract tests for access request HTTP models."""

import pytest

from packages.access.request.schemas import AccessRequestStatusResponse


@pytest.mark.unit
def test_access_request_status_response_decisions_description_documents_invariant() -> None:
    schema = AccessRequestStatusResponse.model_json_schema()
    decisions_schema = schema["properties"]["decisions"]

    description = decisions_schema.get("description")
    assert description
    description_lower = description.lower()
    assert "cancel" in description_lower
    assert "retry" in description_lower
    assert "empty" in description_lower
