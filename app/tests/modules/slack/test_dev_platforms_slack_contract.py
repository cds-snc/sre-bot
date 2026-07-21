"""Contract tests for dev Slack platform environment gating."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from modules.dev.platforms import slack as dev_slack


def test_contract_require_dev_environment_uses_environment_not_prefix():
    """Dev commands must be gated by ENVIRONMENT, not PREFIX."""
    payload = MagicMock()

    with patch(
        "modules.dev.platforms.slack.get_app_settings",
        return_value=SimpleNamespace(PREFIX="dev-", ENVIRONMENT="local"),
    ):
        response = dev_slack._require_dev_environment(payload)

    assert response is not None
    assert response.ephemeral is True
