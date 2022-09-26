from server.event_handlers import aws

import json
from unittest.mock import MagicMock, patch


@patch("server.event_handlers.aws.log_ops_message")
def test_parse_returns_empty_block_if_no_match_and_logs_error(log_ops_message_mock):
    client = MagicMock()
    payload = MagicMock(Message='{"foo": "bar"}')
    response = aws.parse(payload, client)
    assert response == []
    log_ops_message_mock.assert_called_once_with(
        client, f"Unidentified AWS event received ```{payload.Message}```"
    )


@patch("server.event_handlers.aws.format_cloudwatch_alarm")
def test_parse_returns_blocks_if_AlarmArn_in_msg(format_cloudwatch_alarm_mock):
    client = MagicMock()
    format_cloudwatch_alarm_mock.return_value = ["foo", "bar"]
    payload = mock_cloudwatch_alarm()
    response = aws.parse(payload, client)
    assert response == ["foo", "bar"]
    format_cloudwatch_alarm_mock.assert_called_once_with(json.loads(payload.Message))


def test_format_cloudwatch_alarm_extracts_the_region_and_inserts_it_into_blocks():
    msg = json.loads(mock_cloudwatch_alarm().Message)
    response = aws.format_cloudwatch_alarm(msg)
    assert "ca-central-1" in response[1]["text"]["text"]


def test_format_cloudwatch_alarm_adds_fire_emoji_if_NewStateValue_is_ALARM():
    msg = json.loads(mock_cloudwatch_alarm().Message)
    response = aws.format_cloudwatch_alarm(msg)
    assert "🔥" in response[1]["text"]["text"]


def test_format_cloudwatch_alarm_adds_green_checkmark_emoji_if_NewStateValue_is_OK():
    msg = json.loads(mock_cloudwatch_alarm().Message)
    msg["NewStateValue"] = "OK"
    response = aws.format_cloudwatch_alarm(msg)
    assert "✅" in response[1]["text"]["text"]


def test_format_cloudwatch_alarm_adds_shrug_emoji_if_NewStateValue_is_no_known():
    msg = json.loads(mock_cloudwatch_alarm().Message)
    msg["NewStateValue"] = "NO_DATA"
    response = aws.format_cloudwatch_alarm(msg)
    assert "🤷‍♀️" in response[1]["text"]["text"]


def test_format_cloudwatch_alarm_replaces_empty_AlarmDescription_with_blank():
    msg = json.loads(mock_cloudwatch_alarm().Message)
    msg["AlarmDescription"] = None
    response = aws.format_cloudwatch_alarm(msg)
    assert response[3]["text"]["text"] == " "


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
