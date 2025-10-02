from unittest.mock import MagicMock
from modules.webhooks.patterns.aws_sns_notification import iam_user


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


def test_iam_user_handler_extracts_user_created():
    client = MagicMock()
    payload = mock_new_iam_user()
    blocks = iam_user.handle_iam_user_notification(payload, client)
    assert any("user_created" in b["text"]["text"] for b in blocks if "text" in b)


def test_iam_user_handler_extracts_account():
    client = MagicMock()
    payload = mock_new_iam_user()
    blocks = iam_user.handle_iam_user_notification(payload, client)
    assert any("412578375350" in b["text"]["text"] for b in blocks if "text" in b)


def test_iam_user_handler_extracts_user():
    client = MagicMock()
    payload = mock_new_iam_user()
    blocks = iam_user.handle_iam_user_notification(payload, client)
    assert any(
        "test_user@cds-snc.ca" in b["text"]["text"] for b in blocks if "text" in b
    )


def test_iam_user_matcher():
    payload = mock_new_iam_user()
    assert iam_user.is_iam_user_notification(payload, None)
