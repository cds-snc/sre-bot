"""AWS DynamoDB API client"""

from core.config import settings
from core.logging import get_module_logger
from integrations.aws.client import (
    execute_aws_api_call,
    handle_aws_api_errors,
)

logger = get_module_logger()

client_config = dict(
    region_name=settings.aws.AWS_REGION,
)

if settings.PREFIX:
    client_config["endpoint_url"] = "http://dynamodb-local:8000"


@handle_aws_api_errors
def query(
    TableName,
    **kwargs,
):
    logger.debug("dynamodb_query_started", table=TableName)
    params = {
        "TableName": TableName,
    }
    if params:
        params.update(kwargs)
    response = execute_aws_api_call(
        "dynamodb", "query", paginated=True, client_config=client_config, **params
    )
    logger.debug(
        "dynamodb_query_completed",
        table=TableName,
        item_count=len(response) if response else 0,
    )
    return response


@handle_aws_api_errors
def scan(TableName, **kwargs):
    """Scan a DynamoDB table. Will return only the list of items found in the table that match the query."""
    logger.debug("dynamodb_scan_started", table=TableName)
    params = {
        "TableName": TableName,
    }
    if kwargs:
        params.update(kwargs)
    response = execute_aws_api_call(
        "dynamodb",
        "scan",
        paginated=True,
        keys=["Items"],
        client_config=client_config,
        **params,
    )
    logger.debug(
        "dynamodb_scan_completed",
        table=TableName,
        item_count=len(response) if response else 0,
    )
    return response


@handle_aws_api_errors
def put_item(TableName, **kwargs):
    logger.debug("dynamodb_put_item_started", table=TableName)
    params = {
        "TableName": TableName,
    }
    if kwargs:
        params.update(kwargs)
    response = execute_aws_api_call(
        "dynamodb", "put_item", client_config=client_config, **params
    )
    logger.debug("dynamodb_put_item_completed", table=TableName)
    return response


@handle_aws_api_errors
def get_item(TableName, **kwargs) -> dict:
    """Get an item from a DynamoDB table

    Reference: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb.html#DynamoDB.Client.get_item
    """
    logger.debug("dynamodb_get_item_started", table=TableName)
    params = {
        "TableName": TableName,
    }
    if kwargs:
        params.update(kwargs)
    response = execute_aws_api_call(
        "dynamodb", "get_item", client_config=client_config, **params
    )
    if response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 200:
        logger.debug(
            "dynamodb_get_item_completed",
            table=TableName,
            item_found=bool(response.get("Item")),
        )
        return response.get("Item")
    else:
        logger.warning(
            "dynamodb_get_item_failed",
            table=TableName,
            status_code=response.get("ResponseMetadata", {}).get("HTTPStatusCode"),
        )
        return None


@handle_aws_api_errors
def update_item(TableName, **kwargs):
    """Update an item in a DynamoDB table

    Args:
        TableName: str - The name of the table to update
        **kwargs: dict - The parameters to pass to the update_item call

    Returns:
        dict: Response from the AWS API call
    Reference: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb.html#DynamoDB.Client.update_item
    """
    logger.debug("dynamodb_update_item_started", table=TableName)
    params = {
        "TableName": TableName,
    }
    if kwargs:
        params.update(kwargs)
    response = execute_aws_api_call(
        "dynamodb", "update_item", client_config=client_config, **params
    )
    if response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 200:
        logger.debug("dynamodb_update_item_completed", table=TableName)
        return response
    else:
        logger.warning(
            "dynamodb_update_item_failed",
            table=TableName,
            status_code=response.get("ResponseMetadata", {}).get("HTTPStatusCode"),
        )


@handle_aws_api_errors
def delete_item(TableName, **kwargs):
    logger.debug("dynamodb_delete_item_started", table=TableName)
    params = {
        "TableName": TableName,
    }
    if kwargs:
        params.update(kwargs)
    response = execute_aws_api_call(
        "dynamodb", "delete_item", client_config=client_config, **params
    )
    logger.debug("dynamodb_delete_item_completed", table=TableName)
    return response


@handle_aws_api_errors
def list_tables(**kwargs):
    logger.debug("dynamodb_list_tables_started")
    response = execute_aws_api_call(
        "dynamodb", "list_tables", client_config=client_config, **kwargs
    )
    logger.debug(
        "dynamodb_list_tables_completed",
        table_count=len(response.get("TableNames", [])),
    )
    return response
