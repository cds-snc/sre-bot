"""Behavior tests for ``AWSSettings`` as the single home of AWS configuration.

Covers transport fields, the dynamodb-only local endpoint, the transient retry
hint, the feature-level fields (SSO permission sets, per-account role ARNs,
SSO instance identifiers, the service-to-role map) and the cached provider.
Environment aliases are exercised with real environment variables; the
service-to-role map is compared against the infrastructure settings module
that still defines it, so both stay identical while both exist.
"""

from __future__ import annotations

import pytest

from infrastructure.configuration.integrations.aws import AwsSettings as InfrastructureAwsSettings
from integrations.aws.settings import AWSSettings, get_aws_settings

pytestmark = pytest.mark.unit

_FEATURE_FIELDS = [
    ("SYSTEM_ADMIN_PERMISSIONS", "AWS_SSO_SYSTEM_ADMIN_PERMISSIONS"),
    ("VIEW_ONLY_PERMISSIONS", "AWS_SSO_VIEW_ONLY_PERMISSIONS"),
    ("AUDIT_ROLE_ARN", "AWS_AUDIT_ACCOUNT_ROLE_ARN"),
    ("ORG_ROLE_ARN", "AWS_ORG_ACCOUNT_ROLE_ARN"),
    ("LOGGING_ROLE_ARN", "AWS_LOGGING_ACCOUNT_ROLE_ARN"),
    ("INSTANCE_ID", "AWS_SSO_INSTANCE_ID"),
    ("INSTANCE_ARN", "AWS_SSO_INSTANCE_ARN"),
]


class TestTransportFields:
    """Region, retry policy and timeouts with their environment aliases."""

    def test_defaults_resolve_when_env_is_empty(self) -> None:
        settings = AWSSettings()

        assert settings.AWS_REGION == "ca-central-1"
        assert settings.RETRY_MAX_ATTEMPTS == 3
        assert settings.RETRY_MODE == "standard"
        assert settings.CONNECT_TIMEOUT_SECONDS == 10
        assert settings.READ_TIMEOUT_SECONDS == 10

    @pytest.mark.parametrize(
        ("field", "alias", "raw", "expected"),
        [
            ("AWS_REGION", "AWS_REGION", "eu-west-1", "eu-west-1"),
            ("RETRY_MAX_ATTEMPTS", "AWS_RETRY_MAX_ATTEMPTS", "5", 5),
            ("RETRY_MODE", "AWS_RETRY_MODE", "adaptive", "adaptive"),
            ("CONNECT_TIMEOUT_SECONDS", "AWS_CONNECT_TIMEOUT_SECONDS", "2", 2),
            ("READ_TIMEOUT_SECONDS", "AWS_READ_TIMEOUT_SECONDS", "7", 7),
        ],
    )
    def test_reads_from_env_alias(
        self, monkeypatch: pytest.MonkeyPatch, field: str, alias: str, raw: str, expected: object
    ) -> None:
        monkeypatch.setenv(alias, raw)

        assert getattr(AWSSettings(), field) == expected


class TestEndpointFields:
    """Only a dynamodb-specific local endpoint exists; the global endpoint field is gone."""

    def test_dynamodb_endpoint_defaults_to_none(self) -> None:
        assert AWSSettings().DYNAMODB_ENDPOINT_URL is None

    def test_dynamodb_endpoint_reads_botocore_native_alias(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_ENDPOINT_URL_DYNAMODB", "http://dynamodb-local:8000")

        assert AWSSettings().DYNAMODB_ENDPOINT_URL == "http://dynamodb-local:8000"

    def test_global_endpoint_field_is_absent(self) -> None:
        assert "AWS_ENDPOINT_URL" not in AWSSettings.model_fields
        assert not hasattr(AWSSettings(), "AWS_ENDPOINT_URL")


class TestClassificationFields:
    """Error-code catalogues and the transient retry hint."""

    def test_transient_retry_after_defaults_to_sixty_seconds(self) -> None:
        assert AWSSettings().TRANSIENT_RETRY_AFTER_SECONDS == 60

    def test_transient_retry_after_reads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_TRANSIENT_RETRY_AFTER_SECONDS", "15")

        assert AWSSettings().TRANSIENT_RETRY_AFTER_SECONDS == 15

    def test_catalogue_defaults_cover_the_canonical_codes(self) -> None:
        settings = AWSSettings()

        assert {"ResourceNotFoundException", "NoSuchEntity", "NotFoundException"} <= set(settings.NOT_FOUND_CODES)
        assert {"AccessDenied", "AccessDeniedException", "ExpiredToken"} <= set(settings.UNAUTHORIZED_CODES)
        assert {"Throttling", "ThrottlingException", "ServiceUnavailable", "InternalServerError"} <= set(settings.TRANSIENT_CODES)

    def test_catalogues_are_overridable_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_NOT_FOUND_CODES", '["CustomMissing"]')

        assert AWSSettings().NOT_FOUND_CODES == ["CustomMissing"]


class TestFeatureFields:
    """Feature-level AWS configuration lives here with the aliases the deployment already sets."""

    @pytest.mark.parametrize(("field", "alias"), _FEATURE_FIELDS)
    def test_defaults_to_empty_string(self, field: str, alias: str) -> None:
        assert getattr(AWSSettings(), field) == ""

    @pytest.mark.parametrize(("field", "alias"), _FEATURE_FIELDS)
    def test_reads_from_env_alias(self, monkeypatch: pytest.MonkeyPatch, field: str, alias: str) -> None:
        monkeypatch.setenv(alias, f"value-for-{field}")

        assert getattr(AWSSettings(), field) == f"value-for-{field}"

    def test_service_role_map_composes_the_configured_role_arns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_AUDIT_ACCOUNT_ROLE_ARN", "arn:audit")
        monkeypatch.setenv("AWS_ORG_ACCOUNT_ROLE_ARN", "arn:org")
        monkeypatch.setenv("AWS_LOGGING_ACCOUNT_ROLE_ARN", "arn:logging")

        assert AWSSettings().SERVICE_ROLE_MAP == {
            "audit": "arn:audit",
            "organizations": "arn:org",
            "identitystore": "arn:org",
            "sso-admin": "arn:org",
            "logging": "arn:logging",
            "ce": "arn:org",
            "config": "arn:audit",
            "guardduty": "arn:logging",
        }

    def test_service_role_map_matches_the_infrastructure_module_while_both_exist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(InfrastructureAwsSettings.model_config, "env_file", None)
        monkeypatch.setenv("AWS_AUDIT_ACCOUNT_ROLE_ARN", "arn:audit")
        monkeypatch.setenv("AWS_ORG_ACCOUNT_ROLE_ARN", "arn:org")
        monkeypatch.setenv("AWS_LOGGING_ACCOUNT_ROLE_ARN", "arn:logging")

        assert AWSSettings().SERVICE_ROLE_MAP == InfrastructureAwsSettings().SERVICE_ROLE_MAP


class TestProvider:
    """``get_aws_settings()`` caches one instance per process until cleared."""

    def test_returns_an_awssettings_instance(self) -> None:
        assert isinstance(get_aws_settings(), AWSSettings)

    def test_is_a_singleton_across_calls(self) -> None:
        assert get_aws_settings() is get_aws_settings()

    def test_cache_clear_yields_a_fresh_instance(self) -> None:
        first = get_aws_settings()
        get_aws_settings.cache_clear()

        assert get_aws_settings() is not first
