"""Unit tests for the ECS adapter's AWS credentials supplier.

google-auth's built-in AWS source reads only environment variables or EC2 metadata, and
Fargate has neither, so the supplier hands google-auth the botocore session's credentials
(decisions/service-accounts.md rule 5). The botocore session is a fake whose credentials
object returns a different frozen set on each call, as RefreshableCredentials does after a
rotation; no network is used. The assertions show each call reads the current credentials,
the region comes from the session, and a botocore failure surfaces as a RefreshError that
carries a fixed code and none of the library's text, so the client maps it like any refused
token.
"""

from types import SimpleNamespace
from typing import Any

import pytest
from google.auth import aws
from google.auth.exceptions import RefreshError

from integrations.google_workspace.client import BotocoreCredentialsSupplier

pytestmark = pytest.mark.unit


class _RotatingCredentials:
    def __init__(self) -> None:
        self.calls = 0

    def get_frozen_credentials(self) -> Any:
        self.calls += 1
        return SimpleNamespace(access_key=f"AKIA{self.calls}", secret_key=f"secret-{self.calls}", token=f"token-{self.calls}")


class _Session:
    def __init__(self, credentials: Any) -> None:
        self.credentials = credentials
        self.lookups = 0

    def get_credentials(self) -> Any:
        self.lookups += 1
        return self.credentials


def test_each_call_returns_the_current_task_role_credentials() -> None:
    """Rotated task-role credentials are picked up: every call reads the frozen set anew."""
    session = _Session(_RotatingCredentials())
    supplier = BotocoreCredentialsSupplier(session, "ca-central-1")

    first = supplier.get_aws_security_credentials(None, None)
    second = supplier.get_aws_security_credentials(None, None)

    assert isinstance(first, aws.AwsSecurityCredentials)
    assert (first.access_key_id, first.secret_access_key, first.session_token) == ("AKIA1", "secret-1", "token-1")
    assert (second.access_key_id, second.session_token) == ("AKIA2", "token-2")
    assert session.lookups == 1


def test_the_region_is_the_one_resolved_from_the_session() -> None:
    """The region signs the STS GetCallerIdentity request Google verifies."""
    supplier = BotocoreCredentialsSupplier(_Session(_RotatingCredentials()), "ca-central-1")

    assert supplier.get_aws_region(None, None) == "ca-central-1"


def test_no_credentials_in_the_chain_is_a_refused_token() -> None:
    """A task with no role resolves no credentials, which is reported as a fixed code."""
    supplier = BotocoreCredentialsSupplier(_Session(None), "ca-central-1")

    with pytest.raises(RefreshError) as raised:
        supplier.get_aws_security_credentials(None, None)

    assert raised.value.args == ("aws_credentials_unavailable",)


def test_a_botocore_failure_keeps_none_of_its_text() -> None:
    """The library's message may describe the endpoint or the role, so only the code is kept."""

    class _Failing:
        def get_frozen_credentials(self) -> Any:
            raise RuntimeError("container endpoint 169.254.170.2 said role arn:aws:iam::123:role/x")

    supplier = BotocoreCredentialsSupplier(_Session(_Failing()), "ca-central-1")

    with pytest.raises(RefreshError) as raised:
        supplier.get_aws_security_credentials(None, None)

    assert raised.value.args == ("aws_credentials_unavailable",)
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__
