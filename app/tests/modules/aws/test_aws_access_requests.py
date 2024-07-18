import datetime

from unittest.mock import patch

from modules.aws import aws_access_requests


@patch("modules.aws.aws_access_requests.client")
def test_already_has_access_returns_false_is_no_record_exists(client_mock):
    client_mock.query.return_value = {"Count": 0}
    assert (
        aws_access_requests.already_has_access(
            "test_account_id", "test_user_id", "test_access_type"
        )
        is False
    )


@patch("modules.aws.aws_access_requests.client")
def test_already_has_access_returns_false_is_record_exists_but_expired(client_mock):
    client_mock.query.return_value = {
        "Count": 1,
        "Items": [
            {
                "account_id": {"S": "test_account_id"},
                "user_id": {"S": "test_user_id"},
                "access_type": {"S": "test_access_type"},
                "expired": {"BOOL": True},
            }
        ],
    }
    assert (
        aws_access_requests.already_has_access(
            "test_account_id", "test_user_id", "test_access_type"
        )
        is False
    )


@patch("modules.aws.aws_access_requests.client")
def test_already_has_access_returns_false_if_records_does_not_match_user_id(
    client_mock,
):
    client_mock.query.return_value = {
        "Count": 1,
        "Items": [
            {
                "account_id": {"S": "test_account_id"},
                "user_id": {"S": "test_user_id_2"},
                "access_type": {"S": "test_access_type"},
                "expired": {"BOOL": False},
            }
        ],
    }
    assert (
        aws_access_requests.already_has_access(
            "test_account_id", "test_user_id", "test_access_type"
        )
        is False
    )


@patch("modules.aws.aws_access_requests.client")
def test_already_has_access_returns_false_if_records_does_not_match_access_type(
    client_mock,
):
    client_mock.query.return_value = {
        "Count": 1,
        "Items": [
            {
                "account_id": {"S": "test_account_id"},
                "user_id": {"S": "test_user_id"},
                "access_type": {"S": "test_access_type_2"},
                "expired": {"BOOL": False},
            }
        ],
    }
    assert (
        aws_access_requests.already_has_access(
            "test_account_id", "test_user_id", "test_access_type"
        )
        is False
    )


@patch("modules.aws.aws_access_requests.client")
def test_already_has_access_returns_minutes_remaining_until_expiry(client_mock):
    client_mock.query.return_value = {
        "Count": 1,
        "Items": [
            {
                "account_id": {"S": "test_account_id"},
                "user_id": {"S": "test_user_id"},
                "access_type": {"S": "test_access_type"},
                "expired": {"BOOL": False},
                "created_at": {
                    "N": str(datetime.datetime.now().timestamp() - (3 * 60 * 60))
                },
            }
        ],
    }
    assert (
        aws_access_requests.already_has_access(
            "test_account_id", "test_user_id", "test_access_type"
        )
        == 60
    )


@patch("modules.aws.aws_access_requests.client")
def test_create_aws_access_request_creates_record_and_returns_true_if_response_is_200(
    client_mock,
):
    client_mock.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    assert (
        aws_access_requests.create_aws_access_request(
            "test_account_id",
            "test_account_name",
            "test_user_id",
            "test_email",
            datetime.datetime.now(),
            datetime.datetime.now() + datetime.timedelta(hours=1),
            "test_access_type",
            "test_rationale",
        )
        is True
    )


@patch("modules.aws.aws_access_requests.client")
def test_create_aws_access_request_creates_record_and_returns_false_if_response_is_not_200(
    client_mock,
):
    client_mock.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 500}}
    assert (
        aws_access_requests.create_aws_access_request(
            "test_account_id",
            "test_account_name",
            "test_user_id",
            "test_email",
            datetime.datetime.now(),
            datetime.datetime.now() + datetime.timedelta(hours=1),
            "test_access_type",
            "test_rationale",
        )
        is False
    )


@patch("modules.aws.aws_access_requests.client")
def test_expire_request_expires_record_returns_true_if_response_is_200(
    client_mock,
):
    client_mock.update_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    assert aws_access_requests.expire_request("test_account_id", "test_user_id") is True


@patch("modules.aws.aws_access_requests.client")
def test_expire_request_expires_record_returns_false_if_response_is_not_200(
    client_mock,
):
    client_mock.update_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 500}}
    assert (
        aws_access_requests.expire_request("test_account_id", "test_user_id") is False
    )


@patch("modules.aws.aws_access_requests.client")
def test_get_expired_requests_returns_empty_list_if_no_records_exist(client_mock):
    client_mock.scan.return_value = {"Count": 0, "Items": []}
    assert aws_access_requests.get_expired_requests() == []


@patch("modules.aws.aws_access_requests.client")
def test_get_expired_requests_returns_list_of_expired_requests(client_mock):
    client_mock.scan.return_value = {
        "Count": 1,
        "Items": [
            {
                "account_id": {"S": "test_account_id"},
                "user_id": {"S": "test_user_id"},
                "access_type": {"S": "test_access_type"},
                "expired": {"BOOL": True},
            }
        ],
    }

    assert aws_access_requests.get_expired_requests() == [
        {
            "account_id": {"S": "test_account_id"},
            "user_id": {"S": "test_user_id"},
            "access_type": {"S": "test_access_type"},
            "expired": {"BOOL": True},
        }
    ]


@patch("modules.aws.aws_access_requests.client")
def test_get_active_requests(mock_dynamodb_scan):
    # Mock the current timestamp
    current_timestamp = datetime.datetime(2024, 1, 1).timestamp()

    # Define the mock response
    mock_response = {
        "Items": [
            {"id": {"S": "123"}, "end_date_time": {"S": "1720830150.452"}},
            {"id": {"S": "456"}, "end_date_time": {"S": "1720830150.999"}},
        ]
    }
    mock_dynamodb_scan.scan.return_value = mock_response

    # Call the function
    with patch("modules.aws.aws_access_requests.datetime") as mock_datetime:
        mock_datetime.datetime.now.return_value = datetime.datetime(2024, 1, 1)
        items = aws_access_requests.get_active_requests()

        # Assertions
    mock_dynamodb_scan.scan.assert_called_once_with(
        TableName="aws_access_requests",
        FilterExpression="end_date_time > :current_time",
        ExpressionAttributeValues={":current_time": {"S": str(current_timestamp)}},
    )
    assert items == mock_response["Items"]


@patch("modules.aws.aws_access_requests.client")
def test_get_active_requests_empty(mock_dynamodb_scan):
    # Mock the current timestamp
    current_timestamp = datetime.datetime(2024, 1, 1).timestamp()
    with patch("modules.aws.aws_access_requests.datetime") as mock_datetime:
        mock_datetime.datetime.now.return_value = datetime.datetime(2024, 1, 1)

        # Define the mock response
        mock_response = {"Items": []}
        mock_dynamodb_scan.scan.return_value = mock_response

        # Call the function
        items = aws_access_requests.get_active_requests()

        # Assertions
        mock_dynamodb_scan.scan.assert_called_once_with(
            TableName="aws_access_requests",
            FilterExpression="end_date_time > :current_time",
            ExpressionAttributeValues={":current_time": {"S": str(current_timestamp)}},
        )
        assert items == mock_response["Items"]


@patch("modules.aws.aws_access_requests.client")
def test_get_past_requests(mock_dynamodb_scan):
    # Mock the current timestamp
    current_timestamp = datetime.datetime(2024, 1, 1).timestamp()
    with patch("modules.aws.aws_access_requests.datetime") as mock_datetime:
        mock_datetime.datetime.now.return_value = datetime.datetime(2024, 1, 1)

        # Define the mock response
        mock_response = {
            "Items": [
                {"id": {"S": "123"}, "end_date_time": {"S": "1720830150.452"}},
                {"id": {"S": "456"}, "end_date_time": {"S": "1720830150.999"}},
            ]
        }
        mock_dynamodb_scan.scan.return_value = mock_response

        # Call the function
        items = aws_access_requests.get_past_requests()

        # Assertions
        mock_dynamodb_scan.scan.assert_called_once_with(
            TableName="aws_access_requests",
            FilterExpression="end_date_time < :current_time",
            ExpressionAttributeValues={":current_time": {"S": str(current_timestamp)}},
        )
        assert items == mock_response["Items"]


@patch("modules.aws.aws_access_requests.client")
def test_get_past_requests_empty(mock_dynamodb_scan):
    # Mock the current timestamp
    current_timestamp = datetime.datetime(2024, 1, 1).timestamp()
    with patch("modules.aws.aws_access_requests.datetime") as mock_datetime:
        mock_datetime.datetime.now.return_value = datetime.datetime(2024, 1, 1)

        # Define the mock response
        mock_response = {"Items": []}
        mock_dynamodb_scan.scan.return_value = mock_response

        # Call the function
        items = aws_access_requests.get_past_requests()

        # Assertions
        mock_dynamodb_scan.scan.assert_called_once_with(
            TableName="aws_access_requests",
            FilterExpression="end_date_time < :current_time",
            ExpressionAttributeValues={":current_time": {"S": str(current_timestamp)}},
        )
        assert items == mock_response["Items"]
