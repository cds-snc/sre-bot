import os
from integrations.aws.client import (
    execute_aws_api_call,
    handle_aws_api_errors,
    CLIENT_DEFAULTS as client_config,
)

if os.environ.get("PREFIX", None):
    client_config["endpoint_url"] = "http://dynamodb-local:8000"


@handle_aws_api_errors
def query(
    table_name, key_condition_expression=None, expression_attribute_values=None, **kwargs
):
    params = {
        "TableName": table_name,
        "client_config": client_config
    }
    if key_condition_expression:
        params["KeyConditionExpression"] = key_condition_expression
    if expression_attribute_values:
        params["ExpressionAttributeValues"] = expression_attribute_values
    if kwargs:
        params.update(kwargs)
    response = execute_aws_api_call("dynamodb", "query", **params)
    return response


@handle_aws_api_errors
def scan(table, **kwargs):
    params = {
        "TableName": table,
        "client_config": client_config,
    }
    if kwargs:
        params.update(kwargs)
    response = execute_aws_api_call("dynamodb", "scan", **params)
    return response
