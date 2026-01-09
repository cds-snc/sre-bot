"""Unit tests for Google Workspace executor module."""

from unittest.mock import patch

import pytest

from infrastructure.clients.google_workspace.executor import (
    ERROR_CONFIG,
    _calculate_retry_delay,
    execute_google_api_call,
)
from infrastructure.operations.result import OperationResult


@pytest.mark.unit
class TestCalculateRetryDelay:
    """Test suite for _calculate_retry_delay function."""

    def test_rate_limit_delay(self):
        """Test delay calculation for rate limit errors (429)."""
        delay = _calculate_retry_delay(attempt=0, status_code=429)
        assert delay == float(ERROR_CONFIG["rate_limit_delay"])
        assert delay == 60.0

    def test_exponential_backoff_first_attempt(self):
        """Test exponential backoff for first retry attempt."""
        delay = _calculate_retry_delay(attempt=0, status_code=500)
        backoff_factor = float(ERROR_CONFIG["default_backoff_factor"])
        expected = backoff_factor * (2**0)
        assert delay == expected
        assert delay == 1.0

    def test_exponential_backoff_second_attempt(self):
        """Test exponential backoff for second retry attempt."""
        delay = _calculate_retry_delay(attempt=1, status_code=500)
        backoff_factor = float(ERROR_CONFIG["default_backoff_factor"])
        expected = backoff_factor * (2**1)
        assert delay == expected
        assert delay == 2.0

    def test_exponential_backoff_third_attempt(self):
        """Test exponential backoff for third retry attempt."""
        delay = _calculate_retry_delay(attempt=2, status_code=503)
        backoff_factor = float(ERROR_CONFIG["default_backoff_factor"])
        expected = backoff_factor * (2**2)
        assert delay == expected
        assert delay == 4.0


@pytest.mark.unit
class TestExecuteGoogleApiCall:
    """Test suite for execute_google_api_call function."""

    def test_successful_call(self, make_mock_request):
        """Test successful API call execution."""
        expected_data = {"id": "123", "name": "Test User"}
        api_callable = make_mock_request(return_value=expected_data).execute

        result = execute_google_api_call("test_operation", api_callable)

        assert result.is_success
        assert result.data == expected_data
        assert "test_operation succeeded" in result.message

    def test_successful_call_with_operation_result(self, make_mock_request):
        """Test API call that returns OperationResult is propagated."""
        inner_result = OperationResult.success(
            data={"id": "456"}, message="Inner success"
        )
        api_callable = make_mock_request(return_value=inner_result).execute

        result = execute_google_api_call("test_operation", api_callable)

        assert result.is_success
        assert result.data == {"id": "456"}
        assert result.message == "Inner success"

    def test_retryable_error_succeeds_on_retry(
        self, make_mock_request, mock_google_api_error
    ):
        """Test that retryable errors are retried and eventually succeed."""
        error = mock_google_api_error(status=500, reason="Internal Server Error")
        success_data = {"id": "789"}

        # First call fails, second succeeds
        api_callable = make_mock_request(side_effect=[error, success_data]).execute

        with patch("infrastructure.clients.google_workspace.executor.time.sleep"):
            result = execute_google_api_call("test_operation", api_callable)

        assert result.is_success
        assert result.data == success_data

    def test_rate_limit_error_uses_correct_delay(
        self, make_mock_request, mock_google_api_error
    ):
        """Test that rate limit errors use the configured delay."""
        error = mock_google_api_error(status=429, reason="Rate Limit Exceeded")
        success_data = {"id": "101"}

        api_callable = make_mock_request(side_effect=[error, success_data]).execute

        with patch(
            "infrastructure.clients.google_workspace.executor.time.sleep"
        ) as mock_sleep:
            result = execute_google_api_call("test_operation", api_callable)

        assert result.is_success
        mock_sleep.assert_called_once_with(60.0)

    def test_non_retryable_error_fails_immediately(
        self, make_mock_request, mock_google_api_error
    ):
        """Test that non-retryable errors fail without retry."""
        error = mock_google_api_error(status=404, reason="Not Found")
        api_callable = make_mock_request(raise_error=error).execute

        result = execute_google_api_call("test_operation", api_callable)

        assert not result.is_success
        assert result.error_code == "GOOGLE_API_ERROR_404"
        assert "Not Found" in result.message

    def test_max_retries_exhausted(self, make_mock_request, mock_google_api_error):
        """Test that API call fails after exhausting max retries."""
        error = mock_google_api_error(status=500, reason="Internal Server Error")
        api_callable = make_mock_request(raise_error=error).execute

        with patch("infrastructure.clients.google_workspace.executor.time.sleep"):
            result = execute_google_api_call(
                "test_operation", api_callable, max_retries=2
            )

        assert not result.is_success
        assert result.error_code == "GOOGLE_API_ERROR_500"
        assert "Internal Server Error" in result.message

    def test_custom_max_retries(self, make_mock_request, mock_google_api_error):
        """Test that custom max_retries parameter is respected."""
        error = mock_google_api_error(status=503, reason="Service Unavailable")
        success_data = {"id": "202"}

        # Fail 4 times, succeed on 5th (max_retries=4 means 5 total attempts)
        api_callable = make_mock_request(
            side_effect=[error, error, error, error, success_data]
        ).execute

        with patch("infrastructure.clients.google_workspace.executor.time.sleep"):
            result = execute_google_api_call(
                "test_operation", api_callable, max_retries=4
            )

        assert result.is_success
        assert result.data == success_data

    def test_all_retryable_status_codes(self, make_mock_request, mock_google_api_error):
        """Test that all configured retryable status codes are retried."""
        retryable_codes = ERROR_CONFIG["retry_errors"]
        success_data = {"id": "303"}

        for status_code in retryable_codes:
            error = mock_google_api_error(
                status=status_code, reason=f"Error {status_code}"
            )
            api_callable = make_mock_request(side_effect=[error, success_data]).execute

            with patch("infrastructure.clients.google_workspace.executor.time.sleep"):
                result = execute_google_api_call(
                    f"test_operation_{status_code}", api_callable
                )

            assert result.is_success, f"Status code {status_code} should be retryable"

    def test_non_http_error_exception(self, make_mock_request):
        """Test handling of non-HttpError exceptions."""
        error = ValueError("Invalid parameter")
        api_callable = make_mock_request(raise_error=error).execute

        result = execute_google_api_call("test_operation", api_callable)

        assert not result.is_success
        assert result.error_code == "GOOGLE_API_ERROR"
        assert "Invalid parameter" in result.message

    def test_exponential_backoff_progression(
        self, make_mock_request, mock_google_api_error
    ):
        """Test that exponential backoff increases correctly across retries."""
        error = mock_google_api_error(status=502, reason="Bad Gateway")
        success_data = {"id": "404"}

        # Fail 3 times, succeed on 4th
        api_callable = make_mock_request(
            side_effect=[error, error, error, success_data]
        ).execute

        with patch(
            "infrastructure.clients.google_workspace.executor.time.sleep"
        ) as mock_sleep:
            result = execute_google_api_call("test_operation", api_callable)

        assert result.is_success
        # Verify exponential backoff: 1.0, 2.0, 4.0
        assert mock_sleep.call_count == 3
        delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0, 4.0]

    def test_zero_max_retries(self, make_mock_request, mock_google_api_error):
        """Test that max_retries=0 means one attempt only."""
        error = mock_google_api_error(status=500, reason="Internal Server Error")
        api_callable = make_mock_request(raise_error=error).execute

        result = execute_google_api_call("test_operation", api_callable, max_retries=0)

        assert not result.is_success
        assert result.error_code == "GOOGLE_API_ERROR_500"
