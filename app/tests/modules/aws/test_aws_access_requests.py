import datetime

from unittest.mock import ANY, MagicMock, patch

from modules.aws import aws_access_requests


@patch("modules.aws.aws_access_requests.dynamodb_client")
def test_already_has_access_returns_false_is_no_record_exists(client_mock):
    client_mock.query.return_value = {"Count": 0}
    assert (
        aws_access_requests.already_has_access(
            "test_account_id", "test_user_id", "test_access_type"
        )
        is False
    )


@patch("modules.aws.aws_access_requests.dynamodb_client")
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


@patch("modules.aws.aws_access_requests.dynamodb_client")
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


@patch("modules.aws.aws_access_requests.dynamodb_client")
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


@patch("modules.aws.aws_access_requests.dynamodb_client")
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


@patch("modules.aws.aws_access_requests.dynamodb_client")
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
            datetime.datetime.now(),
            datetime.datetime.now() + datetime.timedelta(hours=1),
        )
        is True
    )


@patch("modules.aws.aws_access_requests.dynamodb_client")
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
            datetime.datetime.now(),
            datetime.datetime.now() + datetime.timedelta(hours=1),
        )
        is False
    )


@patch("modules.aws.aws_access_requests.dynamodb_client")
def test_expire_request_expires_record_returns_true_if_response_is_200(
    client_mock,
):
    client_mock.update_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    assert aws_access_requests.expire_request("test_account_id", "test_user_id") is True


@patch("modules.aws.aws_access_requests.dynamodb_client")
def test_expire_request_expires_record_returns_false_if_response_is_not_200(
    client_mock,
):
    client_mock.update_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 500}}
    assert (
        aws_access_requests.expire_request("test_account_id", "test_user_id") is False
    )


@patch("modules.aws.aws_access_requests.dynamodb_client")
def test_get_expired_requests_returns_empty_list_if_no_records_exist(client_mock):
    client_mock.scan.return_value = {"Count": 0, "Items": []}
    assert aws_access_requests.get_expired_requests() == []


@patch("modules.aws.aws_access_requests.dynamodb_client")
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


@patch("modules.aws.aws_access_requests.dynamodb_client")
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


@patch("modules.aws.aws_access_requests.dynamodb_client")
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


@patch("modules.aws.aws_access_requests.dynamodb_client")
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


@patch("modules.aws.aws_access_requests.dynamodb_client")
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


def test_access_view_handler_returns_errors_with_rational_over_2000_characters():
    ack = MagicMock()
    body = build_body(rationale="a" * 2001)

    aws_access_requests.access_view_handler(ack, body, MagicMock(), MagicMock())
    ack.assert_called_with(
        response_action="errors",
        errors={"rationale": "Please use less than 2000 characters"},
    )


@patch("modules.aws.aws_access_requests.log_ops_message")
@patch("modules.aws.aws_access_requests.identity_store.get_user_id")
def test_access_view_handler_with_unknown_sso_user(
    get_user_id_mock, log_ops_message_mock
):
    ack = MagicMock()
    body = build_body()
    logger = MagicMock()
    client = MagicMock()

    client.users_info.return_value = {
        "user": {"id": "user_id", "profile": {"email": "email"}}
    }

    get_user_id_mock.return_value = None

    aws_access_requests.access_view_handler(ack, body, logger, client)
    ack.assert_called()
    client.users_info.assert_called_with(user="user_id")
    logger.info.assert_called_with(
        "aws_account_access_request",
        user_id="user_id",
        email="email",
        account_id="account_id",
        account_name="account",
        access_type="access_type",
        rationale="rationale",
    )
    log_ops_message_mock.assert_called_with(
        client,
        "<@user_id> (email) requested access to account (account_id) with access_type priviliges.\n\nRationale: rationale",
    )
    client.chat_postEphemeral.assert_called_with(
        channel="user_id",
        user="user_id",
        text="<@user_id> (email) is not registered with AWS SSO. Please contact your administrator.\n<@user_id> (email) n'est pas enregistré avec AWS SSO. SVP contactez votre administrateur.",
    )


@patch("modules.aws.aws_access_requests.log_ops_message")
@patch("modules.aws.aws_access_requests.identity_store.get_user_id")
@patch("modules.aws.aws_access_requests.already_has_access")
def test_access_view_handler_with_existing_access(
    already_has_access_mock, get_user_id_mock, log_ops_message_mock
):
    ack = MagicMock()
    body = build_body()
    logger = MagicMock()
    client = MagicMock()

    client.users_info.return_value = {
        "user": {"id": "user_id", "profile": {"email": "email"}}
    }

    get_user_id_mock.return_value = "aws_user_id"
    already_has_access_mock.return_value = 10

    aws_access_requests.access_view_handler(ack, body, logger, client)
    ack.assert_called()
    client.users_info.assert_called_with(user="user_id")
    logger.info.assert_called_with(
        "aws_account_access_request",
        user_id="user_id",
        email="email",
        account_id="account_id",
        account_name="account",
        access_type="access_type",
        rationale="rationale",
    )
    log_ops_message_mock.assert_called_with(
        client,
        "<@user_id> (email) requested access to account (account_id) with access_type priviliges.\n\nRationale: rationale",
    )
    client.chat_postEphemeral.assert_called_with(
        channel="user_id",
        user="user_id",
        text="You already have access to account (account_id) with access type access_type. Your access will expire in 10 minutes.",
    )


@patch("modules.aws.aws_access_requests.log_ops_message")
@patch("modules.aws.aws_access_requests.identity_store.get_user_id")
@patch("modules.aws.aws_access_requests.already_has_access")
@patch("modules.aws.aws_access_requests.create_aws_access_request")
@patch("modules.aws.aws_access_requests.sso_admin.create_account_assignment")
def test_access_view_handler_successful_access_request(
    add_permissions_for_user_mock,
    create_aws_access_request_mock,
    already_has_access_mock,
    get_user_id_mock,
    log_ops_message_mock,
):
    ack = MagicMock()
    body = build_body()
    logger = MagicMock()
    client = MagicMock()

    client.users_info.return_value = {
        "user": {"id": "user_id", "profile": {"email": "email"}}
    }

    get_user_id_mock.return_value = "aws_user_id"
    already_has_access_mock.return_value = False
    create_aws_access_request_mock.return_value = True
    add_permissions_for_user_mock.return_value = True

    aws_access_requests.access_view_handler(ack, body, logger, client)
    ack.assert_called()
    client.users_info.assert_called_with(user="user_id")
    logger.info.assert_called_with(
        "aws_account_access_request",
        user_id="user_id",
        email="email",
        account_id="account_id",
        account_name="account",
        access_type="access_type",
        rationale="rationale",
    )
    log_ops_message_mock.assert_called_with(
        client,
        "<@user_id> (email) requested access to account (account_id) with access_type priviliges.\n\nRationale: rationale",
    )
    client.chat_postEphemeral.assert_called_with(
        channel="user_id",
        user="user_id",
        text="Provisioning access_type access request for account (account_id). This can take a minute or two. Visit <https://cds-snc.awsapps.com/start#/|https://cds-snc.awsapps.com/start#/> to gain access.\nTraitement de la requête d'accès access_type pour le compte account (account_id) en cours. Cela peut prendre quelques minutes. Visitez <https://cds-snc.awsapps.com/start#/|https://cds-snc.awsapps.com/start#/> pour y accéder",
    )


@patch("modules.aws.aws_access_requests.log_ops_message")
@patch("modules.aws.aws_access_requests.identity_store.get_user_id")
@patch("modules.aws.aws_access_requests.already_has_access")
@patch("modules.aws.aws_access_requests.create_aws_access_request")
@patch("modules.aws.aws_access_requests.sso_admin.create_account_assignment")
def test_access_view_handler_failed_access_request(
    add_permissions_for_user_mock,
    create_aws_access_request_mock,
    already_has_access_mock,
    get_user_id_mock,
    log_ops_message_mock,
):
    ack = MagicMock()
    body = build_body()
    logger = MagicMock()
    client = MagicMock()

    client.users_info.return_value = {
        "user": {"id": "user_id", "profile": {"email": "email"}}
    }

    get_user_id_mock.return_value = "aws_user_id"
    already_has_access_mock.return_value = False
    create_aws_access_request_mock.return_value = True
    add_permissions_for_user_mock.return_value = False

    aws_access_requests.access_view_handler(ack, body, logger, client)
    ack.assert_called()
    client.users_info.assert_called_with(user="user_id")
    logger.info.assert_called_with(
        "aws_account_access_request",
        user_id="user_id",
        email="email",
        account_id="account_id",
        account_name="account",
        access_type="access_type",
        rationale="rationale",
    )
    log_ops_message_mock.assert_called_with(
        client,
        "<@user_id> (email) requested access to account (account_id) with access_type priviliges.\n\nRationale: rationale",
    )
    client.chat_postEphemeral.assert_called_with(
        channel="user_id",
        user="user_id",
        text="Failed to provision access_type access request for account (account_id). Please drop a note in the <#sre-and-tech-ops> channel.\nLa requête d'accès access_type pour account (account_id) a échouée. Envoyez une note sur le canal <#sre-and-tech-ops>",
    )


@patch("modules.aws.aws_access_requests.organizations.list_organization_accounts")
def test_request_access_modal(get_accounts_mock):
    get_accounts_mock.return_value = [{"Id": "id", "Name": "name"}]

    client = MagicMock()
    body = {"trigger_id": "trigger_id", "view": {"state": {"values": {}}}}

    aws_access_requests.request_access_modal(client, body)
    client.views_open.assert_called_with(
        trigger_id="trigger_id",
        view=ANY,
    )


def build_body(
    rationale="rationale",
    account="account",
    account_id="account_id",
    access_type="access_type",
):
    return {
        "view": {
            "state": {
                "values": {
                    "rationale": {"rationale": {"value": rationale}},
                    "account": {
                        "account": {
                            "selected_option": {
                                "text": {"text": account},
                                "value": account_id,
                            }
                        }
                    },
                    "access_type": {
                        "access_type": {"selected_option": {"value": access_type}}
                    },
                }
            }
        },
        "user": {"id": "user_id"},
    }
