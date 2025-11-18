import json
from unittest.mock import MagicMock

from modules.webhooks.patterns.aws_sns_notification import cloudwatch_alarm


def mock_cloudwatch_alarm():
    return MagicMock(
        Type="Notification",
        MessageId="2d3a994f-adb5-5d6f-ab5e-c2e508881361",
        TopicArn="arn:aws:sns:ca-central-1:017790921725:test-sre-bot",
        Subject='ALARM: "Test alarm" in Canada (Central)',
        Message='{"AlarmName":"Test alarm","AlarmDescription":null,"AWSAccountId":"017790921725","AlarmConfigurationUpdatedTimestamp":"2022-09-25T18:48:56.505+0000","NewStateValue":"ALARM","NewStateReason":"Threshold Crossed: 1 out of the last 1 datapoints [6.0 (25/09/22 18:49:00)] was greater than the threshold (5.0) (minimum 1 datapoint for OK -> ALARM transition).","StateChangeTime":"2022-09-25T18:50:37.811+0000","Region":"Canada (Central)","AlarmArn":"arn:aws:cloudwatch:ca-central-1:017790921725:alarm:Test alarm","OldStateValue":"INSUFFICIENT_DATA","OKActions":[],"AlarmActions":["arn:aws:sns:ca-central-1:017790921725:test-sre-bot"],"InsufficientDataActions":[],"Trigger":{"MetricName":"ConcurrentExecutions","Namespace":"AWS/Lambda","StatisticType":"Statistic","Statistic":"SUM","Unit":null,"Dimensions":[],"Period":60,"EvaluationPeriods":1,"DatapointsToAlarm":1,"ComparisonOperator":"GreaterThanThreshold","Threshold":5.0,"TreatMissingData":"missing","EvaluateLowSampleCountPercentile":""}}',
        Timestamp="2022-09-25T18:50:37.868Z",
        SignatureVersion="1",
        Signature="moqTWYO0OA1HN4MIHrtym3N6SWqvotsY4EcG+Ty/wrfZcxpQ3mximWM7ZfoYlzZ8NBh4s1XTPuqbl5efK64TEuPgNWBMKsm5Gc2d8H6hoDpLqAOELGl2/xlvWf2CovLH/KPj8xrSwAgOS9jL4r/EEMdXYb705YMMBudu78gooatU9EpVl+1I2MCP2AW0ZJWrcSwYMqxo9yo7H6coyBRlmTxP97PlELXoqXLfufsfFBjZ0eFycndG5A0YHeue82uLF5fIHGpcTjqNzLF0PXuJoS9xVkGx3X7p+dzmRE4rp/swGyKCqbXvgldPRycuj7GSk3r8HLSfzjqHyThnDqMECA==",
        SigningCertURL="https://sns.ca-central-1.amazonaws.com/SimpleNotificationService-56e67fcb41f6fec09b0196692625d385.pem",
        UnsubscribeURL="https://sns.ca-central-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:ca-central-1:017790921725:test-sre-bot:4636a013-5224-4207-91b2-d6d7c7ab7ea7",
    )


def test_cloudwatch_alarm_handler_extracts_region():
    client = MagicMock()
    payload = mock_cloudwatch_alarm()
    blocks = cloudwatch_alarm.handle_cloudwatch_alarm(payload, client)
    assert any("ca-central-1" in b["text"]["text"] for b in blocks if "text" in b)


def test_cloudwatch_alarm_handler_adds_fire_emoji_if_alarm():
    client = MagicMock()
    payload = mock_cloudwatch_alarm()
    blocks = cloudwatch_alarm.handle_cloudwatch_alarm(payload, client)
    assert any("🔥" in b["text"]["text"] for b in blocks if "text" in b)


def test_cloudwatch_alarm_handler_adds_green_checkmark_if_ok():
    client = MagicMock()
    payload = mock_cloudwatch_alarm()
    # Patch NewStateValue to OK
    msg = json.loads(payload.Message)
    msg["NewStateValue"] = "OK"
    payload.Message = json.dumps(msg)
    blocks = cloudwatch_alarm.handle_cloudwatch_alarm(payload, client)
    assert any("✅" in b["text"]["text"] for b in blocks if "text" in b)


def test_cloudwatch_alarm_handler_adds_shrug_if_unknown():
    client = MagicMock()
    payload = mock_cloudwatch_alarm()
    msg = json.loads(payload.Message)
    msg["NewStateValue"] = "NO_DATA"
    payload.Message = json.dumps(msg)
    blocks = cloudwatch_alarm.handle_cloudwatch_alarm(payload, client)
    assert any("🤷‍♀️" in b["text"]["text"] for b in blocks if "text" in b)


def test_cloudwatch_alarm_handler_replaces_empty_alarm_description():
    client = MagicMock()
    payload = mock_cloudwatch_alarm()
    msg = json.loads(payload.Message)
    msg["AlarmDescription"] = None
    payload.Message = json.dumps(msg)
    blocks = cloudwatch_alarm.handle_cloudwatch_alarm(payload, client)
    assert blocks[3]["text"]["text"] == " "


def test_cloudwatch_alarm_matcher():
    payload = mock_cloudwatch_alarm()
    parsed_message = json.loads(payload.Message)
    assert cloudwatch_alarm.is_cloudwatch_alarm_message(payload, parsed_message)
