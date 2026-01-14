"""Tests for platform-agnostic data models."""

import pytest
from datetime import datetime

from infrastructure.platforms.models import (
    CardAction,
    CardActionStyle,
    CardDefinition,
    CardElementType,
    CardSection,
    CommandPayload,
    CommandResponse,
    HttpEndpointRequest,
    HttpEndpointResponse,
    ViewDefinition,
    ViewField,
    ViewSubmission,
)


class TestCommandPayload:
    """Tests for CommandPayload model."""

    def test_create_with_required_fields(self):
        """Should create payload with required fields only."""
        payload = CommandPayload(
            text="/sre help",
            user_id="U12345",
        )

        assert payload.text == "/sre help"
        assert payload.user_id == "U12345"
        assert payload.user_email is None
        assert payload.channel_id is None
        assert payload.correlation_id != ""  # Auto-generated

    def test_create_with_all_fields(self):
        """Should create payload with all fields."""
        payload = CommandPayload(
            text="/sre groups list",
            user_id="U12345",
            user_email="user@example.com",
            channel_id="C67890",
            response_url="https://hooks.slack.com/...",
            correlation_id="cmd-123",
            platform_metadata={"team_id": "T123"},
        )

        assert payload.text == "/sre groups list"
        assert payload.user_id == "U12345"
        assert payload.user_email == "user@example.com"
        assert payload.channel_id == "C67890"
        assert payload.response_url == "https://hooks.slack.com/..."
        assert payload.correlation_id == "cmd-123"
        assert payload.platform_metadata == {"team_id": "T123"}

    def test_auto_generates_correlation_id(self):
        """Should auto-generate correlation ID if not provided."""
        payload1 = CommandPayload(text="/sre help", user_id="U1")
        payload2 = CommandPayload(text="/sre help", user_id="U2")

        assert payload1.correlation_id != ""
        assert payload2.correlation_id != ""
        assert payload1.correlation_id != payload2.correlation_id


class TestCommandResponse:
    """Tests for CommandResponse model."""

    def test_create_simple_response(self):
        """Should create simple text response."""
        response = CommandResponse(message="Operation successful")

        assert response.message == "Operation successful"
        assert response.ephemeral is False
        assert response.blocks is None
        assert response.attachments is None

    def test_create_ephemeral_response(self):
        """Should create ephemeral response."""
        response = CommandResponse(
            message="Private message",
            ephemeral=True,
        )

        assert response.message == "Private message"
        assert response.ephemeral is True

    def test_create_rich_response(self):
        """Should create response with rich formatting."""
        response = CommandResponse(
            message="Fallback text",
            blocks=[{"type": "section", "text": "Rich content"}],
            attachments=[{"text": "Attachment"}],
        )

        assert response.message == "Fallback text"
        assert response.blocks == [{"type": "section", "text": "Rich content"}]
        assert response.attachments == [{"text": "Attachment"}]


class TestViewModels:
    """Tests for view/modal models."""

    def test_view_field_required(self):
        """Should create required field."""
        field = ViewField(
            field_id="email",
            field_type="text",
            label="Email Address",
            required=True,
        )

        assert field.field_id == "email"
        assert field.field_type == "text"
        assert field.label == "Email Address"
        assert field.required is True

    def test_view_field_with_options(self):
        """Should create select field with options."""
        field = ViewField(
            field_id="role",
            field_type="select",
            label="Role",
            options=[
                {"value": "admin", "label": "Administrator"},
                {"value": "user", "label": "User"},
            ],
        )

        assert field.field_type == "select"
        assert len(field.options) == 2
        assert field.options[0]["value"] == "admin"

    def test_view_definition(self):
        """Should create view definition."""
        view = ViewDefinition(
            view_id="add-member-modal",
            title="Add Member",
            fields=[
                ViewField(field_id="email", field_type="text", label="Email"),
                ViewField(field_id="group", field_type="select", label="Group"),
            ],
            callback_url="/api/v1/groups/add",
        )

        assert view.view_id == "add-member-modal"
        assert view.title == "Add Member"
        assert len(view.fields) == 2
        assert view.callback_url == "/api/v1/groups/add"
        assert view.submit_label == "Submit"  # Default

    def test_view_submission(self):
        """Should create view submission."""
        submission = ViewSubmission(
            view_id="add-member-modal",
            user_id="U12345",
            user_email="user@example.com",
            field_values={
                "email": "newmember@example.com",
                "group": "eng-team",
            },
        )

        assert submission.view_id == "add-member-modal"
        assert submission.user_id == "U12345"
        assert submission.field_values["email"] == "newmember@example.com"


class TestCardModels:
    """Tests for interactive card models."""

    def test_card_action_button(self):
        """Should create button action."""
        action = CardAction(
            action_id="approve",
            action_type=CardElementType.BUTTON,
            label="Approve",
            value="request-123",
            style=CardActionStyle.PRIMARY,
        )

        assert action.action_id == "approve"
        assert action.action_type == CardElementType.BUTTON
        assert action.label == "Approve"
        assert action.value == "request-123"
        assert action.style == CardActionStyle.PRIMARY

    def test_card_action_link(self):
        """Should create link button."""
        action = CardAction(
            action_id="view_docs",
            action_type=CardElementType.BUTTON,
            label="View Documentation",
            url="https://docs.example.com",
        )

        assert action.url == "https://docs.example.com"
        assert action.callback_url is None  # External link

    def test_card_action_with_callback(self):
        """Should create action with callback URL."""
        action = CardAction(
            action_id="reject",
            action_type=CardElementType.BUTTON,
            label="Reject",
            callback_url="/api/v1/requests/reject",
            style=CardActionStyle.DANGER,
        )

        assert action.callback_url == "/api/v1/requests/reject"
        assert action.style == CardActionStyle.DANGER

    def test_card_section_with_actions(self):
        """Should create section with actions."""
        section = CardSection(
            text="Request requires approval",
            actions=[
                CardAction(
                    action_id="approve",
                    action_type=CardElementType.BUTTON,
                    label="Approve",
                ),
                CardAction(
                    action_id="reject",
                    action_type=CardElementType.BUTTON,
                    label="Reject",
                ),
            ],
        )

        assert section.text == "Request requires approval"
        assert section.markdown is True  # Default
        assert len(section.actions) == 2

    def test_card_section_with_fields(self):
        """Should create section with fields."""
        section = CardSection(
            text="Request Details",
            fields=[
                {"key": "Requestor", "value": "user@example.com"},
                {"key": "Group", "value": "eng-team"},
            ],
        )

        assert len(section.fields) == 2
        assert section.fields[0]["key"] == "Requestor"

    def test_card_definition(self):
        """Should create complete card."""
        card = CardDefinition(
            title="Access Request",
            sections=[
                CardSection(
                    text="New access request from user@example.com",
                    fields=[
                        {"key": "Group", "value": "eng-team"},
                        {"key": "Reason", "value": "Need access for project"},
                    ],
                ),
                CardSection(
                    text="Approve or reject this request",
                    actions=[
                        CardAction(
                            action_id="approve",
                            action_type=CardElementType.BUTTON,
                            label="Approve",
                            style=CardActionStyle.PRIMARY,
                        ),
                    ],
                ),
            ],
            footer="Requested on 2026-01-14",
            color="#0078D4",
        )

        assert card.title == "Access Request"
        assert len(card.sections) == 2
        assert card.footer == "Requested on 2026-01-14"
        assert card.color == "#0078D4"


class TestHttpModels:
    """Tests for HTTP request/response models."""

    def test_http_request_get(self):
        """Should create GET request."""
        request = HttpEndpointRequest(
            method="GET",
            path="/api/v1/groups/list",
            query_params={"provider": "google"},
        )

        assert request.method == "GET"
        assert request.path == "/api/v1/groups/list"
        assert request.query_params == {"provider": "google"}
        assert request.body is None

    def test_http_request_post(self):
        """Should create POST request."""
        request = HttpEndpointRequest(
            method="POST",
            path="/api/v1/groups/add",
            headers={"Content-Type": "application/json"},
            body={
                "group_id": "eng-team",
                "member_email": "user@example.com",
            },
        )

        assert request.method == "POST"
        assert request.path == "/api/v1/groups/add"
        assert request.body["group_id"] == "eng-team"
        assert request.timeout_seconds == 30  # Default

    def test_http_response_success(self):
        """Should create successful response."""
        response = HttpEndpointResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={"success": True, "data": {"id": "123"}},
        )

        assert response.status_code == 200
        assert response.body["success"] is True

    def test_http_response_error(self):
        """Should create error response."""
        response = HttpEndpointResponse(
            status_code=400,
            headers={"Content-Type": "application/json"},
            body={"detail": "Invalid request"},
        )

        assert response.status_code == 400
        assert response.body["detail"] == "Invalid request"
