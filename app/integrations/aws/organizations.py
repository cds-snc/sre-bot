import os
import logging
from integrations.aws.client import execute_aws_api_call, handle_aws_api_errors

ORG_ROLE_ARN = os.environ.get("AWS_ORG_ACCOUNT_ROLE_ARN", "")

logger = logging.getLogger(__name__)


@handle_aws_api_errors
def list_organization_accounts():
    """Retrieves all accounts from the AWS Organization

    Returns:
        list: A list of account objects.
    """
    params = {"role_arn": ORG_ROLE_ARN}
    return execute_aws_api_call(
        "organizations", "list_accounts", paginated=True, keys=["Accounts"], **params
    )


def get_active_account_names():
    """Retrieves the names of all active accounts from the AWS Organization

    Returns:
        list: A list of account names.
    """
    response = list_organization_accounts()

    # Return a list of account names with 'Status' == 'ACTIVE'
    return (
        [account["Name"] for account in response if account.get("Status") == "ACTIVE"]
        if response
        else []
    )


def get_account_id_by_name(account_name):
    """Retrieves the account ID for a given account name.

    Args:
        account_name (str): The name of the account.

    Returns:
        str: The account ID.
    """
    response = list_organization_accounts()

    # Return the account ID for the account with the given name
    return next(
        (account["Id"] for account in response if account.get("Name") == account_name),
        None,
    )


@handle_aws_api_errors
def get_account_details(account_id) -> dict:
    """Retrieves the details for a given account ID.

    Args:
        account_id (str): The ID of the account.

    Returns:
        dict: The account details.
    """
    params = {"role_arn": ORG_ROLE_ARN, "AccountId": account_id}
    return execute_aws_api_call("organizations", "describe_account", **params).get(
        "Account", {}
    )


@handle_aws_api_errors
def get_account_tags(account_id) -> list:
    """Retrieves the tags for a given account ID.

    Args:
        account_id (str): The ID of the account.

    Returns:
        list: The account tags.
    """
    params = {"role_arn": ORG_ROLE_ARN, "ResourceId": account_id}
    return execute_aws_api_call(
        "organizations", "list_tags_for_resource", **params
    ).get("Tags", [])


def healthcheck():
    """Check the health of the AWS integration.

    Returns:
        bool: True if the integration is healthy, False otherwise.
    """
    healthy = False
    try:
        response = list_organization_accounts()
        healthy = True if response else False
        logger.info(f"AWS Organizations healthcheck result: {response}")
    except Exception as error:
        logger.error(f"AWS Organizations healthcheck failed: {error}")
    return healthy
