import json
import os
import logging
from urllib.request import Request, urlopen

# Use the integrations API Key as the Opsgenie API Key
OPSGENIE_KEY = os.getenv("OPSGENIE_INTEGRATIONS_KEY", None)


def get_on_call_users(schedule):
    content = api_get_request(
        f"https://api.opsgenie.com/v2/schedules/{schedule}/on-calls",
        {"name": "GenieKey", "token": OPSGENIE_KEY},
    )
    try:
        data = json.loads(content)
        return list(map(lambda x: x["name"], data["data"]["onCallParticipants"]))
    except Exception as e:
        logging.error(
            f"Could not get on call users for schedule {schedule}. Details of error: {e}"
        )
        return []


# Create an Opsgenie alert. This is used to notify the on-call users
def create_alert(description):
    content = api_post_request(
        "https://api.opsgenie.com/v2/alerts",
        {"name": "GenieKey", "token": OPSGENIE_KEY},
        {
            "message": "Notify API Key has been compromised!",
            "description": f"{description}",
        },
    )
    try:
        data = json.loads(content)
        logging.info(f"Created opsgenie alert with result: {data['result']}")
        return data["result"]
    except Exception as e:
        logging.error(f"Could not create opsgenie alert. Error: {e}")
        return "Could not issue alert to Opsgenie!"


def healthcheck():
    """Check if the bot can interact with the Opsgenie API."""
    healthy = False
    try:
        content = api_get_request(
            "https://api.opsgenie.com/v1/services",
            {"name": "GenieKey", "token": OPSGENIE_KEY},
        )
        result = json.loads(content)
        healthy = "data" in result
        logging.info(f"OpsGenie healthcheck result: {result}")
    except Exception as error:
        logging.error(f"OpsGenie healthcheck failed: {error}")
    return healthy


def api_get_request(url, auth):
    req = Request(url)
    req.add_header("Authorization", f"{auth['name']} {auth['token']}")
    conn = urlopen(req)  # nosec - Scheme is hardcoded to https
    return conn.read().decode("utf-8")


# Post the API request to the Opsgenie API
def api_post_request(url, auth, data):
    data = json.dumps(data).encode("utf-8")
    req = Request(url, data=data)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"{auth['name']} {auth['token']}")
    conn = urlopen(req)  # nosec - Scheme is hardcoded to https
    return conn.read().decode("utf-8")
