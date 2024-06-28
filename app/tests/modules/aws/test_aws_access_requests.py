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
