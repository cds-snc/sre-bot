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


@patch("server.event_handlers.aws.format_budget_notification")
def test_parse_returns_blocks_if_budget_notification_in_msg(
    format_budget_notification_mock,
):
    client = MagicMock()
    format_budget_notification_mock.return_value = ["foo", "bar"]
    payload = mock_budget_alert()
    response = aws.parse(payload, client)
    assert response == ["foo", "bar"]
    format_budget_notification_mock.assert_called_once_with(payload)


@patch("server.event_handlers.aws.format_abuse_notification")
def test_parse_returns_blocks_if_service_is_ABUSE(format_abuse_notification_mock):
    client = MagicMock()
    format_abuse_notification_mock.return_value = ["foo", "bar"]
    payload = mock_abuse_alert()
    response = aws.parse(payload, client)
    assert response == ["foo", "bar"]
    format_abuse_notification_mock.assert_called_once_with(
        payload, json.loads(payload.Message)
    )


@patch("server.event_handlers.aws.format_auto_mitigation")
def test_parse_returns_blocks_if_auto_mitigated(format_auto_mitigation_mock):
    # Test that the parse function returns the blocks returned by format_auto_mitigation
    client = MagicMock()
    format_auto_mitigation_mock.return_value = ["foo", "bar"]
    payload = mock_auto_migitation()
    response = aws.parse(payload, client)
    assert response == ["foo", "bar"]
    format_auto_mitigation_mock.assert_called_once_with(payload)


@patch("server.event_handlers.aws.format_new_iam_user")
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


@patch("server.event_handlers.aws.format_api_key_detected")
def test_parse_returns_blocks_if_api_key_detected(format_api_key_detected_mock):
    # Test that the parse function returns the blocks returned by format_api_key_detected
    client = MagicMock()
    format_api_key_detected_mock.return_value = ["foo", "bar"]
    payload = mock_api_key_detected()
    response = aws.parse(payload, client)
    assert response == ["foo", "bar"]
    format_api_key_detected_mock.assert_called_once_with(payload, client)


@patch("server.event_handlers.aws.alert_on_call")
def test_format_api_key_detected_extracts_the_api_key_and_inserts_it_into_blocks(
    alert_on_call_mock,
):
    # Test that the format_api_key_detected function extracts the api key properly
    client = MagicMock()
    payload = mock_api_key_detected()
    response = aws.format_api_key_detected(payload, client)
    assert "api-key-blah" in response[2]["text"]["text"]


@patch("server.event_handlers.aws.alert_on_call")
def test_format_api_key_detected_extracts_the_url_and_inserts_it_into_blocks(
    alert_on_call_mock,
):
    # Test that the format_api_key_detected function extracts the url properly
    client = MagicMock()
    payload = mock_api_key_detected()
    response = aws.format_api_key_detected(payload, client)
    assert "https://github.com/blah" in response[2]["text"]["text"]


@patch("server.event_handlers.aws.alert_on_call")
def test_format_api_key_detected_extracts_the_on_call_message_and_inserts_it_into_blocks(
    alert_on_call_mock,
):
    # Test that the format_api_key_detected function extracts the on call message properly
    client = MagicMock()
    alert_on_call_mock.return_value = "test message"
    payload = mock_api_key_detected()
    response = aws.format_api_key_detected(payload, client)
    assert "test message" in response[3]["text"]["text"]


@patch("integrations.google_drive.get_google_service")
@patch("commands.incident.google_drive.list_folders")
@patch("commands.incident.google_drive.list_metadata")
@patch("integrations.opsgenie.create_alert")
@patch("integrations.opsgenie.get_on_call_users")
def test_alert_on_call_returns_message(
    get_on_call_users_mock,
    create_alert_mock,
    list_metadata_mock,
    google_list_folders_mock,
    get_google_service_mock,
):
    # Test that the alert_on_call function returns the proper message
    client = MagicMock()
    product = "test"
    api_key = "test_api_key"
    github_repo = "test_repo"
    google_list_folders_mock.return_value = [
        {
            "name": "Notify",
            "id": 12345,
            "appProperties": {"genie_schedule": "test_schedule"},
        }
    ]
    list_metadata_mock.return_value = {
        "name": "Notify",
        "appProperties": {"genie_schedule": "test_schedule"},
    }
    create_alert_mock.return_value = "test result"
    response = aws.alert_on_call(product, client, api_key, github_repo)
    assert (
        "test on-call staff have been notified.\nAn alert has been created in OpsGenie with result: test result."
        in response
    )


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
    return MagicMock(
        Type="Notification",
        MessageId="1e5f5647g-adb5-5d6f-ab5e-c2e508881361",
        TopicArn="arn:aws:sns:ca-central-1:412578375350:test-sre-bot",
        Subject="API Key detected",
        Message="API Key with value token='gcntfy-api-key-blah-00000000-0000-0000-0000-000000000000-00000000-0000-0000-0000-000000000000' has been detected in url='https://github.com/blah'! This key needs to be revoked asap.",
        Timestamp="2023-09-25T20:50:37.868Z",
        SignatureVersion="1",
        Signature="EXAMPLEO0OA1HN4MIHrtym3N6SWqvotsY4EcG+Ty/wrfZcxpQ3mximWM7ZfoYlzZ8NBh4s1XTPuqbl5efK64TEuPgNWBMKsm5Gc2d8H6hoDpLqAOELGl2/xlvWf2CovLH/KPj8xrSwAgOS9jL4r/EEMdXYb705YMMBudu78gooatU9EpVl+1I2MCP2AW0ZJWrcSwYMqxo9yo7H6coyBRlmTxP97PlELXoqXLfufsfFBjZ0eFycndG5A0YHeue82uLF5fIHGpcTjqNzLF0PXuJoS9xVkGx3X7p+dzmRE4rp/swGyKCqbXvgldPRycuj7GSk3r8HLSfzjqHyThnDqMECA==",
        SigningCertURL="https://sns.ca-central-1.amazonaws.com/SimpleNotificationService-56e67fcb41f6fec09b0196692625d385.pem",
        UnsubscribeURL="https://sns.ca-central-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:ca-central-1:412578375350:test-sre-bot:4636a013-5224-4207-91b2-d6d7c7ab7ea7",
    )
