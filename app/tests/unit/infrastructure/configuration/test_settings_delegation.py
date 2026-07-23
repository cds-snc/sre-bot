"""Unit tests for Settings aggregator delegation to domain singletons (PR-5).

Verifies that Settings.__init__ delegates to singleton providers so that
Settings().slack is get_slack_settings() (same object identity).
"""

import pytest

from infrastructure.configuration.app import get_app_settings
from infrastructure.configuration.features import (
    get_atip_settings,
    get_aws_feature_settings,
    get_incident_settings,
    get_sre_ops_settings,
)
from infrastructure.configuration.infrastructure import (
    get_dev_settings,
    get_directory_settings,
    get_idempotency_settings,
    get_platforms_settings,
    get_retry_settings,
    get_server_settings,
)
from infrastructure.configuration.integrations import (
    get_aws_settings,
    get_google_resources_config,
    get_google_workspace_settings,
    get_maxmind_settings,
    get_notify_settings,
    get_opsgenie_settings,
    get_sentinel_settings,
    get_slack_settings,
    get_trello_settings,
)


@pytest.fixture(autouse=True)
def clear_all_caches():
    """Clear all singleton caches before and after each test."""
    get_app_settings.cache_clear()
    get_slack_settings.cache_clear()
    get_aws_settings.cache_clear()
    get_google_workspace_settings.cache_clear()
    get_google_resources_config.cache_clear()
    get_maxmind_settings.cache_clear()
    get_notify_settings.cache_clear()
    get_opsgenie_settings.cache_clear()
    get_sentinel_settings.cache_clear()
    get_trello_settings.cache_clear()
    get_incident_settings.cache_clear()
    get_aws_feature_settings.cache_clear()
    get_atip_settings.cache_clear()
    get_sre_ops_settings.cache_clear()
    get_server_settings.cache_clear()
    get_dev_settings.cache_clear()
    get_idempotency_settings.cache_clear()
    get_retry_settings.cache_clear()
    get_platforms_settings.cache_clear()
    get_directory_settings.cache_clear()
    yield
    get_app_settings.cache_clear()
    get_slack_settings.cache_clear()
    get_aws_settings.cache_clear()
    get_google_workspace_settings.cache_clear()
    get_google_resources_config.cache_clear()
    get_maxmind_settings.cache_clear()
    get_notify_settings.cache_clear()
    get_opsgenie_settings.cache_clear()
    get_sentinel_settings.cache_clear()
    get_trello_settings.cache_clear()
    get_incident_settings.cache_clear()
    get_aws_feature_settings.cache_clear()
    get_atip_settings.cache_clear()
    get_sre_ops_settings.cache_clear()
    get_server_settings.cache_clear()
    get_dev_settings.cache_clear()
    get_idempotency_settings.cache_clear()
    get_retry_settings.cache_clear()
    get_platforms_settings.cache_clear()
    get_directory_settings.cache_clear()
