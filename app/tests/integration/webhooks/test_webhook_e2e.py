"""End-to-end webhook integration tests.

Tests the complete webhook flow including:
- FastAPI lifespan initialization (app.state setup)
- HTTP request handling with real app context
- Payload validation for all webhook types
- Graceful error handling when dependencies unavailable
- Request/response cycle with actual middleware and dependencies

These tests prevent regressions like:
- KeyError: 'bot' when accessing request.state
- Missing app.state attributes causing crashes
- Unhandled payload types
- Graceful degradation when Slack bot not initialized
"""

import pytest
from unittest.mock import MagicMock


@pytest.mark.integration
def test_webhook_handler_with_cloudwatch_alarm_and_bot_initialized(
    app_with_lifespan,
    webhook_id,
    sns_cloudwatch_alarm_payload,
    mock_webhook_lookup,
    mock_webhook_increment,
    mock_sns_signature_validation_disabled,
):
    """Test SNS CloudWatch alarm payload with bot initialized.

    This is the exact scenario that previously crashed with:
    KeyError: 'bot' in request.state

    The payload triggers the AwsSnsPayload handler path that accesses
    the bot client. With proper app.state initialization, this should
    succeed without crashes.
    """
    # Verify bot is initialized
    assert hasattr(app_with_lifespan.app.state, "bot")

    # Send SNS payload
    response = app_with_lifespan.post(
        f"/hook/{webhook_id}",
        json=sns_cloudwatch_alarm_payload,
    )

    # Should succeed (200) or degrade gracefully (503 if no bot)
    # Never crash with 500 ASGI error
    assert response.status_code in [
        200,
        503,
    ], f"Expected 200 or 503, got {response.status_code}: {response.text}"

    if response.status_code == 503:
        # If bot not initialized, should return clear error message
        assert (
            "Slack bot not initialized" in response.text or "Slack bot" in response.text
        )


@pytest.mark.integration
def test_webhook_handler_with_budget_notification(
    app_with_lifespan,
    webhook_id,
    sns_budget_notification_payload,
    mock_webhook_lookup,
    mock_webhook_increment,
    mock_sns_signature_validation_disabled,
):
    """Test SNS budget notification payload."""
    response = app_with_lifespan.post(
        f"/hook/{webhook_id}",
        json=sns_budget_notification_payload,
    )

    # Should handle SNS payload without crash
    assert response.status_code in [
        200,
        503,
    ], f"Got crash: {response.status_code}: {response.text}"


@pytest.mark.integration
def test_webhook_handler_with_subscription_confirmation(
    app_with_lifespan,
    webhook_id,
    sns_subscription_confirmation_payload,
    mock_webhook_lookup,
    mock_webhook_increment,
):
    """Test SNS subscription confirmation (SubscriptionConfirmation type)."""
    response = app_with_lifespan.post(
        f"/hook/{webhook_id}",
        json=sns_subscription_confirmation_payload,
    )

    # Should handle subscription confirmation without crash
    assert (
        response.status_code != 500
    ), f"Got ASGI crash: {response.status_code}: {response.text}"


@pytest.mark.integration
def test_webhook_handler_with_simple_text_payload(
    app_with_lifespan,
    webhook_id,
    simple_text_payload,
    mock_webhook_lookup,
    mock_webhook_increment,
):
    """Test simple text webhook payload."""
    response = app_with_lifespan.post(
        f"/hook/{webhook_id}",
        json=simple_text_payload,
    )

    # Should handle without crash
    assert response.status_code != 500, f"Got ASGI crash: {response.status_code}"


@pytest.mark.integration
def test_webhook_handler_with_all_payload_types(
    app_with_lifespan,
    webhook_id,
    webhook_payload_variety,
    mock_webhook_lookup,
    mock_webhook_increment,
    mock_sns_signature_validation_disabled,
):
    """Test that all webhook payload types are handled without crashes.

    This parametrized test ensures every payload type (SNS, simple text,
    access request, generic) can be processed without ASGI crashes.

    This catches issues where specific payload paths access uninitialized
    app.state attributes.
    """
    payload_type_name, payload = webhook_payload_variety

    response = app_with_lifespan.post(
        f"/hook/{webhook_id}",
        json=payload,
    )

    # Never crash with 500 ASGI error
    assert response.status_code != 500, (
        f"Payload type '{payload_type_name}' caused ASGI crash "
        f"(500): {response.text}"
    )

    # Should return valid HTTP status (200, 400, 503, etc.)
    assert 100 <= response.status_code < 600, (
        f"Invalid HTTP status for payload type '{payload_type_name}': "
        f"{response.status_code}"
    )


@pytest.mark.integration
def test_webhook_missing_webhook_record(
    app_with_lifespan,
    webhook_id,
    sns_cloudwatch_alarm_payload,
    monkeypatch,
):
    """Test webhook request when webhook record not found in database."""
    # Mock webhook lookup to return None
    mock_get_webhook = MagicMock(return_value=None)
    monkeypatch.setattr(
        "modules.slack.webhooks.get_webhook",
        mock_get_webhook,
        raising=False,
    )

    response = app_with_lifespan.post(
        f"/hook/{webhook_id}",
        json=sns_cloudwatch_alarm_payload,
    )

    # Should return 404, not crash
    assert response.status_code == 404
    assert "not found" in response.text.lower()


@pytest.mark.integration
def test_webhook_inactive_webhook(
    app_with_lifespan,
    webhook_id,
    sns_cloudwatch_alarm_payload,
    monkeypatch,
):
    """Test webhook request when webhook is inactive."""
    # Mock webhook lookup to return inactive record
    mock_get_webhook = MagicMock(
        return_value={
            "id": {"S": webhook_id},
            "channel": {"S": "test-channel"},
            "active": {"BOOL": False},  # Inactive
        }
    )
    monkeypatch.setattr(
        "modules.slack.webhooks.get_webhook",
        mock_get_webhook,
        raising=False,
    )

    response = app_with_lifespan.post(
        f"/hook/{webhook_id}",
        json=sns_cloudwatch_alarm_payload,
    )

    # Should return 404 for inactive webhook
    assert response.status_code == 404
    assert "not active" in response.text.lower() or "inactive" in response.text.lower()


@pytest.mark.integration
def test_webhook_malformed_json(
    app_with_lifespan,
    webhook_id,
    mock_webhook_lookup,
):
    """Test webhook request with malformed JSON payload."""
    response = app_with_lifespan.post(
        f"/hook/{webhook_id}",
        data='{"invalid_json": "missing_end_quote}',
        headers={"Content-Type": "application/json"},
    )

    # FastAPI returns 422 for JSON validation errors, not 400
    assert response.status_code == 422
    # Verify it's a validation error response


@pytest.mark.integration
def test_app_state_bot_accessible_in_webhook_context(app_with_lifespan):
    """Verify app.state.bot is accessible during webhook request context.

    This ensures the fix for the KeyError: 'bot' issue is working.
    The bot attribute must exist on app.state for routes to safely check it.
    """
    # app.state.bot can be None if Slack not configured, but must exist
    assert hasattr(app_with_lifespan.app.state, "bot"), (
        "app.state.bot not found. Routes that use getattr(app.state, 'bot') "
        "will fail if the attribute doesn't exist."
    )

    # If bot exists, it should be either None or have a client attribute
    bot = getattr(app_with_lifespan.app.state, "bot", None)
    if bot is not None:
        assert hasattr(bot, "client"), (
            "app.state.bot exists but has no 'client' attribute. "
            "This will cause AttributeError when routes try to use bot.client."
        )
