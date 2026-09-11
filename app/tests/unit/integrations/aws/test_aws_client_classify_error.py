"""Behavior tests for ``classify_aws_error``.

Each expected botocore exception family is mapped onto the closed
``OperationStatus`` set using the code catalogues and the transient retry hint
from ``integrations.aws.settings``; anything unexpected propagates unchanged.
Catalogue and retry-hint overrides are applied through real environment
variables plus a provider cache clear so the tests prove settings are read at
classification time rather than bound at import.
"""

from __future__ import annotations

import pytest
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError

from infrastructure.operations.status import OperationStatus
from integrations.aws import client as aws_client
from integrations.aws.settings import get_aws_settings

pytestmark = pytest.mark.unit


def _client_error(code: str, message: str = "boom") -> ClientError:
    return ClientError(
        error_response={"Error": {"Code": code, "Message": message}},
        operation_name="TestOperation",
    )


class TestMappedFamilies:
    """Expected ClientError codes and BotoCoreError map to a status, code and retry hint."""

    @pytest.mark.parametrize("code", ["ResourceNotFoundException", "NoSuchEntity", "NotFoundException"])
    def test_not_found_codes(self, code: str) -> None:
        assert aws_client.classify_aws_error(_client_error(code)) == (OperationStatus.NOT_FOUND, code, None)

    @pytest.mark.parametrize("code", ["AccessDenied", "AccessDeniedException", "ExpiredToken"])
    def test_unauthorized_codes(self, code: str) -> None:
        assert aws_client.classify_aws_error(_client_error(code)) == (OperationStatus.UNAUTHORIZED, code, None)

    @pytest.mark.parametrize("code", ["Throttling", "ThrottlingException", "ServiceUnavailable", "InternalServerError"])
    def test_transient_codes_carry_the_default_retry_hint(self, code: str) -> None:
        assert aws_client.classify_aws_error(_client_error(code)) == (OperationStatus.TRANSIENT_ERROR, code, 60)

    def test_conditional_check_failure_is_permanent(self) -> None:
        result = aws_client.classify_aws_error(_client_error("ConditionalCheckFailedException"))

        assert result == (OperationStatus.PERMANENT_ERROR, "ConditionalCheckFailedException", None)

    def test_botocore_transport_errors_are_transient_without_a_retry_hint(self) -> None:
        exc = EndpointConnectionError(endpoint_url="https://dynamodb.ca-central-1.amazonaws.com")

        status, code, retry_after = aws_client.classify_aws_error(exc)

        assert isinstance(exc, BotoCoreError)
        assert status is OperationStatus.TRANSIENT_ERROR
        assert code == "EndpointConnectionError"
        assert retry_after is None


class TestSettingsDriven:
    """Catalogues and the retry hint come from the AWS settings module."""

    def test_retry_hint_follows_the_configured_transient_retry_after(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_TRANSIENT_RETRY_AFTER_SECONDS", "15")
        get_aws_settings.cache_clear()

        assert aws_client.classify_aws_error(_client_error("Throttling")) == (OperationStatus.TRANSIENT_ERROR, "Throttling", 15)

    def test_not_found_catalogue_override_maps_a_custom_code(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_NOT_FOUND_CODES", '["CustomMissing"]')
        get_aws_settings.cache_clear()

        assert aws_client.classify_aws_error(_client_error("CustomMissing")) == (OperationStatus.NOT_FOUND, "CustomMissing", None)

    def test_transient_catalogue_override_removes_default_codes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_TRANSIENT_CODES", '["OnlyThisOne"]')
        get_aws_settings.cache_clear()

        with pytest.raises(ClientError):
            aws_client.classify_aws_error(_client_error("Throttling"))


class TestPropagation:
    """Unexpected exceptions are not outcomes: they propagate unchanged."""

    def test_unmapped_client_error_propagates(self) -> None:
        exc = _client_error("ValidationException")

        with pytest.raises(ClientError) as excinfo:
            aws_client.classify_aws_error(exc)

        assert excinfo.value is exc

    def test_client_error_without_a_code_propagates(self) -> None:
        exc = ClientError(error_response={"Error": {"Message": "no code"}}, operation_name="TestOperation")

        with pytest.raises(ClientError):
            aws_client.classify_aws_error(exc)

    def test_programmer_errors_propagate(self) -> None:
        with pytest.raises(KeyError):
            aws_client.classify_aws_error(KeyError("bug"))
