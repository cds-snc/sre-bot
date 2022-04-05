import json
import os
from urllib.request import Request, urlopen

OPSGENIE_KEY = os.getenv("OPSGENIE_KEY", None)


def get_on_call_users(schedule):
    content = api_get_request(
        f"https://api.opsgenie.com/v2/schedules/{schedule}/on-calls",
        {"name": "GenieKey", "token": OPSGENIE_KEY},
    )
    try:
        data = json.loads(content)
        return list(map(lambda x: x["name"], data["data"]["onCallParticipants"]))
    except Exception:
        return []


def api_get_request(url, auth):
    req = Request(url)
    req.add_header("Authorization", f"{auth['name']} {auth['token']}")
    conn = urlopen(req)  # nosec - Scheme is hardcoded to https
    return conn.read().decode("utf-8")
