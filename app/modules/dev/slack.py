def slack_command(ack, client, body, respond, logger, args):
    ack()
    respond("Processing request...")
