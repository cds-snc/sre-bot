import json
import os
import pytest
from unittest.mock import MagicMock, patch

from modules.webhooks import aws
from modules.webhooks.aws import (
    SignatureVerificationFailureException,
    HTTPException,
)
from models.webhooks import AwsSnsPayload


@patch("modules.webhooks.aws.log_ops_message")
@patch("modules.webhooks.aws.sns_message_validator")
def test_validate_sns_payload_validates_model(
    sns_message_validator_mock, log_ops_message_mock
):
    client = MagicMock()
    payload = AwsSnsPayload(**mock_budget_alert())
    sns_message_validator_mock.validate_message.return_value = None
    response = aws.validate_sns_payload(payload, client)
    assert sns_message_validator_mock.validate_message.call_count == 1
    assert log_ops_message_mock.call_count == 0
    assert response == payload


@patch("modules.webhooks.aws.logger")
@patch("modules.webhooks.aws.log_ops_message")
def test_validate_sns_payload_invalid_message_type(
    log_ops_message_mock,
    logger_mock,
):
    client = MagicMock()
    payload = AwsSnsPayload(**mock_budget_alert())
    payload.Type = "InvalidType"

    with pytest.raises(HTTPException) as e:
        aws.validate_sns_payload(payload, client)
    assert e.value.status_code == 500

    logger_mock.exception.assert_called_once_with(
        "aws_sns_payload_validation_error",
        error="InvalidType is not a valid message type.",
    )
    assert log_ops_message_mock.call_count == 1
    assert (
        log_ops_message_mock.call_args[0][1]
        == f"Invalid message type ```{payload.Type}``` in message: ```{payload}```"
    )


@patch("modules.webhooks.aws.logger")
@patch("modules.webhooks.aws.log_ops_message")
def test_validate_sns_payload_invalid_signature_version(
    log_ops_message_mock, logger_mock
):
    client = MagicMock()
    payload = AwsSnsPayload(**mock_budget_alert())
    payload.Type = "Notification"
    payload.SignatureVersion = "InvalidVersion"

    with pytest.raises(HTTPException) as e:
        aws.validate_sns_payload(payload, client)
    assert e.value.status_code == 500

    logger_mock.exception.assert_called_once_with(
        "aws_sns_payload_validation_error",
        error="Invalid signature version. Unable to verify signature.",
    )
    log_ops_message_mock.assert_called_once_with(
        client,
        f"Unexpected signature version ```{payload.SignatureVersion}``` in message: ```{payload}```",
    )


@patch("modules.webhooks.aws.logger")
@patch("modules.webhooks.aws.log_ops_message")
def test_validate_sns_payload_invalid_signature_url(log_ops_message_mock, logger_mock):
    client = MagicMock()
    payload = AwsSnsPayload(**mock_budget_alert())
    payload.Type = "Notification"
    payload.SignatureVersion = "1"
    payload.SigningCertURL = "https://invalid.url"

    with pytest.raises(HTTPException) as e:
        aws.validate_sns_payload(payload, client)
    assert e.value.status_code == 500
    logger_mock.exception.assert_called_once_with(
        "aws_sns_payload_validation_error",
        error="Invalid certificate URL.",
    )
    log_ops_message_mock.assert_called_once_with(
        client,
        f"Invalid certificate URL ```{payload.SigningCertURL}``` in message: ```{payload}```",
    )


@patch("modules.webhooks.aws.logger")
@patch("modules.webhooks.aws.sns_message_validator._verify_signature")
@patch("modules.webhooks.aws.log_ops_message")
def test_validate_sns_payload_signature_verification_failure(
    log_ops_message_mock, verify_signature_mock, logger_mock
):
    client = MagicMock()
    payload = AwsSnsPayload(**mock_budget_alert())
    payload.Type = "Notification"
    payload.SignatureVersion = "1"
    payload.SigningCertURL = "https://sns.us-east-1.amazonaws.com/valid-cert.pem"
    payload.Signature = "invalid_signature"

    # Mock the verify_signature method to raise the right exception to test
    verify_signature_mock.side_effect = SignatureVerificationFailureException(
        "Invalid signature."
    )

    with pytest.raises(HTTPException) as e:
        aws.validate_sns_payload(payload, client)
    assert e.value.status_code == 500

    logger_mock.exception.assert_called_once_with(
        "aws_sns_payload_validation_error",
        error="Invalid signature.",
    )
    log_ops_message_mock.assert_called_once_with(
        client,
        f"Failed to verify signature ```{payload.Signature}``` in message: ```{payload}```",
    )


@patch("modules.webhooks.aws.logger")
@patch("modules.webhooks.aws.log_ops_message")
@patch("modules.webhooks.aws.sns_message_validator.validate_message")
def test_validate_sns_payload_unexpected_exception(
    validate_message_mock, log_ops_message_mock, logger_mock
):
    client = MagicMock()
    payload = AwsSnsPayload(**mock_budget_alert())

    # Mock the validate_message method to raise a generic exception
    validate_message_mock.side_effect = Exception("Unexpected error")

    with pytest.raises(HTTPException) as e:
        aws.validate_sns_payload(payload, client)
    assert e.value.status_code == 500

    logger_mock.exception.assert_called_once_with(
        "aws_sns_payload_validation_error", error="Unexpected error"
    )
    log_ops_message_mock.assert_called_once_with(
        client,
        f"Error parsing AWS event due to Exception: ```{payload}```",
    )


@patch("modules.webhooks.aws.log_ops_message")
def test_parse_returns_empty_block_if_empty_message(log_ops_message_mock):
    client = MagicMock()
    payload = MagicMock(Message=None, Type="Notification")
    response = aws.parse(payload, client)
    assert response == []
    log_ops_message_mock.assert_called_once_with(
        client, f"Payload Message is empty ```{payload}```"
    )


@patch("modules.webhooks.aws.log_ops_message")
def test_parse_returns_empty_block_if_no_match_and_logs_error(log_ops_message_mock):
    client = MagicMock()
    payload = MagicMock(Message='{"foo": "bar"}')
    response = aws.parse(payload, client)
    assert response == []
    log_ops_message_mock.assert_called_once_with(
        client, f"Unidentified AWS event received ```{payload.Message}```"
    )


@patch("modules.webhooks.aws.log_ops_message")
def test_parse_returns_empty_block_if_budget_auto_adjustment_event(
    log_ops_message_mock,
):
    client = MagicMock()
    payload = MagicMock(
        Message='{"previousBudgetLimit": "1", "currentBudgetLimit": "2"}'
    )
    response = aws.parse(payload, client)
    assert response == []
    log_ops_message_mock.assert_not_called()


@patch("modules.webhooks.aws.format_cloudwatch_alarm")
def test_parse_returns_blocks_if_AlarmArn_in_msg(format_cloudwatch_alarm_mock):
    client = MagicMock()
    format_cloudwatch_alarm_mock.return_value = ["foo", "bar"]
    payload = mock_cloudwatch_alarm()
    response = aws.parse(payload, client)
    assert response == ["foo", "bar"]
    format_cloudwatch_alarm_mock.assert_called_once_with(json.loads(payload.Message))


@patch("modules.webhooks.aws.format_budget_notification")
def test_parse_returns_blocks_if_budget_notification_in_msg(
    format_budget_notification_mock,
):
    client = MagicMock()
    format_budget_notification_mock.return_value = ["foo", "bar"]
    payload = mock_budget_alert()
    response = aws.parse(payload, client)
    assert response == ["foo", "bar"]
    format_budget_notification_mock.assert_called_once_with(payload)


@patch("modules.webhooks.aws.format_abuse_notification")
def test_parse_returns_blocks_if_service_is_ABUSE(format_abuse_notification_mock):
    client = MagicMock()
    format_abuse_notification_mock.return_value = ["foo", "bar"]
    payload = mock_abuse_alert()
    response = aws.parse(payload, client)
    assert response == ["foo", "bar"]
    format_abuse_notification_mock.assert_called_once_with(
        payload, json.loads(payload.Message)
    )


@patch("modules.webhooks.aws.format_auto_mitigation")
def test_parse_returns_blocks_if_auto_mitigated(format_auto_mitigation_mock):
    # Test that the parse function returns the blocks returned by format_auto_mitigation
    client = MagicMock()
    format_auto_mitigation_mock.return_value = ["foo", "bar"]
    payload = mock_auto_migitation()
    response = aws.parse(payload, client)
    assert response == ["foo", "bar"]
    format_auto_mitigation_mock.assert_called_once_with(payload)


@patch("modules.webhooks.aws.format_new_iam_user")
def test_parse_returns_blocks_if_new_iam_user(format_new_iam_user_mock):
    # Test that the parse function returns the blocks returned by format_new_iam_user
    client = MagicMock()
    format_new_iam_user_mock.return_value = ["foo", "bar"]
    payload = mock_new_iam_user()
    response = aws.parse(payload, client)
    assert response == ["foo", "bar"]
    format_new_iam_user_mock.assert_called_once_with(payload)


def test_format_abuse_notification_extracts_the_account_id_and_inserts_it_into_blocks():
    payload = mock_abuse_alert()
    msg = json.loads(payload.Message)
    response = aws.format_abuse_notification(payload, msg)
    assert "017790921725" in response[1]["text"]["text"]


def test_format_budget_notification_extracts_the_account_id_and_inserts_it_into_blocks():
    payload = mock_budget_alert()
    response = aws.format_budget_notification(payload)
    assert "017790921725" in response[1]["text"]["text"]


def test_format_budget_notificatio_adds_the_subject_into_blocks():
    payload = mock_budget_alert()
    response = aws.format_budget_notification(payload)
    assert response[2]["text"]["text"] == payload.Subject


def test_format_budget_notificatio_adds_the_message_into_blocks():
    payload = mock_budget_alert()
    response = aws.format_budget_notification(payload)
    assert response[3]["text"]["text"] == payload.Message


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


def test_format_auto_mitigation_extracts_the_security_group_id_and_inserts_it_into_blocks():
    # Test that the format_auto_mitigation function extracts the security group id properly
    payload = mock_auto_migitation()
    response = aws.format_auto_mitigation(payload)
    assert "sg-09d2738530b93476d" in response[2]["text"]["text"]


def test_format_auto_mitigation_extracts_the_account_id_and_inserts_it_into_blocks():
    # Test that the format_auto_mitigation function extracts the account id properly
    payload = mock_auto_migitation()
    response = aws.format_auto_mitigation(payload)
    assert "017790921725" in response[1]["text"]["text"]


def test_format_auto_mitigation_extracts_the_port_and_inserts_it_into_blocks():
    # Test that the format_auto_mitigation function extracts the ip properly
    payload = mock_auto_migitation()
    response = aws.format_auto_mitigation(payload)
    assert "22" in response[1]["text"]["text"]


def test_format_auto_mitigation_extracts_the_user_and_inserts_it_into_blocks():
    # Test that the format_auto_mitigation function extracts the user properly
    payload = mock_auto_migitation()
    response = aws.format_auto_mitigation(payload)
    assert "test_user@cds-snc.ca" in response[1]["text"]["text"]


def test_format_new_iam_user_extracts_the_iam_user_created_and_inserts_it_into_blocks():
    # Test that the format_new_iam_user function extracts the user_created properly
    payload = mock_new_iam_user()
    response = aws.format_new_iam_user(payload)
    assert "user_created" in response[2]["text"]["text"]


def test_format_new_iam_user_extracts_the_account_and_inserts_it_into_blocks():
    # Test that the format_new_iam_user function extracts the user_created properly
    payload = mock_new_iam_user()
    response = aws.format_new_iam_user(payload)
    assert "412578375350" in response[2]["text"]["text"]


def test_format_new_iam_user_extracts_the_user_and_inserts_it_into_blocks():
    # Test that the format_new_iam_user function extracts the user properly
    payload = mock_new_iam_user()
    response = aws.format_new_iam_user(payload)
    assert "test_user@cds-snc.ca" in response[2]["text"]["text"]


@patch("modules.webhooks.aws.format_api_key_detected")
def test_parse_returns_blocks_if_api_key_detected(format_api_key_detected_mock):
    # Test that the parse function returns the blocks returned by format_api_key_detected
    client = MagicMock()
    format_api_key_detected_mock.return_value = ["foo", "bar"]
    payload = mock_api_key_detected()
    response = aws.parse(payload, client)
    assert response == ["foo", "bar"]
    format_api_key_detected_mock.assert_called_once_with(payload, client)


@patch("modules.webhooks.aws.format_api_key_detected")
def test_parse_returns_blocks_if_api_key_compromised(format_api_key_detected_mock):
    # Test that the parse function returns the blocks returned by format_new_iam_user
    client = MagicMock()
    aws.format_api_key_detected.return_value = ["foo", "bar"]
    payload = mock_api_key_detected()
    response = aws.parse(payload, client)
    assert response == ["foo", "bar"]
    aws.format_api_key_detected.assert_called_once_with(payload, client)


@patch("integrations.notify.revoke_api_key")
def test_format_api_key_detected_extracts_the_api_key_and_inserts_it_into_blocks(
    revoke_api_key_mock,
):
    # Test that the format_api_key_detected function extracts the api key properly
    client = MagicMock()
    payload = mock_api_key_detected()
    response = aws.format_api_key_detected(payload, client)
    assert "api-key-blah" in response[2]["text"]["text"]


@patch("integrations.notify.revoke_api_key")
def test_format_api_key_detected_extracts_the_url_and_inserts_it_into_blocks(
    revoke_api_key_mock,
):
    # Test that the format_api_key_detected function extracts the url properly
    client = MagicMock()
    payload = mock_api_key_detected()
    response = aws.format_api_key_detected(payload, client)
    assert "https://github.com/blah" in response[2]["text"]["text"]


@patch("integrations.notify.revoke_api_key")
def test_format_api_key_detected_extracts_the_service_id_and_inserts_it_into_blocks(
    revoke_api_key_mock,
):
    # Test that the format_api_key_detected function extracts the url properly
    client = MagicMock()
    payload = mock_api_key_detected()
    response = aws.format_api_key_detected(payload, client)
    assert "00000000-0000-0000-0000-000000000000" in response[2]["text"]["text"]


# Test that the format_api_key_detected function extracts the api revoke message if it is successful
@patch("integrations.notify.revoke_api_key")
def test_format_api_key_detected_success_extracts_the_api_revoke_message_and_inserts_it_into_blocks(
    revoke_api_key_mock,
):
    # Test that the format_api_key_detected function extracts the on call message properly
    client = MagicMock()
    revoke_api_key_mock.return_value = True
    payload = mock_api_key_detected()
    response = aws.format_api_key_detected(payload, client)
    assert (
        "*API key api-key-blah has been successfully revoked.*"
        in response[3]["text"]["text"]
    )


# Test that the format_api_key_detected function extracts the api revoke message if it is unsuccessful
@patch("integrations.notify.revoke_api_key")
def test_format_api_key_detected_failure_extracts_the_api_revoke_message_and_inserts_it_into_blocks(
    revoke_api_key_mock,
):
    client = MagicMock()
    revoke_api_key_mock.return_value = False
    payload = mock_api_key_detected()
    response = aws.format_api_key_detected(payload, client)
    assert (
        "*API key api-key-blah could not be revoked due to an error.*"
        in response[3]["text"]["text"]
    )


@patch.object(aws, "NOTIFY_OPS_CHANNEL_ID", "test_channel_id")
def test_successful_message_post_notify_channel_for_notify():
    # Mock the chat_postMessage method
    client = MagicMock()
    blocks = ["test_blocks"]

    # Call the function
    aws.send_message_to_notify_chanel(client, blocks)

    # Assert that chat_postMessage was called with the correct parameters
    client.chat_postMessage.assert_called_once_with(
        channel="test_channel_id", blocks=["test_blocks"]
    )


@patch.object(aws, "NOTIFY_OPS_CHANNEL_ID", None)
def test_exception_for_missing_env_variable_notify_channel_for_notify():
    # Test that an exception is reaised if the NOTIFY_POS_CHANNEL_ID is not set
    with pytest.raises(AssertionError) as err:
        client = MagicMock()
        aws.send_message_to_notify_chanel(client, ["test_blocks"])
    # assert that the correct exception is raised
    assert str(err.value) == "NOTIFY_OPS_CHANNEL_ID is not set in the environment"


def mock_abuse_alert():
    return MagicMock(
        Type="Notification",
        MessageId="0da238f6-da6c-5214-96e1-635d27a9b79b",
        TopicArn="arn:aws:sns:ca-central-1:017790921725:test-sre-bot",
        Subject="",
        Message='{"version":"0","id":"7bf73129-1428-4cd3-a780-95db273d1602","detail-type":"AWS Health Abuse Event","source":"aws.health","account":"123456789012","time":"2018-08-01T06:27:57Z","region":"global","resources":["arn:aws:ec2:us-east-1:123456789012:instance/i-abcd1111","arn:aws:ec2:us-east-1:123456789012:instance/i-abcd2222"],"detail":{"eventArn":"arn:aws:health:global::event/AWS_ABUSE_DOS_REPORT_92387492375_4498_2018_08_01_02_33_00","service":"ABUSE","eventTypeCode":"AWS_ABUSE_DOS_REPORT","eventTypeCategory":"issue","startTime":"Wed, 01 Aug 2018 06:27:57 GMT","eventDescription":[{"language":"en_US","latestDescription":"A description of the event will be provided here"}],"affectedEntities":[{"entityValue":"arn:aws:ec2:us-east-1:123456789012:instance/i-abcd1111"},{"entityValue":"arn:aws:ec2:us-east-1:123456789012:instance/i-abcd2222"}]}}',
        Timestamp="2022-09-26T19:20:37.147Z",
        SignatureVersion="1",
        Signature="HLsCTKHEC2FXGe6LFkV/JGD7k/apzJZD42R8ph4AzcD9NcrxZyjINTyPFe1zMtg3kcGSge2J3MqFcTTyQJtkRrKZZftIVZRflwWKu4OLHt1atHSOavI8n7Qh3bRtwR5C3mezhtu6oWbfEdTXAuyz4AWcZ0L9dxE4B3bOMS302ViQA3hIfjSlGLRr+j/Ra7+IbzY35QUJLxtVcmcAAw/ByuyXeDRy+6qhJtKndOTeMBLTKAQlIOPubyJP1Q2BWo0spREmIESnPtB14c5k+6LWxa/srPjfOWu66ICUNnydKnvf5EuIlpooycLldttvDtwmD2NZt6kQr2FJhkqARyr/Ng==",
        SigningCertURL="https://sns.ca-central-1.amazonaws.com/SimpleNotificationService-56e67fcb41f6fec09b0196692625d385.pem",
        UnsubscribeURL="https://sns.ca-central-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:ca-central-1:017790921725:test-sre-bot:4636a013-5224-4207-91b2-d6d7c7ab7ea7",
    )


def mock_budget_alert():
    return MagicMock(
        Type="Notification",
        MessageId="0da238f6-da6c-5214-96e1-635d27a9b79b",
        TopicArn="arn:aws:sns:ca-central-1:017790921725:test-sre-bot",
        Subject="AWS Budgets: Test Budget has exceeded your alert threshold",
        Message="AWS Budget Notification September 26, 2022\nAWS Account 017790921725\n\nDear AWS Customer,\n\nYou requested that we alert you when the ACTUAL Cost associated with your Test Budget budget is greater than $0.16 for the current month. The ACTUAL Cost associated with this budget is $0.59. You can find additional details below and by accessing the AWS Budgets dashboard [1].\n\nBudget Name: Test Budget\nBudget Type: Cost\nBudgeted Amount: $0.20\nAlert Type: ACTUAL\nAlert Threshold: > $0.16\nACTUAL Amount: $0.59\n\n[1] https://console.aws.amazon.com/billing/home#/budgets\n",
        Timestamp="2022-09-26T19:20:37.147Z",
        SignatureVersion="1",
        Signature="HLsCTKHEC2FXGe6LFkV/JGD7k/apzJZD42R8ph4AzcD9NcrxZyjINTyPFe1zMtg3kcGSge2J3MqFcTTyQJtkRrKZZftIVZRflwWKu4OLHt1atHSOavI8n7Qh3bRtwR5C3mezhtu6oWbfEdTXAuyz4AWcZ0L9dxE4B3bOMS302ViQA3hIfjSlGLRr+j/Ra7+IbzY35QUJLxtVcmcAAw/ByuyXeDRy+6qhJtKndOTeMBLTKAQlIOPubyJP1Q2BWo0spREmIESnPtB14c5k+6LWxa/srPjfOWu66ICUNnydKnvf5EuIlpooycLldttvDtwmD2NZt6kQr2FJhkqARyr/Ng==",
        SigningCertURL="https://sns.ca-central-1.amazonaws.com/SimpleNotificationService-56e67fcb41f6fec09b0196692625d385.pem",
        UnsubscribeURL="https://sns.ca-central-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:ca-central-1:017790921725:test-sre-bot:4636a013-5224-4207-91b2-d6d7c7ab7ea7",
    )


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


# Mock the SNS message
def mock_auto_migitation():
    return MagicMock(
        Type="Notification",
        MessageId="1e5f5647g-adb5-5d6f-ab5e-c2e508881361",
        TopicArn="arn:aws:sns:ca-central-1:017790921725:test-sre-bot",
        Subject="Auto-mitigation successful",
        Message='AUTO-MITIGATED: Ingress rule removed from security group: sg-09d2738530b93476d that was added by arn:aws:sts::017790921725:assumed-role/AWSReservedSSO_AWSAdministratorAccess_a01cd72a8d380c1f/test_user@cds-snc.ca: [{"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": "0.0.0.0 / 0"}]}]',
        Timestamp="2023-09-25T20:50:37.868Z",
        SignatureVersion="1",
        Signature="EXAMPLEO0OA1HN4MIHrtym3N6SWqvotsY4EcG+Ty/wrfZcxpQ3mximWM7ZfoYlzZ8NBh4s1XTPuqbl5efK64TEuPgNWBMKsm5Gc2d8H6hoDpLqAOELGl2/xlvWf2CovLH/KPj8xrSwAgOS9jL4r/EEMdXYb705YMMBudu78gooatU9EpVl+1I2MCP2AW0ZJWrcSwYMqxo9yo7H6coyBRlmTxP97PlELXoqXLfufsfFBjZ0eFycndG5A0YHeue82uLF5fIHGpcTjqNzLF0PXuJoS9xVkGx3X7p+dzmRE4rp/swGyKCqbXvgldPRycuj7GSk3r8HLSfzjqHyThnDqMECA==",
        SigningCertURL="https://sns.ca-central-1.amazonaws.com/SimpleNotificationService-56e67fcb41f6fec09b0196692625d385.pem",
        UnsubscribeURL="https://sns.ca-central-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:ca-central-1:017790921725:test-sre-bot:4636a013-5224-4207-91b2-d6d7c7ab7ea7",
    )


# Mock the message returned from AWS when a new IAM User is created
def mock_new_iam_user():
    return MagicMock(
        Type="Notification",
        MessageId="1e5f5647g-adb5-5d6f-ab5e-c2e508881361",
        TopicArn="arn:aws:sns:ca-central-1:412578375350:test-sre-bot",
        Subject="Violation - IAM User is out of compliance",
        Message="An IAM User was created in an Account\n\nIAM ARN: arn:aws:iam::412578375350:user/test2\nIAM User: user_created\nEvent: CreateUser\nActor: arn:aws:sts::412578375350:assumed-role/AWSReservedSSO_AWSAdministratorAccess_3cbb717fd3b23655/test_user@cds-snc.ca\nSource IP Address: 69.172.156.196\nUser Agent: AWS Internal\n\nAccount: 412578375350\nRegion: us-east-1",
        Timestamp="2023-09-25T20:50:37.868Z",
        SignatureVersion="1",
        Signature="EXAMPLEO0OA1HN4MIHrtym3N6SWqvotsY4EcG+Ty/wrfZcxpQ3mximWM7ZfoYlzZ8NBh4s1XTPuqbl5efK64TEuPgNWBMKsm5Gc2d8H6hoDpLqAOELGl2/xlvWf2CovLH/KPj8xrSwAgOS9jL4r/EEMdXYb705YMMBudu78gooatU9EpVl+1I2MCP2AW0ZJWrcSwYMqxo9yo7H6coyBRlmTxP97PlELXoqXLfufsfFBjZ0eFycndG5A0YHeue82uLF5fIHGpcTjqNzLF0PXuJoS9xVkGx3X7p+dzmRE4rp/swGyKCqbXvgldPRycuj7GSk3r8HLSfzjqHyThnDqMECA==",
        SigningCertURL="https://sns.ca-central-1.amazonaws.com/SimpleNotificationService-56e67fcb41f6fec09b0196692625d385.pem",
        UnsubscribeURL="https://sns.ca-central-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:ca-central-1:412578375350:test-sre-bot:4636a013-5224-4207-91b2-d6d7c7ab7ea7",
    )


# Mock the message returned from AWS when a API key has been compromised
def mock_api_key_detected():
    # get the test key. Put it in a variable not to trigger the alarming of the key when committing the file in gitub
    NOTIFY_TEST_KEY = os.getenv("NOTIFY_TEST_KEY", None)
    return MagicMock(
        Type="Notification",
        MessageId="1e5f5647g-adb5-5d6f-ab5e-c2e508881361",
        TopicArn="arn:aws:sns:ca-central-1:412578375350:test-sre-bot",
        Subject="API Key detected",
        Message=f"API Key with value token='{NOTIFY_TEST_KEY}', type='cds_test_type' and source='source_data' has been detected in url='https://github.com/blah'!",
        Timestamp="2023-09-25T20:50:37.868Z",
        SignatureVersion="1",
        Signature="EXAMPLEO0OA1HN4MIHrtym3N6SWqvotsY4EcG+Ty/wrfZcxpQ3mximWM7ZfoYlzZ8NBh4s1XTPuqbl5efK64TEuPgNWBMKsm5Gc2d8H6hoDpLqAOELGl2/xlvWf2CovLH/KPj8xrSwAgOS9jL4r/EEMdXYb705YMMBudu78gooatU9EpVl+1I2MCP2AW0ZJWrcSwYMqxo9yo7H6coyBRlmTxP97PlELXoqXLfufsfFBjZ0eFycndG5A0YHeue82uLF5fIHGpcTjqNzLF0PXuJoS9xVkGx3X7p+dzmRE4rp/swGyKCqbXvgldPRycuj7GSk3r8HLSfzjqHyThnDqMECA==",
        SigningCertURL="https://sns.ca-central-1.amazonaws.com/SimpleNotificationService-56e67fcb41f6fec09b0196692625d385.pem",
        UnsubscribeURL="https://sns.ca-central-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:ca-central-1:412578375350:test-sre-bot:4636a013-5224-4207-91b2-d6d7c7ab7ea7",
    )
