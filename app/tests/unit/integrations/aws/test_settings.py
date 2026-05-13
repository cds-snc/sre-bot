"""Tests for `AWSSettings` and its `get_aws_settings()` provider.

Verifies vendor-credential scope, env-var resolution, the `@lru_cache`
singleton contract, and the absence of domain fields on the settings class.
"""

from __future__ import annotations

import pytest

from integrations.aws.settings import AWSSettings, get_aws_settings

pytestmark = pytest.mark.unit


class TestAWSSettingsFields:
    """Fields exposed by `AWSSettings`."""

    def test_defaults_resolve_when_env_is_empty(self):
        settings = AWSSettings()

        assert settings.AWS_REGION == "ca-central-1"
        assert settings.AWS_ENDPOINT_URL is None
        assert settings.RETRY_MAX_ATTEMPTS == 3
        assert settings.RETRY_MODE == "standard"
        assert settings.CONNECT_TIMEOUT_SECONDS == 10
        assert settings.READ_TIMEOUT_SECONDS == 10

    def test_aws_region_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("AWS_REGION", "eu-west-1")

        settings = AWSSettings()

        assert settings.AWS_REGION == "eu-west-1"

    def test_endpoint_url_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")

        settings = AWSSettings()

        assert settings.AWS_ENDPOINT_URL == "http://localhost:4566"

    def test_retry_max_attempts_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("AWS_RETRY_MAX_ATTEMPTS", "5")

        settings = AWSSettings()

        assert settings.RETRY_MAX_ATTEMPTS == 5

    def test_retry_mode_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("AWS_RETRY_MODE", "adaptive")

        settings = AWSSettings()

        assert settings.RETRY_MODE == "adaptive"


class TestAWSSettingsClassificationCatalogues:
    """Default error-code catalogues used by the shield's classifier."""

    def test_not_found_defaults_include_canonical_aws_codes(self):
        codes = AWSSettings().NOT_FOUND_CODES

        assert "ResourceNotFoundException" in codes
        assert "NoSuchEntity" in codes
        assert "NoSuchBucket" in codes
        assert "NoSuchKey" in codes

    def test_unauthorized_defaults_include_canonical_aws_codes(self):
        codes = AWSSettings().UNAUTHORIZED_CODES

        assert "AccessDenied" in codes
        assert "AccessDeniedException" in codes
        assert "InvalidClientTokenId" in codes
        assert "ExpiredToken" in codes

    def test_transient_defaults_include_throttling_and_5xx_codes(self):
        codes = AWSSettings().TRANSIENT_CODES

        assert "Throttling" in codes
        assert "ThrottlingException" in codes
        assert "RequestLimitExceeded" in codes
        assert "ProvisionedThroughputExceededException" in codes
        assert "ServiceUnavailable" in codes
        assert "InternalServerError" in codes

    def test_catalogues_are_overridable_at_construction(self):
        settings = AWSSettings(
            AWS_NOT_FOUND_CODES=["CustomNotFound"],
            AWS_UNAUTHORIZED_CODES=["CustomDenied"],
            AWS_TRANSIENT_CODES=["CustomThrottle"],
        )

        assert settings.NOT_FOUND_CODES == ["CustomNotFound"]
        assert settings.UNAUTHORIZED_CODES == ["CustomDenied"]
        assert settings.TRANSIENT_CODES == ["CustomThrottle"]


class TestAWSSettingsScope:
    """`AWSSettings` is scoped to vendor credentials only."""

    @pytest.mark.parametrize(
        "domain_field",
        [
            "SYSTEM_ADMIN_PERMISSIONS",
            "VIEW_ONLY_PERMISSIONS",
            "INSTANCE_ID",
            "INSTANCE_ARN",
            "AUDIT_ROLE_ARN",
            "ORG_ROLE_ARN",
            "LOGGING_ROLE_ARN",
        ],
    )
    def test_domain_fields_are_absent(self, domain_field):
        """Feature-domain settings (SSO permission sets, instance ARNs,
        per-service role ARNs) do not live on the vendor settings class."""
        assert not hasattr(AWSSettings(), domain_field)


class TestGetAWSSettingsProvider:
    """`get_aws_settings()` caches a single instance per process."""

    def test_returns_an_awssettings_instance(self):
        assert isinstance(get_aws_settings(), AWSSettings)

    def test_is_a_singleton_across_calls(self):
        first = get_aws_settings()
        second = get_aws_settings()

        assert first is second

    def test_cache_clear_yields_a_fresh_instance(self):
        first = get_aws_settings()
        get_aws_settings.cache_clear()
        second = get_aws_settings()

        assert first is not second
