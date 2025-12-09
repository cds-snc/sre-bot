"""Unit tests for groups notification event handlers.

Tests the GroupNotificationHandler class with centralized infrastructure
dependencies (NotificationDispatcher, Translator, LocaleResolver, IdempotencyKeyBuilder).

Following testing strategy in /workspace/app/tests/TESTING_STRATEGY.md:
- Pure unit tests with mocked external dependencies
- Test classes group related functionality
- Fixtures for test data and mocks
- Descriptive test names following test_<function>_<scenario> pattern
"""

import pytest
from unittest.mock import MagicMock
from infrastructure.events import Event
from infrastructure.i18n import Locale
from infrastructure.notifications.models import NotificationStatus
from modules.groups.events.handlers import GroupNotificationHandler
from tests.factories.notifications import make_notification_result


@pytest.fixture
def mock_dispatcher():
    """Mock NotificationDispatcher for testing."""
    dispatcher = MagicMock()
    dispatcher.send.return_value = [
        make_notification_result(
            channel="chat",
            status=NotificationStatus.SENT,
            message="Sent successfully",
        )
    ]
    return dispatcher


@pytest.fixture
def mock_translator():
    """Mock Translator for testing."""
    translator = MagicMock()
    translator.translate_message.return_value = "Translated message"
    return translator


@pytest.fixture
def mock_locale_resolver():
    """Mock LocaleResolver for testing."""
    resolver = MagicMock()
    resolver.default_locale = Locale.EN_US
    return resolver


@pytest.fixture
def mock_key_builder():
    """Mock IdempotencyKeyBuilder for testing."""
    builder = MagicMock()
    builder.build.return_value = "groups_notifications:send_notification:abc123"
    return builder


@pytest.fixture
def notification_handler(
    mock_dispatcher, mock_translator, mock_locale_resolver, mock_key_builder
):
    """Create GroupNotificationHandler with mocked dependencies."""
    return GroupNotificationHandler(
        dispatcher=mock_dispatcher,
        translator=mock_translator,
        locale_resolver=mock_locale_resolver,
        key_builder=mock_key_builder,
    )


@pytest.fixture
def sample_event_added():
    """Sample event for member added."""
    return Event(
        event_type="group.member.added",
        metadata={
            "request": {
                "requestor": "admin@example.com",
                "member_email": "user@example.com",
                "group_id": "engineering-team",
                "provider": "google",
            },
            "orchestration": {
                "action": "add_member",
                "provider": "google",
                "status": "success",
            },
        },
    )


@pytest.fixture
def sample_event_removed():
    """Sample event for member removed."""
    return Event(
        event_type="group.member.removed",
        metadata={
            "request": {
                "requestor": "admin@example.com",
                "member_email": "user@example.com",
                "group_id": "engineering-team",
                "provider": "google",
            },
            "orchestration": {
                "action": "remove_member",
                "provider": "google",
                "status": "success",
            },
        },
    )


@pytest.mark.unit
class TestGroupNotificationHandler:
    """Tests for GroupNotificationHandler class."""

    def test_handle_member_added_uses_translator(
        self, notification_handler, mock_translator, sample_event_added
    ):
        """Test that handler uses translator for i18n."""
        notification_handler.handle_member_added(sample_event_added)

        assert mock_translator.translate_message.called
        call_args = mock_translator.translate_message.call_args_list
        assert len(call_args) > 0

    def test_handle_member_added_uses_locale_resolver(
        self, notification_handler, mock_locale_resolver, sample_event_added
    ):
        """Test that handler uses locale resolver's default locale."""
        notification_handler.handle_member_added(sample_event_added)

        assert mock_locale_resolver.default_locale == Locale.EN_US

    def test_handle_member_added_uses_idempotency_builder(
        self, notification_handler, mock_key_builder, sample_event_added
    ):
        """Test that handler uses centralized idempotency builder with correlation_id.

        Idempotency is scoped to the operation (correlation_id) to allow the same
        member to be added/removed multiple times while preventing duplicates
        within a single operation.
        """
        notification_handler.handle_member_added(sample_event_added)

        assert mock_key_builder.build.called
        # Get all calls to build - one for requestor, one for member
        all_calls = mock_key_builder.build.call_args_list
        assert len(all_calls) >= 2

        # Each call should include correlation_id and recipient
        for call in all_calls:
            call_kwargs = call.kwargs
            assert call_kwargs["operation"] == "send_notification"
            assert "correlation_id" in call_kwargs
            assert "recipient" in call_kwargs

    def test_handle_member_added_sends_notifications(
        self, notification_handler, mock_dispatcher, sample_event_added
    ):
        """Test notifications are sent via dispatcher."""
        notification_handler.handle_member_added(sample_event_added)

        assert mock_dispatcher.send.call_count == 2

    def test_handle_member_removed_sends_notifications(
        self, notification_handler, mock_dispatcher, sample_event_removed
    ):
        """Test notifications sent for member removal."""
        notification_handler.handle_member_removed(sample_event_removed)

        assert mock_dispatcher.send.call_count == 2

    def test_skip_notification_for_same_requester_and_member(
        self, notification_handler, mock_dispatcher
    ):
        """Test only one notification sent when requester equals member."""
        event = Event(
            event_type="group.member.added",
            metadata={
                "request": {
                    "requestor": "admin@example.com",
                    "member_email": "admin@example.com",
                    "group_id": "engineering-team",
                    "provider": "google",
                },
                "orchestration": {
                    "action": "add_member",
                    "provider": "google",
                },
            },
        )

        notification_handler.handle_member_added(event)

        assert mock_dispatcher.send.call_count == 1

    def test_skip_notification_when_no_requestor(
        self, notification_handler, mock_dispatcher
    ):
        """Test no notifications sent when requestor is missing."""
        event = Event(
            event_type="group.member.added",
            metadata={
                "request": {
                    "member_email": "user@example.com",
                    "group_id": "engineering-team",
                    "provider": "google",
                },
                "orchestration": {
                    "action": "add_member",
                    "provider": "google",
                },
            },
        )

        notification_handler.handle_member_added(event)

        mock_dispatcher.send.assert_not_called()

    def test_translator_receives_correct_variables(
        self, notification_handler, mock_translator, sample_event_added
    ):
        """Test translator receives correct variable substitutions."""
        notification_handler.handle_member_added(sample_event_added)

        calls = mock_translator.translate_message.call_args_list
        requester_call = calls[0]

        assert requester_call.kwargs["variables"]["member_email"] == "user@example.com"
        assert requester_call.kwargs["variables"]["group_id"] == "engineering-team"

    def test_idempotency_key_includes_recipient(
        self, notification_handler, mock_key_builder, sample_event_added
    ):
        """Test idempotency key includes recipient for uniqueness."""
        notification_handler.handle_member_added(sample_event_added)

        calls = mock_key_builder.build.call_args_list
        assert calls[0].kwargs["recipient"] == "admin@example.com"
        assert calls[1].kwargs["recipient"] == "user@example.com"

    def test_notification_metadata_includes_all_context(
        self, notification_handler, mock_dispatcher, sample_event_added
    ):
        """Test notification includes complete metadata."""
        notification_handler.handle_member_added(sample_event_added)

        notification = mock_dispatcher.send.call_args_list[0][0][0]
        assert notification.metadata["group_id"] == "engineering-team"
        assert notification.metadata["member_email"] == "user@example.com"
        assert notification.metadata["requestor"] == "admin@example.com"
        assert notification.metadata["action"] == "add_member"
        assert notification.metadata["provider"] == "google"
        assert notification.metadata["event_type"] == "group.member.added"
        assert "locale" in notification.metadata
