"""Contract tests for dev Slack platform environment gating."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from modules.dev.platforms import slack as dev_slack


def test_contract_require_dev_environment_uses_environment_not_prefix():
    """Dev commands should be available in non-production environments."""
    payload = MagicMock()

    with patch(
        "modules.dev.platforms.slack.get_app_settings",
        return_value=SimpleNamespace(ENVIRONMENT="local"),
    ):
        response = dev_slack._require_dev_environment(payload)

    assert response is None


def test_contract_require_dev_environment_denies_production():
    """Dev commands must be blocked in production environments."""
    payload = MagicMock()

    with patch(
        "modules.dev.platforms.slack.get_app_settings",
        return_value=SimpleNamespace(ENVIRONMENT="production"),
    ):
        response = dev_slack._require_dev_environment(payload)

    assert response is not None
    assert response.ephemeral is True
