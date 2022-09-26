import json
import re
import urllib.parse
from commands.utils import log_ops_message


def parse(payload, client):
    try:
        msg = json.loads(payload.Message)
    except Exception:
        msg = payload.Message
    if isinstance(msg, dict) and "AlarmArn" in msg:
        blocks = format_cloudwatch_alarm(msg)
    elif isinstance(msg, str) and "AWS Budget Notification" in msg:
        blocks = format_budget_notification(payload)
    else:
        blocks = []
        log_ops_message(
            client,
            f"Unidentified AWS event received ```{payload.Message}```",
        )

    return blocks


def format_budget_notification(payload):
    regex = r"arn:aws:sns:\w.*:(\d.*):\w.*"
    account = re.search(regex, payload.TopicArn).groups()[0]

    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<https://console.aws.amazon.com/billing/home#/budgets| 💸 Budget Alert | {account}>*",
            },
        },
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{payload.Subject}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{payload.Message}"},
        },
    ]


def format_cloudwatch_alarm(msg):
    regex = r"arn:aws:cloudwatch:(\w.*):\d.*:alarm:\w.*"
    region = re.search(regex, msg["AlarmArn"]).groups()[0]

    if msg["NewStateValue"] == "ALARM":
        emoji = "🔥"
    elif msg["NewStateValue"] == "OK":
        emoji = "✅"
    else:
        emoji = "🤷‍♀️"

    if msg["AlarmDescription"] is None:
        msg["AlarmDescription"] = " "

    link = f"https://console.aws.amazon.com/cloudwatch/home?region={region}#alarm:alarmFilter=ANY;name={urllib.parse.quote(msg['AlarmName'])}"

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{link}|{emoji} CloudWatch Alert | {region} | {msg['AWSAccountId']}>*",
            },
        },
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{msg['AlarmName']}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{msg['AlarmDescription']}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{msg['NewStateReason']}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*New State:*\n {msg['NewStateValue']}"},
                {"type": "mrkdwn", "text": f"*Old State:*\n {msg['OldStateValue']}"},
            ],
        },
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": link}},
    ]
    return blocks
