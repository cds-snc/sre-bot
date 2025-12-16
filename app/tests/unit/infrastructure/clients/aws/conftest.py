import pytest

from infrastructure.clients.aws import AWSClientFactory


@pytest.fixture
def aws_factory():
    """Provide a simple AWSClientFactory instance for unit tests.

    Tests that need to customize boto3 behavior should still monkeypatch
    `infrastructure.clients.aws.client.get_boto3_client` to return fake
    clients. This fixture centralizes the construction and keeps tests
    consistent with the project's testing strategy.
    """
    return AWSClientFactory(aws_region="us-east-1")
