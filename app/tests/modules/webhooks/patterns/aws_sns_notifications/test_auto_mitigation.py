from unittest.mock import MagicMock
from modules.webhooks.patterns.aws_sns_notification import auto_mitigation


def mock_auto_mitigation():
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


def test_auto_mitigation_handler_extracts_security_group():
    client = MagicMock()
    payload = mock_auto_mitigation()
    blocks = auto_mitigation.handle_auto_mitigation(payload, client)
    assert any(
        "sg-09d2738530b93476d" in b["text"]["text"] for b in blocks if "text" in b
    )


def test_auto_mitigation_handler_extracts_account():
    client = MagicMock()
    payload = mock_auto_mitigation()
    blocks = auto_mitigation.handle_auto_mitigation(payload, client)
    assert any("017790921725" in b["text"]["text"] for b in blocks if "text" in b)


def test_auto_mitigation_handler_extracts_port():
    client = MagicMock()
    payload = mock_auto_mitigation()
    blocks = auto_mitigation.handle_auto_mitigation(payload, client)
    assert any("22" in b["text"]["text"] for b in blocks if "text" in b)


def test_auto_mitigation_handler_extracts_user():
    client = MagicMock()
    payload = mock_auto_mitigation()
    blocks = auto_mitigation.handle_auto_mitigation(payload, client)
    assert any(
        "test_user@cds-snc.ca" in b["text"]["text"] for b in blocks if "text" in b
    )


def test_auto_mitigation_matcher():
    payload = mock_auto_mitigation()
    assert auto_mitigation.is_auto_mitigation(payload, None)
