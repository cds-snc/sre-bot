import logging
from fastapi import Request, HTTPException

logging.basicConfig(level=logging.INFO)


def log_ops_message(client, message):
    channel_id = "C0388M21LKZ"
    logging.info(f"Ops msg: {message}")
    client.conversations_join(channel=channel_id)
    client.chat_postMessage(channel=channel_id, text=message, as_user=True)


def get_user_email_from_request(request: Request):
    if not request or not request.session:
        raise HTTPException(
            status_code=400, detail="Invalid request or missing session data"
        )

    user_email = request.session.get("user").get("email")
    if user_email:
        return user_email
    return None
