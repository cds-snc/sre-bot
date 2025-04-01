from slack_sdk.web import WebClient
from slack_bolt import Respond

from integrations.aws import lambdas as aws_lambdas

help_text = """
\n *AWS Lambda*:
\n • `/aws lambda functions` - List all Lambda functions.
\n • `/aws lambda layers` - List all Lambda layers.
"""


def command_handler(client: WebClient, body, respond: Respond, args, logger):
    """Handle the command.

    Args:
        client (Slack WebClient): The Slack client.
        body (dict): The request body.
        respond (function): The function to respond to the request.
        args (list[str]): The list of arguments.
        logger (Logger): The logger.
    """

    action = args.pop(0) if args else ""

    match action:
        case "help" | "aide":
            respond(help_text)
        case "functions" | "function":
            request_list_functions(client, body, respond, logger)
        case "layers" | "layer":
            request_list_layers(client, body, respond, logger)
        case _:
            respond("Invalid command. Type `/aws lambda help` for more information.")


def request_list_functions(client: WebClient, body, respond: Respond, logger):
    """List all Lambda functions.

    Args:
        client (Slack WebClient): The Slack client.
        body (dict): The request body.
        respond (function): The function to respond to the request.
    """
    respond("Fetching Lambda functions...")
    response = aws_lambdas.list_functions()
    if response:
        logger.info("lambda_functions_found", count=len(response), response=response)
        function_string = ""
        for function in response:
            function_string += f"\n • {function['FunctionName']}"
        respond(f"Lambda functions found:\n{function_string}")
    else:
        respond("Lambda functions management is currently disabled.")


def request_list_layers(client: WebClient, body, respond: Respond, logger):
    """List all Lambda layers.

    Args:
        client (Slack WebClient): The Slack client.
        body (dict): The request body.
        respond (function): The function to respond to the request.
    """
    response = aws_lambdas.list_layers()
    respond("Fetching Lambda layers...")
    if response:
        logger.info("lambda_layers_found", count=len(response), response=response)
        response_string = ""
        for layer in response:
            response_string += f"\n • {layer['LayerName']} <latest version: {layer['LatestMatchingVersion']['Version']}>"
        respond(f"Lambda layers found:\n{response_string}")
    else:
        respond("Lambda layers management is currently disabled.")
