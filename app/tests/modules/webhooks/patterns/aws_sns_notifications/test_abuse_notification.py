from unittest.mock import MagicMock
from modules.webhooks.patterns.aws_sns_notification import abuse_notification
import json


def mock_abuse_alert():
    return MagicMock(
        Type="Notification",
        MessageId="0da238f6-da6c-5214-96e1-635d27a9b79b",
        TopicArn="arn:aws:sns:ca-central-1:017790921725:test-sre-bot",
        Subject="",
        Message='{"version":"0","id":"7bf73129-1428-4cd3-a780-95db273d1602","detail-type":"AWS Health Abuse Event","source":"aws_sns.health","account":"123456789012","time":"2018-08-01T06:27:57Z","region":"global","resources":["arn:aws:ec2:us-east-1:123456789012:instance/i-abcd1111","arn:aws:ec2:us-east-1:123456789012:instance/i-abcd2222"],"detail":{"eventArn":"arn:aws:health:global::event/AWS_ABUSE_DOS_REPORT_92387492375_4498_2018_08_01_02_33_00","service":"ABUSE","eventTypeCode":"AWS_ABUSE_DOS_REPORT","eventTypeCategory":"issue","startTime":"Wed, 01 Aug 2018 06:27:57 GMT","eventDescription":[{"language":"en_US","latestDescription":"A description of the event will be provided here"}],"affectedEntities":[{"entityValue":"arn:aws:ec2:us-east-1:123456789012:instance/i-abcd1111"},{"entityValue":"arn:aws:ec2:us-east-1:123456789012:instance/i-abcd2222"}]}}',
        Timestamp="2022-09-26T19:20:37.147Z",
        SignatureVersion="1",
        Signature="HLsCTKHEC2FXGe6LFkV/JGD7k/apzJZD42R8ph4AzcD9NcrxZyjINTyPFe1zMtg3kcGSge2J3MqFcTTyQJtkRrKZZftIVZRflwWKu4OLHt1atHSOavI8n7Qh3bRtwR5C3mezhtu6oWbfEdTXAuyz4AWcZ0L9dxE4B3bOMS302ViQA3hIfjSlGLRr+j/Ra7+IbzY35QUJLxtVcmcAAw/ByuyXeDRy+6qhJtKndOTeMBLTKAQlIOPubyJP1Q2BWo0spREmIESnPtB14c5k+6LWxa/srPjfOWu66ICUNnydKnvf5EuIlpooycLldttvDtwmD2NZt6kQr2FJhkqARyr/Ng==",
        SigningCertURL="https://sns.ca-central-1.amazonaws.com/SimpleNotificationService-56e67fcb41f6fec09b0196692625d385.pem",
        UnsubscribeURL="https://sns.ca-central-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:ca-central-1:017790921725:test-sre-bot:4636a013-5224-4207-91b2-d6d7c7ab7ea7",
    )


def test_abuse_notification_handler_extracts_account_id():
    client = MagicMock()
    payload = mock_abuse_alert()
    blocks = abuse_notification.handle_abuse_notification(payload, client)
    assert any("017790921725" in b["text"]["text"] for b in blocks if "text" in b)


def test_abuse_notification_matcher():
    payload = mock_abuse_alert()
    parsed_message = json.loads(payload.Message)
    assert abuse_notification.is_abuse_notification(payload, parsed_message)
