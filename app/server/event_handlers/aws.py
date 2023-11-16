import json
import re
import logging
import os
import requests
import urllib.parse
from commands.utils import log_ops_message
from integrations import google_drive, opsgenie, notify


def parse(payload, client):
    try:
        msg = json.loads(payload.Message)
    except Exception:
        msg = payload.Message
    if isinstance(msg, dict) and "AlarmArn" in msg:
        blocks = format_cloudwatch_alarm(msg)
    elif isinstance(msg, str) and "AWS Budget Notification" in msg:
        blocks = format_budget_notification(payload)
    elif isinstance(msg, dict) and nested_get(msg, ["detail", "service"]) == "ABUSE":
        blocks = format_abuse_notification(payload, msg)
    elif isinstance(msg, str) and "AUTO-MITIGATED" in msg:
        blocks = format_auto_mitigation(payload)
    elif isinstance(msg, str) and "IAM User" in msg:
        blocks = format_new_iam_user(payload)
    elif isinstance(msg, str) and "API Key with value token=" in msg:
        blocks = format_api_key_detected(payload, client)
    else:
        blocks = []
        log_ops_message(
            client,
            f"Unidentified AWS event received ```{payload.Message}```",
        )

    return blocks


def nested_get(dictionary, keys):
    for key in keys:
        try:
            dictionary = dictionary[key]
        except KeyError:
            return None
    return dictionary


def format_abuse_notification(payload, msg):
    regex = r"arn:aws:sns:\w.*:(\d.*):\w.*"
    account = re.search(regex, payload.TopicArn).groups()[0]

    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<https://health.aws.amazon.com/health/home#/account/dashboard/open-issues| 🚨 Abuse Alert | {account}>*",
            },
        },
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{msg['detail']['eventTypeCode'].replace('_', ' ')}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{msg['detail']['eventDescription'][0]['latestDescription']}",
            },
        },
    ]


# If the message contains "AUTO-MITIGATED" it will be parsed by the format_auto_mitigated function. Format the message to give information about the security group, account and the user that opened the port.
def format_auto_mitigation(payload):
    msg = payload.Message
    regex = r"security group: (\w.+) that was added by arn:aws:sts::(\d.+):assumed-role/\w.+/(\w.+): \[{\"IpProtocol\": \"tcp\", \"FromPort\": (\d.+), \"ToPort\":"
    security_group = re.search(regex, msg).groups()[0]
    account = re.search(regex, msg).groups()[1]
    user = re.search(regex, msg).groups()[2]
    port = re.search(regex, msg).groups()[3]

    # Format the message displayed in Slack
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🛠 Auto-mitigated: Port {port} opened in account {account} by {user} 🔩",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Inbound rule change on port {port} created by user {user} for Security group {security_group} on account {account} has been reversed.",
            },
        },
    ]


# If the message contains "IAM User" it will be parsed by the format_new_iam_user function.
def format_new_iam_user(payload):
    msg = payload.Message
    regex = r"IAM User: (\w.+)"
    user_created = re.search(regex, msg).groups()[0]
    regex = r"Actor: arn:aws:sts::(\d.+):assumed-role/\w.+/(\w.+)"
    account = re.search(regex, msg).groups()[0]
    user = re.search(regex, msg).groups()[1]

    # Format the message displayed in Slack
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "👾 New IAM User created 👾",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"New IAM User named {user_created} was created in account {account} by user {user}.",
            },
        },
    ]


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


# If the message contains an api key it will be parsed by the format_api_key_detected function.


def format_api_key_detected(payload, client):
    msg = payload.Message
    regex = r"API Key with value token='(\w.+)' has been detected in url='(\w.+)'"
    # extract the api key and the github repo from the message
    api_key = re.search(regex, msg).groups()[0]
    github_repo = re.search(regex, msg).groups()[1]

    # We don't want to send the actual api-key through Slack, but we do want the name to be given,
    # so therefore extract the api key name by following the format of a Notify api key
    api_key_name = api_key[7 : len(api_key) - 74]

    # call the revoke api endpoint to revoke the api key
    if (notify.revoke_api_key(api_key, api_key_name, github_repo)):
        revoke_api_key_message = f"API key {api_key_name} has been successfully revoked."
    else:
        revoke_api_key_message = f"API key {api_key_name} could not be revoked."

    # Format the message displayed in Slack
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🙀 Notify API Key has been exposed and revoked 😌!",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Notify API Key Name * {api_key_name} * was committed in github file {github_repo}."
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{revoke_api_key_message}",
            },
        },
    ]
