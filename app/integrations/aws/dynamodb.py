import os
from integrations.aws.client import (
    execute_aws_api_call,
    handle_aws_api_errors,
)

client_config = dict(
    region_name=os.environ.get("AWS_REGION", "ca-central-1"),
)

if os.environ.get("PREFIX", None):
    client_config["endpoint_url"] = "http://dynamodb-local:8000"


@handle_aws_api_errors
def query(
    TableName,
    **kwargs,
):
    params = {
        "TableName": TableName,
    }
    if params:
        params.update(kwargs)
    response = execute_aws_api_call(
        "dynamodb", "query", paginated=True, client_config=client_config, **params
    )
    return response


@handle_aws_api_errors
def scan(TableName, **kwargs):
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
    return response


@handle_aws_api_errors
def put_item(TableName, **kwargs):
    params = {
        "TableName": TableName,
    }
    if kwargs:
        params.update(kwargs)
    response = execute_aws_api_call(
        "dynamodb", "put_item", client_config=client_config, **params
    )
    return response


@handle_aws_api_errors
def get_item(TableName, **kwargs):
    params = {
        "TableName": TableName,
    }
    if kwargs:
        params.update(kwargs)
    response = execute_aws_api_call(
        "dynamodb", "get_item", client_config=client_config, **params
    )
    if response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 200:
        return response


@handle_aws_api_errors
def update_item(TableName, **kwargs):
    params = {
        "TableName": TableName,
    }
    if kwargs:
        params.update(kwargs)
    response = execute_aws_api_call(
        "dynamodb", "update_item", client_config=client_config, **params
    )
    if response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 200:
        return response


@handle_aws_api_errors
def delete_item(TableName, **kwargs):
    params = {
        "TableName": TableName,
    }
    if kwargs:
        params.update(kwargs)
    response = execute_aws_api_call(
        "dynamodb", "delete_item", client_config=client_config, **params
    )
    return response


@handle_aws_api_errors
def list_tables(**kwargs):
    response = execute_aws_api_call(
        "dynamodb", "list_tables", client_config=client_config, **kwargs
    )
    return response
