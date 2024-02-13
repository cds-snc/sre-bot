import logging
from integrations.sentinel import send_event
import re

logging.basicConfig(level=logging.INFO)


def log_ops_message(client, message):
    channel_id = "C0388M21LKZ"
    logging.info(f"Ops msg: {message}")
    client.conversations_join(channel=channel_id)
    client.chat_postMessage(channel=channel_id, text=message, as_user=True)


def log_to_sentinel(event, message):
    payload = {"event": event, "message": message}
    if send_event(payload):
        logging.info(f"Sentinel event sent: {payload}")
    else:
        logging.error(f"Sentinel event failed: {payload}")
