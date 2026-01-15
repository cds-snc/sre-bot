"""Unit tests for response models."""

from infrastructure.commands.responses.models import (
    Button,
    ButtonStyle,
    Card,
    ErrorMessage,
    Field,
    SuccessMessage,
)


class TestButtonStyle:
    """Tests for ButtonStyle enum."""

    def test_button_style_default_value(self):
        """ButtonStyle.DEFAULT has expected value."""
        assert ButtonStyle.DEFAULT.value == "default"

    def test_button_style_primary_value(self):
        """ButtonStyle.PRIMARY has expected value."""
        assert ButtonStyle.PRIMARY.value == "primary"

    def test_button_style_danger_value(self):
        """ButtonStyle.DANGER has expected value."""
        assert ButtonStyle.DANGER.value == "danger"

    def test_button_style_is_string_enum(self):
        """ButtonStyle values are strings."""
        assert isinstance(ButtonStyle.DEFAULT, str)
        assert isinstance(ButtonStyle.PRIMARY, str)
        assert isinstance(ButtonStyle.DANGER, str)


class TestButton:
    """Tests for Button model."""

    def test_button_creation_with_required_fields(self):
        """Button can be created with required fields."""
        btn = Button(text="Click me", action_id="btn_1")

        assert btn.text == "Click me"
        assert btn.action_id == "btn_1"
        assert btn.style == ButtonStyle.DEFAULT
        assert btn.value is None

    def test_button_creation_with_all_fields(self):
        """Button can be created with all fields."""
        btn = Button(
            text="Delete",
            action_id="btn_delete",
            style=ButtonStyle.DANGER,
            value="item-123",
        )

        assert btn.text == "Delete"
        assert btn.action_id == "btn_delete"
        assert btn.style == ButtonStyle.DANGER
        assert btn.value == "item-123"

    def test_button_style_default(self):
        """Button defaults to DEFAULT style."""
        btn = Button(text="Test", action_id="test")
        assert btn.style == ButtonStyle.DEFAULT

    def test_button_value_optional(self):
        """Button value is optional."""
        btn = Button(text="Test", action_id="test")
        assert btn.value is None

    def test_button_string_style_accepted(self):
        """Button accepts ButtonStyle enum values."""
        btn = Button(
            text="Primary",
            action_id="btn_primary",
            style=ButtonStyle.PRIMARY,
        )
        assert btn.style == ButtonStyle.PRIMARY


class TestField:
    """Tests for Field model."""

    def test_field_creation_with_required_fields(self):
        """Field can be created with required fields."""
        field = Field(title="Status", value="Active")

        assert field.title == "Status"
        assert field.value == "Active"
        assert field.short is False

    def test_field_creation_with_all_fields(self):
        """Field can be created with all fields."""
        field = Field(title="Priority", value="High", short=True)

        assert field.title == "Priority"
        assert field.value == "High"
        assert field.short is True

    def test_field_short_default_false(self):
        """Field short defaults to False."""
        field = Field(title="Test", value="test")
        assert field.short is False

    def test_field_short_true(self):
        """Field can be set to display inline."""
        field = Field(title="Test", value="test", short=True)
        assert field.short is True

    def test_field_empty_title(self):
        """Field allows empty title."""
        field = Field(title="", value="test")
        assert field.title == ""

    def test_field_empty_value(self):
        """Field allows empty value."""
        field = Field(title="Empty", value="")
        assert field.value == ""


class TestCard:
    """Tests for Card model."""

    def test_card_creation_with_required_fields(self):
        """Card can be created with required fields."""
        card = Card(title="Test Card", text="Card content")

        assert card.title == "Test Card"
        assert card.text == "Card content"
        assert card.color == "#36a64f"
        assert card.fields == []
        assert card.buttons == []
        assert card.footer is None
        assert card.image_url is None

    def test_card_creation_with_all_fields(self):
        """Card can be created with all fields."""
        fields = [Field(title="Status", value="Active")]
        buttons = [Button(text="Action", action_id="act_1")]

        card = Card(
            title="Full Card",
            text="Content",
            color="#FF0000",
            fields=fields,
            buttons=buttons,
            footer="Card footer",
            image_url="https://example.com/image.png",
        )

        assert card.title == "Full Card"
        assert card.text == "Content"
        assert card.color == "#FF0000"
        assert len(card.fields) == 1
        assert len(card.buttons) == 1
        assert card.footer == "Card footer"
        assert card.image_url == "https://example.com/image.png"

    def test_card_default_color(self):
        """Card defaults to green color."""
        card = Card(title="Test", text="Test")
        assert card.color == "#36a64f"

    def test_card_custom_color(self):
        """Card can have custom hex color."""
        card = Card(title="Test", text="Test", color="#FF5733")
        assert card.color == "#FF5733"

    def test_card_multiple_fields(self):
        """Card can contain multiple fields."""
        fields = [
            Field(title="Field 1", value="Value 1"),
            Field(title="Field 2", value="Value 2"),
            Field(title="Field 3", value="Value 3"),
        ]
        card = Card(title="Test", text="Test", fields=fields)

        assert len(card.fields) == 3
        assert card.fields[0].title == "Field 1"
        assert card.fields[2].title == "Field 3"

    def test_card_multiple_buttons(self):
        """Card can contain multiple buttons."""
        buttons = [
            Button(text="Button 1", action_id="btn_1"),
            Button(text="Button 2", action_id="btn_2"),
        ]
        card = Card(title="Test", text="Test", buttons=buttons)

        assert len(card.buttons) == 2
        assert card.buttons[0].text == "Button 1"
        assert card.buttons[1].text == "Button 2"

    def test_card_empty_text(self):
        """Card allows empty text."""
        card = Card(title="Test", text="")
        assert card.text == ""


class TestErrorMessage:
    """Tests for ErrorMessage model."""

    def test_error_message_creation_with_required_fields(self):
        """ErrorMessage can be created with required fields."""
        error = ErrorMessage(message="Something went wrong")

        assert error.message == "Something went wrong"
        assert error.details is None
        assert error.error_code is None

    def test_error_message_creation_with_all_fields(self):
        """ErrorMessage can be created with all fields."""
        error = ErrorMessage(
            message="Operation failed",
            details="Traceback: ...",
            error_code="ERR_OPERATION_FAILED",
        )

        assert error.message == "Operation failed"
        assert error.details == "Traceback: ..."
        assert error.error_code == "ERR_OPERATION_FAILED"

    def test_error_message_details_optional(self):
        """ErrorMessage details are optional."""
        error = ErrorMessage(message="Error", error_code="ERR_001")
        assert error.details is None

    def test_error_message_error_code_optional(self):
        """ErrorMessage error_code is optional."""
        error = ErrorMessage(message="Error", details="Some details")
        assert error.error_code is None

    def test_error_message_empty_message(self):
        """ErrorMessage allows empty message."""
        error = ErrorMessage(message="")
        assert error.message == ""

    def test_error_message_multiline_details(self):
        """ErrorMessage supports multiline details."""
        details = "Line 1\nLine 2\nLine 3"
        error = ErrorMessage(message="Error", details=details)
        assert error.details == details


class TestSuccessMessage:
    """Tests for SuccessMessage model."""

    def test_success_message_creation_with_required_fields(self):
        """SuccessMessage can be created with required fields."""
        success = SuccessMessage(message="Operation succeeded")

        assert success.message == "Operation succeeded"
        assert success.details is None

    def test_success_message_creation_with_all_fields(self):
        """SuccessMessage can be created with all fields."""
        success = SuccessMessage(
            message="Success",
            details="Additional information",
        )

        assert success.message == "Success"
        assert success.details == "Additional information"

    def test_success_message_details_optional(self):
        """SuccessMessage details are optional."""
        success = SuccessMessage(message="Done")
        assert success.details is None

    def test_success_message_empty_message(self):
        """SuccessMessage allows empty message."""
        success = SuccessMessage(message="")
        assert success.message == ""

    def test_success_message_with_details(self):
        """SuccessMessage supports detailed information."""
        details = "5 items processed\n2 items updated"
        success = SuccessMessage(message="Success", details=details)
        assert success.details == details


class TestCardModelIntegration:
    """Integration tests for Card with nested models."""

    def test_card_with_all_model_types(self):
        """Card can integrate Field and Button models."""
        fields = [
            Field(title="Count", value="5"),
            Field(title="Status", value="Completed", short=True),
        ]
        buttons = [
            Button(text="Confirm", action_id="confirm", style=ButtonStyle.PRIMARY),
            Button(text="Cancel", action_id="cancel", style=ButtonStyle.DEFAULT),
        ]

        card = Card(
            title="Report",
            text="Processing complete",
            fields=fields,
            buttons=buttons,
            footer="Generated today",
        )

        assert len(card.fields) == 2
        assert len(card.buttons) == 2
        assert card.fields[1].short is True
        assert card.buttons[0].style == ButtonStyle.PRIMARY
        assert card.footer == "Generated today"
