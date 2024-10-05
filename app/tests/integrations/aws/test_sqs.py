from unittest.mock import patch

# Import the functions to test
from integrations.aws.sqs import (
    get_queue_url,
    send_message,
    receive_message,
    delete_message,
)


@patch("integrations.aws.sqs.execute_aws_api_call")
def test_get_queue_url(mock_execute_aws_api_call):
    # Arrange
    queue_name = "test-queue"
    queue_name = "sre-bot-fifo-queue.fifo"
    expected_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"

    # Mock the execute_aws_api_call function
    mock_execute_aws_api_call.return_value = {
        "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    }

    # Act
    result = get_queue_url(queue_name)

    # Assert
    mock_execute_aws_api_call.assert_called_once_with(
        "sqs", "get_queue_url", QueueName=queue_name
    )
    assert result == expected_url


@patch("integrations.aws.sqs.execute_aws_api_call")
def test_get_queue_url_invalid_queue_name(mock_execute_api_call):
    # Arrange
    queue_name = ""  # Invalid queue name
    mock_execute_api_call.return_value = False

    result = get_queue_url(queue_name)
    # Act & Assert
    mock_execute_api_call.assert_called_once_with(
        "sqs", "get_queue_url", QueueName=queue_name
    )
    assert result is False


@patch("integrations.aws.sqs.execute_aws_api_call")
def test_send_message(mock_execute_aws_api_call):
    # Arrange
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    message_body = "Test message"
    message_group_id = "test-group"
    expected_response = {"MessageId": "abc123"}

    # Mock the execute_aws_api_call function
    mock_execute_aws_api_call.return_value = expected_response

    # Act
    result = send_message(queue_url, message_body, message_group_id)

    # Assert
    mock_execute_aws_api_call.assert_called_once_with(
        "sqs",
        "send_message",
        QueueUrl=queue_url,
        MessageBody=message_body,
        MessageGroupId=message_group_id,
    )
    assert result == expected_response


@patch("integrations.aws.sqs.execute_aws_api_call")
def test_receive_message(mock_execute_aws_api_call):
    # Arrange
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    max_number_of_messages = 5
    wait_time_seconds = 20
    expected_messages = {
        "Messages": [
            {
                "MessageId": "msg1",
                "ReceiptHandle": "handle1",
                "Body": "Message 1",
            },
            {
                "MessageId": "msg2",
                "ReceiptHandle": "handle2",
                "Body": "Message 2",
            },
        ]
    }

    # Mock the execute_aws_api_call function
    mock_execute_aws_api_call.return_value = expected_messages

    # Act
    result = receive_message(queue_url, max_number_of_messages, wait_time_seconds)

    # Assert
    mock_execute_aws_api_call.assert_called_once_with(
        "sqs",
        "receive_message",
        QueueUrl=queue_url,
        MaxNumberOfMessages=max_number_of_messages,
        WaitTimeSeconds=wait_time_seconds,
    )
    assert result == expected_messages


@patch("integrations.aws.sqs.execute_aws_api_call")
def test_delete_message(mock_execute_api_call):
    # Arrange
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    receipt_handle = "handle1"
    expected_response = {"ResponseMetadata": {"HTTPStatusCode": 200}}

    # Mock the execute_aws_api_call function
    mock_execute_api_call.return_value = expected_response

    # Act
    result = delete_message(queue_url, receipt_handle)

    # Assert
    mock_execute_api_call.assert_called_once_with(
        "sqs",
        "delete_message",
        QueueUrl=queue_url,
        ReceiptHandle=receipt_handle,
    )
    assert result == expected_response


@patch("integrations.aws.sqs.execute_aws_api_call")
def test_send_message_api_failure(mock_execute_api_call):
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    message_body = "Test message"
    message_group_id = "test-group"
    mock_execute_api_call.side_effect = Exception("AWS API call failed")

    result = send_message(queue_url, message_body, message_group_id)

    mock_execute_api_call.assert_called_once_with(
        "sqs",
        "send_message",
        QueueUrl=queue_url,
        MessageBody=message_body,
        MessageGroupId=message_group_id,
    )
    assert result is False


@patch("integrations.aws.sqs.execute_aws_api_call")
def test_receive_message_empty_queue(mock_execute_api_call):
    # Arrange
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    # Simulate empty queue by returning an empty dict
    mock_execute_api_call.return_value = {}

    # Act
    result = receive_message(queue_url)

    # Assert
    mock_execute_api_call.assert_called_once_with(
        "sqs",
        "receive_message",
        QueueUrl=queue_url,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=10,
    )
    assert result == {}


@patch("integrations.aws.sqs.execute_aws_api_call")
def test_delete_message_invalid_receipt_handle(mock_execute_api_call):
    # Arrange
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    receipt_handle = "invalid-receipt-handle"
    mock_execute_api_call.side_effect = Exception("Invalid receipt handle")

    # Act & Assert
    result = delete_message(queue_url, receipt_handle)
    assert result is False
    mock_execute_api_call.assert_called_once_with(
        "sqs",
        "delete_message",
        QueueUrl=queue_url,
        ReceiptHandle=receipt_handle,
    )


@patch("integrations.aws.sqs.execute_aws_api_call")
def test_send_message_missing_parameters(mock_execute_api_call):
    # Arrange
    queue_url = None  # Missing queue URL
    message_body = None  # Missing message body
    message_group_id = None  # Missing message group ID
    mock_execute_api_call.side_effect = ValueError("Missing required parameters")

    # Act & Assert
    result = send_message(queue_url, message_body, message_group_id)
    assert result is False
    mock_execute_api_call.assert_called_once_with(
        "sqs",
        "send_message",
        QueueUrl=queue_url,
        MessageBody=message_body,
        MessageGroupId=message_group_id,
    )


@patch("integrations.aws.sqs.execute_aws_api_call")
def test_receive_message_invalid_wait_time(mock_execute_api_call):
    # Arrange
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    max_number_of_messages = 5
    wait_time_seconds = -1  # Invalid wait time
    mock_execute_api_call.side_effect = Exception("WaitTimeSeconds must be >= 0")

    # Act & Assert
    result = receive_message(queue_url, max_number_of_messages, wait_time_seconds)
    assert result is False
    mock_execute_api_call.assert_called_once_with(
        "sqs",
        "receive_message",
        QueueUrl=queue_url,
        MaxNumberOfMessages=max_number_of_messages,
        WaitTimeSeconds=wait_time_seconds,
    )


@patch("integrations.aws.sqs.execute_aws_api_call")
def test_get_queue_url_api_failure(mock_execute_api_call):
    # Arrange
    queue_name = "test-queue"
    mock_execute_api_call.side_effect = Exception("AWS service unavailable")

    # Act & Assert
    result = get_queue_url(queue_name)
    assert result is False
    mock_execute_api_call.assert_called_once_with(
        "sqs", "get_queue_url", QueueName=queue_name
    )


@patch("integrations.aws.sqs.execute_aws_api_call")
def test_delete_message_no_receipt_handle(mock_execute_api_call):
    # Arrange
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    receipt_handle = None  # Missing receipt handle

    # Act & Assert
    delete_message(queue_url, receipt_handle)
    mock_execute_api_call.assert_called_once_with(
        "sqs",
        "delete_message",
        QueueUrl=queue_url,
        ReceiptHandle=receipt_handle,
    )


@patch("integrations.aws.sqs.execute_aws_api_call")
def test_receive_message_max_number_exceeds_limit(mock_execute_api_call):
    # Arrange
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    max_number_of_messages = 11  # Exceeds SQS limit of 10
    mock_execute_api_call.side_effect = Exception(
        "MaxNumberOfMessages cannot be greater than 10"
    )

    # Act & Assert
    result = receive_message(queue_url, max_number_of_messages)
    assert result is False
    mock_execute_api_call.assert_called_once_with(
        "sqs",
        "receive_message",
        QueueUrl=queue_url,
        MaxNumberOfMessages=max_number_of_messages,
        WaitTimeSeconds=10,
    )


@patch("integrations.aws.sqs.execute_aws_api_call")
def test_send_message_large_message_body(mock_execute_api_call):
    # Arrange
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    message_body = "x" * 300000  # Exceeds SQS limit of 256 KB
    message_group_id = "test-group"
    mock_execute_api_call.side_effect = Exception("Message body exceeds maximum size")

    # Act & Assert
    result = send_message(queue_url, message_body, message_group_id)
    assert result is False
    mock_execute_api_call.assert_called_once_with(
        "sqs",
        "send_message",
        QueueUrl=queue_url,
        MessageBody=message_body,
        MessageGroupId=message_group_id,
    )


@patch("integrations.aws.sqs.execute_aws_api_call")
def test_send_message_with_message_attributes(mock_execute_api_call):
    # Arrange
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"
    message_body = "Test message with attributes"
    message_group_id = "test-group"
    expected_response = {"MessageId": "def456"}
    mock_execute_api_call.return_value = expected_response

    result = send_message(
        queue_url,
        message_body,
        message_group_id,
    )

    # Assert
    mock_execute_api_call.assert_called_once_with(
        "sqs",
        "send_message",
        QueueUrl=queue_url,
        MessageBody=message_body,
        MessageGroupId=message_group_id,
    )
    assert result == expected_response