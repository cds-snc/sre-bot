from unittest.mock import patch
from integrations.aws.organizations import (
    list_organization_accounts,
    get_active_account_names,
    get_account_id_by_name,
    get_account_details,
    get_account_tags,
    healthcheck,
)

# Mock the ORG_ROLE_ARN since it's used in the function
ORG_ROLE_ARN = "arn:aws:iam::123456789012:role/OrganizationAccountAccessRole"


@patch("integrations.aws.organizations.ORG_ROLE_ARN", ORG_ROLE_ARN)
@patch("integrations.aws.organizations.execute_aws_api_call")
def test_list_organization_accounts_success(mock_execute_aws_api_call):
    # Mock return value
    mock_accounts = [
        {
            "Id": "123456789012",
            "Arn": "arn:aws:organizations::123456789012:account/o-exampleorgid/123456789012",
            "Email": "example@example.com",
            "Name": "ExampleAccount",
            "Status": "ACTIVE",
            "JoinedMethod": "INVITED",
            "JoinedTimestamp": "2022-09-20T15:09:16.541000+00:00",
        }
    ]

    # Mock the execute_aws_api_call function
    mock_execute_aws_api_call.return_value = mock_accounts

    # Execute the function
    result = list_organization_accounts()

    mock_execute_aws_api_call.assert_called_with(
        "organizations",
        "list_accounts",
        paginated=True,
        keys=["Accounts"],
        role_arn=ORG_ROLE_ARN,
    )
    # Verify the result
    assert result == mock_accounts


@patch("integrations.aws.organizations.execute_aws_api_call")
def test_list_organization_accounts_failure(mock_execute_aws_api_call):
    # Mock the execute_aws_api_call function to raise an exception
    mock_execute_aws_api_call.side_effect = Exception("Some AWS error")

    # Execute the function
    result = list_organization_accounts()

    # Verify the result
    assert result is False


@patch("integrations.aws.organizations.execute_aws_api_call")
def test_list_organization_accounts_empty(mock_execute_aws_api_call):
    # Mock return value with an empty list
    mock_execute_aws_api_call.return_value = []

    # Execute the function
    result = list_organization_accounts()

    # Verify the result
    assert result == []


@patch("integrations.aws.organizations.execute_aws_api_call")
def test_list_organization_accounts_pagination(mock_execute_aws_api_call):
    # Mock return value simulating a paginated response
    mock_accounts_page1 = [
        {
            "Id": "123456789012",
            "Arn": "arn:aws:organizations::123456789012:account/o-exampleorgid/123456789012",
            "Email": "example@example.com",
            "Name": "ExampleAccountPage1",
            "Status": "ACTIVE",
            "JoinedMethod": "INVITED",
            "JoinedTimestamp": "2022-09-20T15:09:16.541000+00:00",
        }
    ]
    mock_accounts_page2 = [
        {
            "Id": "234567890123",
            "Arn": "arn:aws:organizations::234567890123:account/o-exampleorgid/234567890123",
            "Email": "example2@example.com",
            "Name": "ExampleAccountPage2",
            "Status": "ACTIVE",
            "JoinedMethod": "INVITED",
            "JoinedTimestamp": "2022-10-20T15:09:16.541000+00:00",
        }
    ]

    mock_execute_aws_api_call.side_effect = [mock_accounts_page1, mock_accounts_page2]

    # Execute the function
    result = list_organization_accounts()

    # Verify the result
    assert result == mock_accounts_page1


@patch("integrations.aws.organizations.list_organization_accounts")
def test_get_active_account_names_success(mock_list_organization_accounts):
    # Mock return value
    mock_accounts = [
        {
            "Id": "123456789012",
            "Arn": "arn:aws:organizations::123456789012:account/o-exampleorgid/123456789012",
            "Email": "example@example.com",
            "Name": "ExampleAccount1",
            "Status": "ACTIVE",
            "JoinedMethod": "INVITED",
            "JoinedTimestamp": "2022-09-20T15:09:16.541000+00:00",
        },
        {
            "Id": "234567890123",
            "Arn": "arn:aws:organizations::234567890123:account/o-exampleorgid/234567890123",
            "Email": "example2@example.com",
            "Name": "ExampleAccount2",
            "Status": "SUSPENDED",
            "JoinedMethod": "CREATED",
            "JoinedTimestamp": "2021-01-15T12:00:00.000000+00:00",
        },
        {
            "Id": "345678901234",
            "Arn": "arn:aws:organizations::345678901234:account/o-exampleorgid/345678901234",
            "Email": "example3@example.com",
            "Name": "ExampleAccount3",
            "Status": "ACTIVE",
            "JoinedMethod": "INVITED",
            "JoinedTimestamp": "2023-02-15T12:00:00.000000+00:00",
        },
    ]

    mock_list_organization_accounts.return_value = mock_accounts

    # Execute the function
    result = get_active_account_names()

    # Verify the result
    assert result == ["ExampleAccount1", "ExampleAccount3"]


@patch("integrations.aws.organizations.list_organization_accounts")
def test_get_active_account_names_no_active_accounts(mock_list_organization_accounts):
    # Mock return value with no active accounts
    mock_accounts = [
        {
            "Id": "123456789012",
            "Arn": "arn:aws:organizations::123456789012:account/o-exampleorgid/123456789012",
            "Email": "example@example.com",
            "Name": "ExampleAccount1",
            "Status": "SUSPENDED",
            "JoinedMethod": "INVITED",
            "JoinedTimestamp": "2022-09-20T15:09:16.541000+00:00",
        }
    ]

    # Mock the list_organization_accounts function
    mock_list_organization_accounts.return_value = mock_accounts

    # Execute the function
    result = get_active_account_names()

    # Verify the result
    assert result == []


@patch("integrations.aws.organizations.list_organization_accounts")
def test_get_active_account_names_empty_response(mock_list_organization_accounts):
    # Mock return value with an empty list
    mock_list_organization_accounts.return_value = []

    # Execute the function
    result = get_active_account_names()

    # Verify the result
    assert result == []


@patch("integrations.aws.organizations.list_organization_accounts")
def test_get_active_account_names_none_response(mock_list_organization_accounts):
    # Mock return value as None
    mock_list_organization_accounts.return_value = None

    # Execute the function
    result = get_active_account_names()

    # Verify the result
    assert result == []


@patch("integrations.aws.organizations.ORG_ROLE_ARN", ORG_ROLE_ARN)
@patch("integrations.aws.organizations.execute_aws_api_call")
def test_get_account_details_success(mock_execute_aws_api_call):
    # Mock return value
    mock_account = {
        "Account": {
            "Id": "123456789012",
            "Arn": "arn:aws:organizations::123456789012:account/o-exampleorgid/123456789012",
            "Email": "example@example.com",
            "Name": "ExampleAccount",
            "Status": "ACTIVE",
            "JoinedMethod": "INVITED",
            "JoinedTimestamp": "2022-09-20T15:09:16.541000+00:00",
        }
    }

    # Mock the execute_aws_api_call function
    mock_execute_aws_api_call.return_value = mock_account

    # Execute the function
    result = get_account_details("123456789012")

    mock_execute_aws_api_call.assert_called_with(
        "organizations",
        "describe_account",
        role_arn=ORG_ROLE_ARN,
        AccountId="123456789012",
    )

    # Verify the result
    assert result == mock_account["Account"]


@patch("integrations.aws.organizations.ORG_ROLE_ARN", ORG_ROLE_ARN)
@patch("integrations.aws.organizations.execute_aws_api_call")
def test_get_account_details_empty_response(mock_execute_aws_api_call):
    # Mock empty response
    mock_execute_aws_api_call.return_value = {}

    # Execute the function
    result = get_account_details("123456789012")

    # Verify the result
    assert result == {}


# @patch("integrations.aws.organizations.ORG_ROLE_ARN", ORG_ROLE_ARN)
@patch("integrations.aws.organizations.execute_aws_api_call")
def test_get_account_details_exception(mock_execute_aws_api_call):
    # Mock exception
    mock_execute_aws_api_call.side_effect = Exception("AWS API Error")

    # Execute function and expect the handle_aws_api_errors decorator to catch the exception
    result = get_account_details("123456789012")

    # The decorator should return None when exception is caught
    assert result is False


# Adding tests for the get_account_tags function


@patch("integrations.aws.organizations.ORG_ROLE_ARN", ORG_ROLE_ARN)
@patch("integrations.aws.organizations.execute_aws_api_call")
def test_get_account_tags_success(mock_execute_aws_api_call):
    # Mock return value
    mock_tags = {
        "Tags": [
            {
                "Key": "business_unit",
                "Value": "Engineering",
            },
            {
                "Key": "product",
                "Value": "CloudServices",
            },
        ]
    }

    # Mock the execute_aws_api_call function
    mock_execute_aws_api_call.return_value = mock_tags

    # Execute the function
    result = get_account_tags("123456789012")

    mock_execute_aws_api_call.assert_called_with(
        "organizations",
        "list_tags_for_resource",
        role_arn=ORG_ROLE_ARN,
        ResourceId="123456789012",
    )

    # Verify the result
    assert result == mock_tags["Tags"]


@patch("integrations.aws.organizations.ORG_ROLE_ARN", ORG_ROLE_ARN)
@patch("integrations.aws.organizations.execute_aws_api_call")
def test_get_account_tags_empty_response(mock_execute_aws_api_call):
    # Mock empty response
    mock_execute_aws_api_call.return_value = {}

    # Execute the function
    result = get_account_tags("123456789012")

    # Verify the result
    assert result == []


@patch("integrations.aws.organizations.ORG_ROLE_ARN", ORG_ROLE_ARN)
@patch("integrations.aws.organizations.execute_aws_api_call")
def test_get_account_tags_exception(mock_execute_aws_api_call):
    # Mock exception
    mock_execute_aws_api_call.side_effect = Exception("AWS API Error")

    # Execute function and expect the handle_aws_api_errors decorator to catch the exception
    result = get_account_tags("123456789012")

    # The decorator should return None when exception is caught
    assert result is False


@patch("integrations.aws.organizations.list_organization_accounts")
def test_healthcheck_success(mock_list_organization_accounts):
    # Mock return value
    mock_accounts = [
        {
            "Id": "123456789012",
            "Arn": "arn:aws:organizations::123456789012:account/o-exampleorgid/123456789012",
            "Email": "example@example.com",
            "Name": "ExampleAccount1",
            "Status": "ACTIVE",
            "JoinedMethod": "INVITED",
            "JoinedTimestamp": "2022-09-20T15:09:16.541000+00:00",
        }
    ]

    # Mock the list_organization_accounts function
    mock_list_organization_accounts.return_value = mock_accounts

    # Execute the function
    result = healthcheck()

    # Verify the result
    assert result is True


@patch("integrations.aws.organizations.list_organization_accounts")
def test_healthcheck_empty_response(mock_list_organization_accounts):
    # Mock return value with an empty list
    mock_list_organization_accounts.return_value = []

    # Execute the function
    result = healthcheck()

    # Verify the result
    assert result is False


@patch("integrations.aws.organizations.list_organization_accounts")
def test_healthcheck_none_response(mock_list_organization_accounts):
    # Mock return value as None
    mock_list_organization_accounts.return_value = None

    # Execute the function
    result = healthcheck()

    # Verify the result
    assert result is False


@patch("integrations.aws.organizations.list_organization_accounts")
def test_healthcheck_exception(mock_list_organization_accounts):
    # Mock the list_organization_accounts function to raise an exception
    mock_list_organization_accounts.side_effect = Exception("Some AWS error")

    # Execute the function
    result = healthcheck()

    # Verify the result
    assert result is False


@patch("integrations.aws.organizations.list_organization_accounts")
def test_get_account_id_by_name_found(mock_list_organization_accounts):
    # Mock the list_organization_accounts function
    mock_list_organization_accounts.return_value = [
        {"Id": "123456789012", "Name": "TestAccount1"},
        {"Id": "234567890123", "Name": "TestAccount2"},
    ]

    account_id = get_account_id_by_name("TestAccount1")
    assert account_id == "123456789012"


@patch("integrations.aws.organizations.list_organization_accounts")
def test_get_account_id_by_name_not_found(mock_list_organization_accounts):
    # Mock the list_organization_accounts function
    mock_list_organization_accounts.return_value = [
        {"Id": "123456789012", "Name": "TestAccount1"},
        {"Id": "234567890123", "Name": "TestAccount2"},
    ]

    account_id = get_account_id_by_name("NonExistentAccount")
    assert account_id is None


@patch("integrations.aws.organizations.list_organization_accounts")
def test_get_account_id_by_name_empty_list(mock_list_organization_accounts):
    # Mock the list_organization_accounts function
    mock_list_organization_accounts.return_value = []

    account_id = get_account_id_by_name("TestAccount1")
    assert account_id is None


@patch("integrations.aws.organizations.list_organization_accounts")
def test_get_account_id_by_name_case_sensitivity(mock_list_organization_accounts):
    # Mock the list_organization_accounts function
    mock_list_organization_accounts.return_value = [
        {"Id": "123456789012", "Name": "TestAccount1"},
        {"Id": "234567890123", "Name": "testaccount1"},
    ]

    account_id = get_account_id_by_name("TestAccount1")
    assert account_id == "123456789012"
