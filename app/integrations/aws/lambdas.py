import logging
from integrations.aws.client import execute_aws_api_call, handle_aws_api_errors

logger = logging.getLogger(__name__)


@handle_aws_api_errors
def list_functions():
    """List all Lambda functions.

    Returns:
        list: A list of Lambda functions.
    """
    return execute_aws_api_call(
        "lambda", "list_functions", paginated=True, keys=["Functions"]
    )


@handle_aws_api_errors
def list_layers():
    """List all Lambda layers.

    Returns:
        list: A list of Lambda layers.
    """
    return execute_aws_api_call(
        "lambda", "list_layers", paginated=True, keys=["Layers"]
    )


@handle_aws_api_errors
def get_layer_version(layer_name, version_number):
    """Get a Lambda layer version.

    Args:
        layer_name (str): The name of the layer.
        version_number (int): The version number.

    Returns:
        dict: The Lambda layer version.
    """
    return execute_aws_api_call(
        "lambda",
        "get_layer_version",
        LayerName=layer_name,
        VersionNumber=version_number,
    )
