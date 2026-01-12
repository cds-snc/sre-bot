"""Unit tests for batch_executor module."""

import time
from unittest.mock import Mock

import pytest

from infrastructure.clients.google_workspace.batch_executor import execute_batch_request
from infrastructure.operations.result import OperationResult, OperationStatus


@pytest.mark.unit
class TestExecuteBatchRequest:
    """Test execute_batch_request function."""

    def test_batch_request_all_successful(self, mock_google_service):
        """Test batch request with all successful responses."""
        # Arrange
        requests = [
            ("req1", Mock()),
            ("req2", Mock()),
            ("req3", Mock()),
        ]

        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        def batch_execute():
            cb = callback_holder["callback"]
            # Simulate all successful responses
            cb("req1", {"id": "1", "data": "response1"}, None)
            cb("req2", {"id": "2", "data": "response2"}, None)
            cb("req3", {"id": "3", "data": "response3"}, None)

        mock_batch = Mock()
        mock_batch.execute = batch_execute
        mock_batch.add = Mock()

        mock_google_service.new_batch_http_request.side_effect = capture_callback

        # Act
        result = execute_batch_request(mock_google_service, requests)

        # Assert
        assert result.is_success
        assert result.data["results"]["req1"] == {"id": "1", "data": "response1"}
        assert result.data["results"]["req2"] == {"id": "2", "data": "response2"}
        assert result.data["results"]["req3"] == {"id": "3", "data": "response3"}
        assert len(result.data["errors"]) == 0
        assert result.data["summary"]["total"] == 3
        assert result.data["summary"]["successful"] == 3
        assert result.data["summary"]["failed"] == 0
        assert result.data["summary"]["success_rate"] == 1.0

    def test_batch_request_with_errors(self, mock_google_service):
        """Test batch request with some errors."""
        # Arrange
        requests = [
            ("req1", Mock()),
            ("req2", Mock()),
            ("req3", Mock()),
        ]

        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        def batch_execute():
            cb = callback_holder["callback"]
            # First request succeeds
            cb("req1", {"id": "1", "data": "response1"}, None)
            # Second request fails
            error = Exception("Not found")
            error.code = 404
            cb("req2", None, error)
            # Third request succeeds
            cb("req3", {"id": "3", "data": "response3"}, None)

        mock_batch = Mock()
        mock_batch.execute = batch_execute
        mock_batch.add = Mock()

        mock_google_service.new_batch_http_request.side_effect = capture_callback

        # Act
        result = execute_batch_request(mock_google_service, requests)

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "BATCH_ERRORS"
        assert len(result.data["results"]) == 2
        assert len(result.data["errors"]) == 1
        assert "req2" in result.data["errors"]
        assert result.data["errors"]["req2"]["error_code"] == 404
        assert "Not found" in result.data["errors"]["req2"]["message"]
        assert result.data["summary"]["total"] == 3
        assert result.data["summary"]["successful"] == 2
        assert result.data["summary"]["failed"] == 1
        assert result.data["summary"]["success_rate"] == pytest.approx(2 / 3)

    def test_batch_request_with_operation_result_response_success(
        self, mock_google_service
    ):
        """Test batch request when callback receives OperationResult responses (success)."""
        # Arrange
        requests = [
            ("req1", Mock()),
            ("req2", Mock()),
        ]

        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        def batch_execute():
            cb = callback_holder["callback"]
            # Response is an OperationResult (success)
            cb(
                "req1",
                OperationResult.success(data={"user": "user1@example.com"}),
                None,
            )
            cb(
                "req2",
                OperationResult.success(data={"user": "user2@example.com"}),
                None,
            )

        mock_batch = Mock()
        mock_batch.execute = batch_execute
        mock_batch.add = Mock()

        mock_google_service.new_batch_http_request.side_effect = capture_callback

        # Act
        result = execute_batch_request(mock_google_service, requests)

        # Assert
        assert result.is_success
        assert result.data["results"]["req1"] == {"user": "user1@example.com"}
        assert result.data["results"]["req2"] == {"user": "user2@example.com"}
        assert len(result.data["errors"]) == 0

    def test_batch_request_with_operation_result_response_failure(
        self, mock_google_service
    ):
        """Test batch request when callback receives OperationResult responses (failure)."""
        # Arrange
        requests = [
            ("req1", Mock()),
            ("req2", Mock()),
        ]

        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        def batch_execute():
            cb = callback_holder["callback"]
            # First succeeds
            cb(
                "req1",
                OperationResult.success(data={"user": "user1@example.com"}),
                None,
            )
            # Second fails (OperationResult with error)
            cb(
                "req2",
                OperationResult.permanent_error(
                    message="User not found", error_code="NOT_FOUND"
                ),
                None,
            )

        mock_batch = Mock()
        mock_batch.execute = batch_execute
        mock_batch.add = Mock()

        mock_google_service.new_batch_http_request.side_effect = capture_callback

        # Act
        result = execute_batch_request(mock_google_service, requests)

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR
        assert len(result.data["results"]) == 1
        assert len(result.data["errors"]) == 1
        assert "req2" in result.data["errors"]
        assert result.data["errors"]["req2"]["message"] == "User not found"
        assert result.data["errors"]["req2"]["error_code"] == "NOT_FOUND"

    def test_batch_request_with_exception_without_code_attribute(
        self, mock_google_service
    ):
        """Test batch request when exception doesn't have a code attribute."""
        # Arrange
        requests = [("req1", Mock())]

        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        def batch_execute():
            cb = callback_holder["callback"]
            # Exception without code attribute
            error = ValueError("Something went wrong")
            cb("req1", None, error)

        mock_batch = Mock()
        mock_batch.execute = batch_execute
        mock_batch.add = Mock()

        mock_google_service.new_batch_http_request.side_effect = capture_callback

        # Act
        result = execute_batch_request(mock_google_service, requests)

        # Assert
        assert not result.is_success
        assert "req1" in result.data["errors"]
        assert result.data["errors"]["req1"]["error_code"] == "BATCH_ITEM_ERROR"
        assert "Something went wrong" in result.data["errors"]["req1"]["message"]

    def test_batch_execution_fails_completely(self, mock_google_service):
        """Test when batch.execute() itself throws an exception."""
        # Arrange
        requests = [("req1", Mock()), ("req2", Mock())]

        mock_batch = Mock()
        mock_batch.execute.side_effect = RuntimeError("Batch execution failed")
        mock_batch.add = Mock()

        mock_google_service.new_batch_http_request.return_value = mock_batch

        # Act
        result = execute_batch_request(mock_google_service, requests)

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "BATCH_EXECUTION_ERROR"
        assert "Batch execution failed" in result.message

    def test_batch_request_with_custom_callback(self, mock_google_service):
        """Test batch request with custom callback function."""
        # Arrange
        requests = [("req1", Mock()), ("req2", Mock())]

        custom_callback_calls = []

        def custom_callback(request_id, response, exception):
            custom_callback_calls.append(
                {"request_id": request_id, "response": response, "exception": exception}
            )

        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        def batch_execute():
            cb = callback_holder["callback"]
            cb("req1", {"data": "response1"}, None)
            cb("req2", {"data": "response2"}, None)

        mock_batch = Mock()
        mock_batch.execute = batch_execute
        mock_batch.add = Mock()

        mock_google_service.new_batch_http_request.side_effect = capture_callback

        # Act
        result = execute_batch_request(mock_google_service, requests, custom_callback)

        # Assert
        # Custom callback should have been called twice
        assert len(custom_callback_calls) == 2
        assert custom_callback_calls[0]["request_id"] == "req1"
        assert custom_callback_calls[1]["request_id"] == "req2"
        # When using custom callback, no results are collected by default callback
        # The custom callback is responsible for handling results
        assert result.is_success

    def test_batch_request_adds_all_requests_to_batch(self, mock_google_service):
        """Test that all requests are added to the batch."""
        # Arrange
        mock_request_1 = Mock()
        mock_request_2 = Mock()
        mock_request_3 = Mock()
        requests = [
            ("req1", mock_request_1),
            ("req2", mock_request_2),
            ("req3", mock_request_3),
        ]

        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        def batch_execute():
            cb = callback_holder["callback"]
            cb("req1", {}, None)
            cb("req2", {}, None)
            cb("req3", {}, None)

        mock_batch = Mock()
        mock_batch.execute = batch_execute
        mock_batch.add = Mock()

        mock_google_service.new_batch_http_request.side_effect = capture_callback

        # Act
        execute_batch_request(mock_google_service, requests)

        # Assert
        assert mock_batch.add.call_count == 3
        mock_batch.add.assert_any_call(mock_request_1, request_id="req1")
        mock_batch.add.assert_any_call(mock_request_2, request_id="req2")
        mock_batch.add.assert_any_call(mock_request_3, request_id="req3")

    def test_batch_request_empty_requests_list(self, mock_google_service):
        """Test batch request with empty requests list."""
        # Arrange
        requests = []

        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        def batch_execute():
            # No callbacks
            pass

        mock_batch = Mock()
        mock_batch.execute = batch_execute
        mock_batch.add = Mock()

        mock_google_service.new_batch_http_request.side_effect = capture_callback

        # Act
        result = execute_batch_request(mock_google_service, requests)

        # Assert
        assert result.is_success
        assert result.data["summary"]["total"] == 0
        assert result.data["summary"]["successful"] == 0
        assert result.data["summary"]["failed"] == 0
        assert result.data["summary"]["success_rate"] == 0

    def test_batch_request_error_includes_timestamp(self, mock_google_service):
        """Test that error entries include a timestamp."""
        # Arrange
        requests = [("req1", Mock())]

        callback_holder = {}

        def capture_callback(callback):
            callback_holder["callback"] = callback
            return mock_batch

        def batch_execute():
            cb = callback_holder["callback"]
            error = Exception("Test error")
            error.code = 500
            cb("req1", None, error)

        mock_batch = Mock()
        mock_batch.execute = batch_execute
        mock_batch.add = Mock()

        mock_google_service.new_batch_http_request.side_effect = capture_callback

        # Act
        before_time = time.time()
        result = execute_batch_request(mock_google_service, requests)
        after_time = time.time()

        # Assert
        assert "req1" in result.data["errors"]
        assert "timestamp" in result.data["errors"]["req1"]
        timestamp = result.data["errors"]["req1"]["timestamp"]
        assert before_time <= timestamp <= after_time
