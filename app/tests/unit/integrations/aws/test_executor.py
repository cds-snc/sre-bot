"""Tests for `AWSShield.execute()` exception classification.

Verifies that the synchronous executor takes a zero-arg callable, returns
`OperationResult.success` on the call's return value, classifies every
known boto3 `ClientError` code into the closed five-status set, and never
raises an SDK exception above the boundary.
"""

from __future__ import annotations

import pytest
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError

from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus
from integrations.aws.settings import AWSSettings
from integrations.aws.shield import AWSShield

pytestmark = pytest.mark.unit


def _client_error(code: str, message: str = "boom") -> ClientError:
    return ClientError(
        error_response={"Error": {"Code": code, "Message": message}},
        operation_name="TestOperation",
    )


@pytest.fixture
def shield() -> AWSShield:
    return AWSShield(settings=AWSSettings(AWS_REGION="us-east-1"))


class TestExecuteSuccess:
    def test_success_wraps_return_value_in_operation_result(self, shield):
        result = shield.execute(lambda: {"Item": {"id": "1"}})

        assert isinstance(result, OperationResult)
        assert result.is_success
        assert result.data == {"Item": {"id": "1"}}

    def test_success_records_provider_name(self, shield):
        result = shield.execute(lambda: {"ok": True})

        assert result.provider == "aws"

    def test_success_with_none_return_value(self, shield):
        result = shield.execute(lambda: None)

        assert result.is_success
        assert result.data is None


class TestExecuteClientErrorClassification:
    """Each known `ClientError` code maps to the right `OperationStatus`."""

    @pytest.mark.parametrize(
        "code",
        [
            "ResourceNotFoundException",
            "NoSuchEntity",
            "NoSuchBucket",
            "NoSuchKey",
        ],
    )
    def test_not_found_codes(self, shield, code):
        def raise_it():
            raise _client_error(code)

        result = shield.execute(raise_it)

        assert result.status == OperationStatus.NOT_FOUND
        assert result.error_code == code

    @pytest.mark.parametrize(
        "code",
        [
            "AccessDenied",
            "AccessDeniedException",
            "UnauthorizedOperation",
            "InvalidClientTokenId",
            "SignatureDoesNotMatch",
            "ExpiredToken",
        ],
    )
    def test_unauthorized_codes(self, shield, code):
        def raise_it():
            raise _client_error(code)

        result = shield.execute(raise_it)

        assert result.status == OperationStatus.UNAUTHORIZED
        assert result.error_code == code

    @pytest.mark.parametrize(
        "code",
        [
            "Throttling",
            "ThrottlingException",
            "RequestLimitExceeded",
            "ProvisionedThroughputExceededException",
            "TooManyRequestsException",
            "RequestTimeout",
            "ServiceUnavailable",
            "InternalFailure",
        ],
    )
    def test_transient_codes(self, shield, code):
        def raise_it():
            raise _client_error(code)

        result = shield.execute(raise_it)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == code

    @pytest.mark.parametrize(
        "code",
        [
            "ValidationException",
            "InvalidParameterValue",
            "MalformedQueryString",
            "ConditionalCheckFailedException",
        ],
    )
    def test_permanent_codes(self, shield, code):
        def raise_it():
            raise _client_error(code)

        result = shield.execute(raise_it)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == code

    def test_unknown_code_falls_back_to_permanent_error(self, shield):
        def raise_it():
            raise _client_error("SomeBrandNewVendorCode")

        result = shield.execute(raise_it)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "SomeBrandNewVendorCode"


class TestExecuteBotoCoreErrorClassification:
    """Connection-level `BotoCoreError`s classify as transient."""

    def test_endpoint_connection_error_is_transient(self, shield):
        def raise_it():
            raise EndpointConnectionError(endpoint_url="https://example.com")

        result = shield.execute(raise_it)

        assert result.status == OperationStatus.TRANSIENT_ERROR

    def test_generic_botocore_error_is_transient(self, shield):
        class FakeBotoCoreError(BotoCoreError):
            fmt = "fake transport failure"

        def raise_it():
            raise FakeBotoCoreError()

        result = shield.execute(raise_it)

        assert result.status == OperationStatus.TRANSIENT_ERROR


class TestExecuteUsesSettingsCatalogues:
    """The shield classifies against the catalogues carried on `AWSSettings`."""

    def test_custom_not_found_code_routes_to_not_found(self):
        shield = AWSShield(
            settings=AWSSettings(
                AWS_REGION="us-east-1",
                AWS_NOT_FOUND_CODES=["CustomMissing"],
            )
        )

        def raise_it():
            raise _client_error("CustomMissing")

        result = shield.execute(raise_it)

        assert result.status == OperationStatus.NOT_FOUND

    def test_default_not_found_code_is_no_longer_classified_when_overridden(self):
        shield = AWSShield(
            settings=AWSSettings(
                AWS_REGION="us-east-1",
                AWS_NOT_FOUND_CODES=["OnlyThisOne"],
            )
        )

        def raise_it():
            raise _client_error("ResourceNotFoundException")

        result = shield.execute(raise_it)

        assert result.status == OperationStatus.PERMANENT_ERROR

    def test_custom_transient_code_routes_to_transient_error(self):
        shield = AWSShield(
            settings=AWSSettings(
                AWS_REGION="us-east-1",
                AWS_TRANSIENT_CODES=["VendorBackpressure"],
            )
        )

        def raise_it():
            raise _client_error("VendorBackpressure")

        result = shield.execute(raise_it)

        assert result.status == OperationStatus.TRANSIENT_ERROR


class TestExecuteContainsExceptions:
    """No SDK exception ever propagates above `execute()`."""

    @pytest.mark.parametrize(
        "exc_factory",
        [
            lambda: _client_error("ValidationException"),
            lambda: _client_error("ResourceNotFoundException"),
            lambda: _client_error("Throttling"),
            lambda: EndpointConnectionError(endpoint_url="x"),
        ],
    )
    def test_known_sdk_exceptions_do_not_escape(self, shield, exc_factory):
        def raise_it():
            raise exc_factory()

        # Should not raise — every shield-known exception is converted.
        result = shield.execute(raise_it)

        assert not result.is_success

    def test_unexpected_exception_classes_return_permanent_error(self, shield):
        def raise_it():
            raise RuntimeError("logic bug")

        result = shield.execute(raise_it)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "unexpected_error"
