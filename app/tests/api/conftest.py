"""Shared fixtures for the API route tests.

These tests boot the real FastAPI lifespan through ``TestClient``. Any feature
warmup that builds an AWS client with a role ARN would otherwise perform a live
STS ``AssumeRole`` call, so the seam is stubbed for every test in this tree.
"""

from collections.abc import Iterator

import pytest

_FAKE_ASSUMED_CREDENTIALS = {
    "AccessKeyId": "ASIATESTASSUMEDKEY",
    "SecretAccessKey": "test-assumed-secret",
    "SessionToken": "test-assumed-session-token",
}


@pytest.fixture(autouse=True)
def _autouse_stub_aws_assume_role(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Stub the AWS AssumeRole seam so app startup never reaches STS.

    Stub strategy: replace ``integrations.aws.client._assume_role_credentials``
    with a function returning static temporary credentials; the client factory
    then builds a normal boto3 session from them without any network call.
    """
    monkeypatch.setattr(
        "integrations.aws.client._assume_role_credentials",
        lambda sts, role_arn, session_name: dict(_FAKE_ASSUMED_CREDENTIALS),
    )
    yield
