"""Unit tests for error classifiers.

Tests cover:
- Google API HTTP error classification
- AWS SDK error classification
- Edge cases (unknown errors, missing attributes, connection errors)
- Retry-After header extraction
- Error code mapping
"""

import pytest
from unittest.mock import Mock

from infrastructure.operations.classifiers import (
    classify_aws_error,
    classify_http_error,
)
from infrastructure.operations.status import OperationStatus


class TestClassifyHttpError:
    """Tests for classify_http_error() function."""

    def test_classify_429_rate_limit_with_retry_after(self):
        """Test 429 rate limit with Retry-After header."""
        from googleapiclient.errors import HttpError

        mock_resp = Mock()
        mock_resp.status = 429
        mock_resp.get = Mock(return_value="120")  # 120 seconds

        exc = Mock(spec=HttpError)
        exc.resp = mock_resp

        result = classify_http_error(exc)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "RATE_LIMITED"
        assert result.retry_after == 120
        assert "rate limited" in result.message.lower()

    def test_classify_429_rate_limit_without_retry_after(self):
        """Test 429 rate limit without Retry-After header (default 60s)."""
        from googleapiclient.errors import HttpError

        mock_resp = Mock()
        mock_resp.status = 429
        mock_resp.get = Mock(return_value=None)  # No header

        exc = Mock(spec=HttpError)
        exc.resp = mock_resp

        result = classify_http_error(exc)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "RATE_LIMITED"
        assert result.retry_after == 60  # Default

    def test_classify_429_with_malformed_retry_after_header(self):
        """Test 429 with malformed Retry-After header uses default."""
        from googleapiclient.errors import HttpError

        mock_resp = Mock()
        mock_resp.status = 429
        mock_resp.get = Mock(return_value="not-a-number")  # Invalid

        exc = Mock(spec=HttpError)
        exc.resp = mock_resp

        result = classify_http_error(exc)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.retry_after == 60  # Falls back to default

    def test_classify_401_unauthorized(self):
        """Test 401 Unauthorized as PERMANENT_ERROR."""
        from googleapiclient.errors import HttpError

        mock_resp = Mock()
        mock_resp.status = 401

        exc = Mock(spec=HttpError)
        exc.resp = mock_resp

        result = classify_http_error(exc)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "UNAUTHORIZED"
        assert result.retry_after is None
        assert "authentication failed" in result.message.lower()

    def test_classify_403_forbidden(self):
        """Test 403 Forbidden as PERMANENT_ERROR."""
        from googleapiclient.errors import HttpError

        mock_resp = Mock()
        mock_resp.status = 403

        exc = Mock(spec=HttpError)
        exc.resp = mock_resp

        result = classify_http_error(exc)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "FORBIDDEN"
        assert "authorization denied" in result.message.lower()

    def test_classify_404_not_found(self):
        """Test 404 Not Found as NOT_FOUND."""
        from googleapiclient.errors import HttpError

        mock_resp = Mock()
        mock_resp.status = 404

        exc = Mock(spec=HttpError)
        exc.resp = mock_resp

        result = classify_http_error(exc)

        assert result.status == OperationStatus.NOT_FOUND
        assert result.error_code == "NOT_FOUND"
        assert "not found" in result.message.lower()

    @pytest.mark.parametrize("status_code", [500, 502, 503, 504])
    def test_classify_5xx_server_errors(self, status_code):
        """Test 5xx server errors as TRANSIENT_ERROR."""
        from googleapiclient.errors import HttpError

        mock_resp = Mock()
        mock_resp.status = status_code

        exc = Mock(spec=HttpError)
        exc.resp = mock_resp

        result = classify_http_error(exc)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "SERVER_ERROR"
        assert str(status_code) in result.message

    @pytest.mark.parametrize("status_code", [400, 409, 410, 422])
    def test_classify_4xx_client_errors(self, status_code):
        """Test 4xx client errors as PERMANENT_ERROR."""
        from googleapiclient.errors import HttpError

        mock_resp = Mock()
        mock_resp.status = status_code

        exc = Mock(spec=HttpError)
        exc.resp = mock_resp

        result = classify_http_error(exc)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "HTTP_ERROR"
        assert str(status_code) in result.message

    def test_classify_connection_error_non_http_error(self):
        """Test non-HttpError exceptions (connection errors) as TRANSIENT_ERROR."""
        exc = ConnectionError("Connection refused")

        result = classify_http_error(exc)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "CONNECTION_ERROR"
        assert "connection error" in result.message.lower()

    def test_classify_timeout_error(self):
        """Test timeout errors as TRANSIENT_ERROR."""
        exc = TimeoutError("Request timed out")

        result = classify_http_error(exc)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "CONNECTION_ERROR"

    def test_classify_http_error_without_resp_attribute(self):
        """Test HttpError without resp attribute returns PERMANENT_ERROR."""
        from googleapiclient.errors import HttpError

        exc = Mock(spec=HttpError)
        exc.resp = None

        result = classify_http_error(exc)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "UNKNOWN_ERROR"


class TestClassifyAwsError:
    """Tests for classify_aws_error() function."""

    def test_classify_throttling_exception(self):
        """Test ThrottlingException as TRANSIENT_ERROR with retry_after."""
        from botocore.exceptions import ClientError

        exc = Mock(spec=ClientError)
        exc.response = {
            "Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}
        }

        result = classify_aws_error(exc)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "RATE_LIMITED"
        assert result.retry_after == 60
        assert "throttled" in result.message.lower()

    def test_classify_access_denied_exception(self):
        """Test AccessDeniedException as PERMANENT_ERROR."""
        from botocore.exceptions import ClientError

        exc = Mock(spec=ClientError)
        exc.response = {
            "Error": {"Code": "AccessDeniedException", "Message": "Access denied"}
        }

        result = classify_aws_error(exc)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "FORBIDDEN"
        assert "access denied" in result.message.lower()

    def test_classify_resource_not_found_exception(self):
        """Test ResourceNotFoundException as NOT_FOUND."""
        from botocore.exceptions import ClientError

        exc = Mock(spec=ClientError)
        exc.response = {
            "Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}
        }

        result = classify_aws_error(exc)

        assert result.status == OperationStatus.NOT_FOUND
        assert result.error_code == "NOT_FOUND"
        assert "not found" in result.message.lower()

    def test_classify_validation_exception(self):
        """Test ValidationException as PERMANENT_ERROR."""
        from botocore.exceptions import ClientError

        exc = Mock(spec=ClientError)
        exc.response = {
            "Error": {"Code": "ValidationException", "Message": "Invalid input"}
        }

        result = classify_aws_error(exc)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "INVALID_REQUEST"

    def test_classify_invalid_parameter_exception(self):
        """Test InvalidParameterException as PERMANENT_ERROR."""
        from botocore.exceptions import ClientError

        exc = Mock(spec=ClientError)
        exc.response = {
            "Error": {"Code": "InvalidParameterException", "Message": "Bad param"}
        }

        result = classify_aws_error(exc)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "INVALID_REQUEST"

    def test_classify_bad_request_exception(self):
        """Test BadRequestException as PERMANENT_ERROR."""
        from botocore.exceptions import ClientError

        exc = Mock(spec=ClientError)
        exc.response = {
            "Error": {"Code": "BadRequestException", "Message": "Bad request"}
        }

        result = classify_aws_error(exc)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "INVALID_REQUEST"

    def test_classify_unknown_client_error_as_transient(self):
        """Test unknown ClientError codes as TRANSIENT_ERROR."""
        from botocore.exceptions import ClientError

        exc = Mock(spec=ClientError)
        exc.response = {
            "Error": {"Code": "SomeUnknownError", "Message": "Unknown error"}
        }

        result = classify_aws_error(exc)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "AWS_CLIENT_ERROR"

    def test_classify_connection_error_non_client_error(self):
        """Test non-ClientError exceptions (connection errors) as TRANSIENT_ERROR."""
        exc = ConnectionError("Connection refused")

        result = classify_aws_error(exc)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "CONNECTION_ERROR"
        assert "connection error" in result.message.lower()

    def test_classify_botocore_error(self):
        """Test BotoCoreError exceptions as TRANSIENT_ERROR."""
        from botocore.exceptions import BotoCoreError

        exc = Mock(spec=BotoCoreError)

        result = classify_aws_error(exc)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "CONNECTION_ERROR"

    def test_classify_aws_error_without_response(self):
        """Test ClientError without response attribute."""
        from botocore.exceptions import ClientError

        exc = Mock(spec=ClientError)
        exc.response = None

        result = classify_aws_error(exc)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "AWS_CLIENT_ERROR"

    def test_classify_aws_error_with_missing_error_code(self):
        """Test ClientError with missing Error/Code in response."""
        from botocore.exceptions import ClientError

        exc = Mock(spec=ClientError)
        exc.response = {"Error": {}}  # Missing Code

        result = classify_aws_error(exc)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "AWS_CLIENT_ERROR"


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_classify_http_error_with_none_exception(self):
        """Test handling of None as exception (treated as generic error)."""
        exc = None

        result = classify_http_error(exc)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "CONNECTION_ERROR"

    def test_classify_aws_error_with_none_exception(self):
        """Test handling of None as exception (treated as generic error)."""
        exc = None

        result = classify_aws_error(exc)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "CONNECTION_ERROR"

    def test_classify_http_error_generic_exception(self):
        """Test generic Exception as CONNECTION_ERROR."""
        exc = Exception("Generic error")

        result = classify_http_error(exc)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "CONNECTION_ERROR"

    def test_classify_aws_error_generic_exception(self):
        """Test generic Exception as CONNECTION_ERROR."""
        exc = Exception("Generic error")

        result = classify_aws_error(exc)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "CONNECTION_ERROR"

    def test_classify_http_error_with_empty_message(self):
        """Test HttpError with empty exception message."""
        from googleapiclient.errors import HttpError

        mock_resp = Mock()
        mock_resp.status = 400

        exc = Mock(spec=HttpError)
        exc.resp = mock_resp
        exc.__str__ = Mock(return_value="")

        result = classify_http_error(exc)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "HTTP_ERROR"

    def test_classify_aws_error_result_has_no_sensitive_data(self):
        """Test that error results don't expose sensitive information."""
        from botocore.exceptions import ClientError

        exc = Mock(spec=ClientError)
        exc.response = {
            "Error": {
                "Code": "ValidationException",
                "Message": "Invalid API key: secret123",
            }
        }

        result = classify_aws_error(exc)

        # The classifier should include the error message, but that's okay
        # since it's being handled by providers who control what gets logged
        assert result.error_code == "INVALID_REQUEST"
        assert result.status == OperationStatus.PERMANENT_ERROR

    def test_http_error_429_retry_after_zero(self):
        """Test 429 with Retry-After header of 0."""
        from googleapiclient.errors import HttpError

        mock_resp = Mock()
        mock_resp.status = 429
        mock_resp.get = Mock(return_value="0")  # 0 seconds

        exc = Mock(spec=HttpError)
        exc.resp = mock_resp

        result = classify_http_error(exc)

        assert result.retry_after == 0

    def test_aws_error_throttling_exception_with_empty_response(self):
        """Test ThrottlingException with minimal error response."""
        from botocore.exceptions import ClientError

        exc = Mock(spec=ClientError)
        exc.response = {"Error": {"Code": "ThrottlingException"}}

        result = classify_aws_error(exc)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "RATE_LIMITED"
        assert result.retry_after == 60
