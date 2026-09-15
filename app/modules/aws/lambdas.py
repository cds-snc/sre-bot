from typing import Any

import structlog
from slack_bolt import Respond
from slack_sdk.web import WebClient

from infrastructure.operations import OperationResult
from packages.aws_platform.adapters.aws_lambda import build_lambda_adapter

logger = structlog.get_logger()

help_text = """
\n *AWS Lambda*:
\n • `/aws lambda functions` - List all Lambda functions.
\n • `/aws lambda layers` - List all Lambda layers.
"""


def _failure_fields(result: OperationResult[Any]) -> dict[str, Any]:
    """Return the structured log fields describing a non-success adapter result."""
    return {"status": result.status.value, "error_code": result.error_code, "error": result.message}


def command_handler(client: WebClient, body: dict[str, Any], respond: Respond, args: list[str]) -> None:
    """Handle the command.

    Args:
        client: The Slack client.
        body: The request body.
        respond: The function to respond to the request.
        args: The list of arguments.
    """

    action = args.pop(0) if args else ""

    match action:
        case "help" | "aide":
            respond(help_text)
        case "functions" | "function":
            request_list_functions(client, body, respond)
        case "layers" | "layer":
            request_list_layers(client, body, respond)
        case _:
            respond("Invalid command. Type `/aws lambda help` for more information.")


def request_list_functions(client: WebClient, body: dict[str, Any], respond: Respond) -> None:
    """List all Lambda functions.

    Args:
        client: The Slack client.
        body: The request body.
        respond: The function to respond to the request.
    """
    respond("Fetching Lambda functions...")
    result = build_lambda_adapter().list_functions()
    if not result.is_success:
        logger.error("lambda_functions_lookup_failed", **_failure_fields(result))
        respond(
            "Failed to list Lambda functions. Please try again later.\n"
            "Impossible de lister les fonctions Lambda. Veuillez réessayer plus tard."
        )
        return
    functions = result.data or []
    if not functions:
        respond("No Lambda functions found.\nAucune fonction Lambda trouvée.")
        return
    log = logger.bind(count=len(functions))
    log.info("lambda_functions_found")
    function_string = ""
    for function in functions:
        function_string += f"\n • {function['FunctionName']}"
    respond(f"Lambda functions found:\n{function_string}")


def request_list_layers(client: WebClient, body: dict[str, Any], respond: Respond) -> None:
    """List all Lambda layers.

    Args:
        client: The Slack client.
        body: The request body.
        respond: The function to respond to the request.
    """
    respond("Fetching Lambda layers...")
    result = build_lambda_adapter().list_layers()
    if not result.is_success:
        logger.error("lambda_layers_lookup_failed", **_failure_fields(result))
        respond(
            "Failed to list Lambda layers. Please try again later.\n"
            "Impossible de lister les couches Lambda. Veuillez réessayer plus tard."
        )
        return
    layers = result.data or []
    if not layers:
        respond("No Lambda layers found.\nAucune couche Lambda trouvée.")
        return
    log = logger.bind(count=len(layers))
    log.info("lambda_layers_found")
    response_string = ""
    for layer in layers:
        # LatestMatchingVersion is optional in the Lambda API response.
        version = (layer.get("LatestMatchingVersion") or {}).get("Version")
        response_string += f"\n • {layer['LayerName']}"
        if version is not None:
            response_string += f" <latest version: {version}>"
    respond(f"Lambda layers found:\n{response_string}")
