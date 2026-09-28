"""Schema contract tests for access request HTTP models."""

import pytest

from packages.access.request.schemas import AccessRequestStatusResponse, SubmitAccessRequestResponse


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


@pytest.mark.unit
def test_submit_access_request_response_message_is_nullable_and_described() -> None:
    """The submission message may be null on success and says so in the schema.

    OperationResult.message is optional on SUCCESS, so the response mirrors it;
    the public schema field carries a description stating it may be null.
    """
    response = SubmitAccessRequestResponse(request_id="req-1", status="pending", message=None)
    message_schema = SubmitAccessRequestResponse.model_json_schema()["properties"]["message"]

    assert response.message is None
    assert {"type": "null"} in message_schema["anyOf"]
    assert "null" in message_schema["description"].lower()
