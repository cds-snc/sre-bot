from core.logging import get_module_logger
from integrations.aws.client import execute_aws_api_call, handle_aws_api_errors

logger = get_module_logger()


@handle_aws_api_errors
def list_functions():
    """List all Lambda functions.

    Returns:
        list: A list of Lambda functions.
    """
    logger.debug("lambda_list_functions_started")
    response = execute_aws_api_call(
        "lambda", "list_functions", paginated=True, keys=["Functions"]
    )
    function_count = len(response) if response else 0
    logger.debug("lambda_list_functions_completed", function_count=function_count)
    return response


@handle_aws_api_errors
def list_layers():
    """List all Lambda layers.

    Returns:
        list: A list of Lambda layers.
    """
    logger.debug("lambda_list_layers_started")
    response = execute_aws_api_call(
        "lambda", "list_layers", paginated=True, keys=["Layers"]
    )
    layer_count = len(response) if response else 0
    logger.debug("lambda_list_layers_completed", layer_count=layer_count)
    return response


@handle_aws_api_errors
def get_layer_version(layer_name, version_number):
    """Get a Lambda layer version.

    Args:
        layer_name (str): The name of the layer.
        version_number (int): The version number.

    Returns:
        dict: The Lambda layer version.
    """
    logger.debug(
        "lambda_get_layer_version_started",
        layer_name=layer_name,
        version=version_number,
    )
    response = execute_aws_api_call(
        "lambda",
        "get_layer_version",
        LayerName=layer_name,
        VersionNumber=version_number,
    )
    logger.debug(
        "lambda_get_layer_version_completed",
        layer_name=layer_name,
        version=version_number,
    )
    return response
