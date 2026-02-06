"""Unit tests for AWS access requests handler."""

import pytest
from unittest.mock import patch
import datetime

from modules.aws import aws_access_requests


@pytest.mark.unit
@patch("modules.aws.aws_access_requests.dynamodb_client")
def test_should_return_false_when_no_access_record_exists(mock_client):
    """Test already_has_access returns False when no records exist."""
    # Arrange
    mock_client.query.return_value = {"Count": 0}

    # Act
    result = aws_access_requests.already_has_access("account-123", "user-123", "role")

    # Assert
    assert result is False
    mock_client.query.assert_called_once()


@pytest.mark.unit
@patch("modules.aws.aws_access_requests.dynamodb_client")
def test_should_return_false_when_record_expired(mock_client):
    """Test already_has_access returns False when record is expired."""
    # Arrange
    mock_client.query.return_value = {
        "Count": 1,
        "Items": [
            {
                "user_id": {"S": "user-123"},
                "access_type": {"S": "role"},
                "expired": {"BOOL": True},
                "created_at": {"N": str(datetime.datetime.now().timestamp())},
            }
        ],
    }

    # Act
    result = aws_access_requests.already_has_access("account-123", "user-123", "role")

    # Assert
    assert result is False


@pytest.mark.unit
@patch("modules.aws.aws_access_requests.dynamodb_client")
def test_should_return_minutes_when_valid_access_exists(mock_client):
    """Test already_has_access returns minutes remaining for valid access."""
    # Arrange
    now = datetime.datetime.now().timestamp()

    mock_client.query.return_value = {
        "Count": 1,
        "Items": [
            {
                "user_id": {"S": "user-123"},
                "access_type": {"S": "role"},
                "expired": {"BOOL": False},
                "created_at": {"N": str(now)},
            }
        ],
    }

    # Act
    result = aws_access_requests.already_has_access("account-123", "user-123", "role")

    # Assert
    assert isinstance(result, int)
    assert result > 0


@pytest.mark.unit
@patch("modules.aws.aws_access_requests.dynamodb_client")
def test_should_return_false_when_user_id_does_not_match(mock_client):
    """Test already_has_access returns False when user_id doesn't match."""
    # Arrange
    now = datetime.datetime.now().timestamp()

    mock_client.query.return_value = {
        "Count": 1,
        "Items": [
            {
                "user_id": {"S": "other-user"},
                "access_type": {"S": "role"},
                "expired": {"BOOL": False},
                "created_at": {"N": str(now)},
            }
        ],
    }

    # Act
    result = aws_access_requests.already_has_access("account-123", "user-123", "role")

    # Assert
    assert result is False


@pytest.mark.unit
@patch("modules.aws.aws_access_requests.dynamodb_client")
def test_should_return_false_when_access_type_does_not_match(mock_client):
    """Test already_has_access returns False when access_type doesn't match."""
    # Arrange
    now = datetime.datetime.now().timestamp()

    mock_client.query.return_value = {
        "Count": 1,
        "Items": [
            {
                "user_id": {"S": "user-123"},
                "access_type": {"S": "different-role"},
                "expired": {"BOOL": False},
                "created_at": {"N": str(now)},
            }
        ],
    }

    # Act
    result = aws_access_requests.already_has_access("account-123", "user-123", "role")

    # Assert
    assert result is False


@pytest.mark.unit
@patch("modules.aws.aws_access_requests.dynamodb_client")
def test_should_create_access_request_successfully(mock_client):
    """Test create_aws_access_request creates record and returns True."""
    # Arrange
    mock_client.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

    # Act
    result = aws_access_requests.create_aws_access_request(
        "account-123",
        "TestAccount",
        "user-123",
        "user@example.com",
        "role",
        "Test rationale",
    )

    # Assert
    assert result is True
    mock_client.put_item.assert_called_once()
    call_args = mock_client.put_item.call_args[1]
    assert call_args["TableName"] == "aws_access_requests"
    assert call_args["Item"]["account_id"]["S"] == "account-123"


@pytest.mark.unit
@patch("modules.aws.aws_access_requests.dynamodb_client")
def test_should_return_false_when_create_request_fails(mock_client):
    """Test create_aws_access_request returns False on error."""
    # Arrange
    mock_client.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 400}}

    # Act
    result = aws_access_requests.create_aws_access_request(
        "account-123",
        "TestAccount",
        "user-123",
        "user@example.com",
        "role",
        "Test rationale",
    )

    # Assert
    assert result is False


@pytest.mark.unit
@patch("modules.aws.aws_access_requests.dynamodb_client")
def test_should_expire_request_successfully(mock_client):
    """Test expire_request successfully expires a record."""
    # Arrange
    mock_client.update_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

    # Act
    result = aws_access_requests.expire_request("account-123", "1234567890")

    # Assert
    assert result is True
    mock_client.update_item.assert_called_once()


@pytest.mark.unit
@patch("modules.aws.aws_access_requests.dynamodb_client")
def test_should_return_false_when_expire_request_fails(mock_client):
    """Test expire_request returns False on error."""
    # Arrange
    mock_client.update_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 400}}

    # Act
    result = aws_access_requests.expire_request("account-123", "1234567890")

    # Assert
    assert result is False


@pytest.mark.unit
@patch("modules.aws.aws_access_requests.dynamodb_client")
def test_should_get_expired_requests_successfully(mock_client):
    """Test get_expired_requests returns list of expired requests."""
    # Arrange
    expired_time = datetime.datetime.now().timestamp() - (5 * 60 * 60)
    mock_client.scan.return_value = {
        "Items": [
            {
                "id": {"S": "req-123"},
                "account_id": {"S": "account-123"},
                "created_at": {"N": str(expired_time)},
            }
        ]
    }

    # Act
    result = aws_access_requests.get_expired_requests()

    # Assert
    assert isinstance(result, list)
    mock_client.scan.assert_called_once()


@pytest.mark.unit
@patch("modules.aws.aws_access_requests.dynamodb_client")
def test_should_return_empty_list_when_no_expired_requests(mock_client):
    """Test get_expired_requests returns empty list when no expired records."""
    # Arrange
    mock_client.scan.return_value = {"Items": []}

    # Act
    result = aws_access_requests.get_expired_requests()

    # Assert
    assert result == []


@pytest.mark.unit
@patch("modules.aws.aws_access_requests.dynamodb_client")
def test_should_get_active_requests_successfully(mock_client):
    """Test get_active_requests returns list of active requests."""
    # Arrange
    now = datetime.datetime.now().timestamp()
    mock_client.scan.return_value = {
        "Items": [
            {
                "id": {"S": "req-123"},
                "account_id": {"S": "account-123"},
                "created_at": {"N": str(now)},
                "expired": {"BOOL": False},
            }
        ]
    }

    # Act
    result = aws_access_requests.get_active_requests()

    # Assert
    assert isinstance(result, list)
    mock_client.scan.assert_called_once()


@pytest.mark.unit
@patch("modules.aws.aws_access_requests.dynamodb_client")
def test_should_return_empty_list_when_no_active_requests(mock_client):
    """Test get_active_requests returns empty list when no active records."""
    # Arrange
    mock_client.scan.return_value = {"Items": []}

    # Act
    result = aws_access_requests.get_active_requests()

    # Assert
    assert result == []
