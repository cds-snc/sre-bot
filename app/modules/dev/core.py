import os
from . import aws_dev, google

PREFIX = os.environ.get("PREFIX", "")


def dev_command(ack, logger, respond, client, body, args):
    ack()

    if PREFIX != "dev-":
        respond("This command is only available in the development environment.")
        return
    action = args.pop(0) if args else ""
    logger.info("Dev command received: %s", action)
    match action:
        case "aws":
            aws_dev.aws_dev_command(ack, client, body, respond)
        case "google":
            google.google_service_command(ack, client, body, respond, logger)
