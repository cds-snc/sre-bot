from unittest.mock import MagicMock
from modules.webhooks.patterns.aws_sns_notification import budget_notification


def mock_budget_alert():
    return MagicMock(
        Type="Notification",
        MessageId="0da238f6-da6c-5214-96e1-635d27a9b79b",
        TopicArn="arn:aws:sns:ca-central-1:017790921725:test-sre-bot",
        Subject="AWS Budgets: Test Budget has exceeded your alert threshold",
        Message="AWS Budget Notification September 26, 2022\nAWS Account 017790921725\n\nDear AWS Customer,\n\nYou requested that we alert you when the ACTUAL Cost associated with your Test Budget budget is greater than $0.16 for the current month. The ACTUAL Cost associated with this budget is $0.59. You can find additional details below and by accessing the AWS Budgets dashboard [1].\n\nBudget Name: Test Budget\nBudget Type: Cost\nBudgeted Amount: $0.20\nAlert Type: ACTUAL\nAlert Threshold: > $0.16\nACTUAL Amount: $0.59\n\n[1] https://console.aws_sns.amazon.com/billing/home#/budgets\n",
        Timestamp="2022-09-26T19:20:37.147Z",
        SignatureVersion="1",
        Signature="HLsCTKHEC2FXGe6LFkV/JGD7k/apzJZD42R8ph4AzcD9NcrxZyjINTyPFe1zMtg3kcGSge2J3MqFcTTyQJtkRrKZZftIVZRflwWKu4OLHt1atHSOavI8n7Qh3bRtwR5C3mezhtu6oWbfEdTXAuyz4AWcZ0L9dxE4B3bOMS302ViQA3hIfjSlGLRr+j/Ra7+IbzY35QUJLxtVcmcAAw/ByuyXeDRy+6qhJtKndOTeMBLTKAQlIOPubyJP1Q2BWo0spREmIESnPtB14c5k+6LWxa/srPjfOWu66ICUNnydKnvf5EuIlpooycLldttvDtwmD2NZt6kQr2FJhkqARyr/Ng==",
        SigningCertURL="https://sns.ca-central-1.amazonaws.com/SimpleNotificationService-56e67fcb41f6fec09b0196692625d385.pem",
        UnsubscribeURL="https://sns.ca-central-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:ca-central-1:017790921725:test-sre-bot:4636a013-5224-4207-91b2-d6d7c7ab7ea7",
    )


def test_budget_notification_handler_extracts_account_id():
    client = MagicMock()
    payload = mock_budget_alert()
    blocks = budget_notification.handle_budget_notification(payload, client)
    assert any("017790921725" in b["text"]["text"] for b in blocks if "text" in b)


def test_budget_notification_handler_adds_subject():
    client = MagicMock()
    payload = mock_budget_alert()
    blocks = budget_notification.handle_budget_notification(payload, client)
    assert blocks[2]["text"]["text"] == payload.Subject


def test_budget_notification_handler_adds_message():
    client = MagicMock()
    payload = mock_budget_alert()
    blocks = budget_notification.handle_budget_notification(payload, client)
    assert blocks[3]["text"]["text"] == payload.Message


def test_budget_notification_matcher():
    payload = mock_budget_alert()
    assert budget_notification.is_budget_notification(payload, None)
