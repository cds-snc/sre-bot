"""Read-only smoke test for the AWS shield.

Exercises `AWSShield.execute()` end-to-end against a local endpoint
configured via `AWS_SMOKE_ENDPOINT_URL`. Skips cleanly when that variable
is unset so default CI runs without credentials. The test is
read-only: no writes, no resource creation, no state mutation.
"""

from __future__ import annotations

import os
import dotenv

import pytest

from infrastructure.operations.status import OperationStatus
from integrations.aws.settings import AWSSettings
from integrations.aws.shield import AWSShield

dotenv.load_dotenv()  # for local development; CI sets env vars directly

pytestmark = [pytest.mark.smoke]

_SMOKE_ENDPOINT = os.environ.get("AWS_SMOKE_ENDPOINT_URL")

if _SMOKE_ENDPOINT is None:
    pytest.skip(
        "AWS_SMOKE_ENDPOINT_URL not set; skipping smoke tests.",
        allow_module_level=True,
    )


@pytest.fixture
def shield() -> AWSShield:
    return AWSShield(
        settings=AWSSettings(
            AWS_REGION=os.environ.get("AWS_SMOKE_REGION", "us-east-1"),
            AWS_ENDPOINT_URL=_SMOKE_ENDPOINT,
        )
    )


class TestAWSShieldAgainstLocalInstance:
    """End-to-end smoke against a running local instance."""

    def test_dynamodb_list_tables_succeeds(self, shield):
        result = shield.execute(lambda: shield.dynamodb.list_tables())

        assert result.is_success
        assert "TableNames" in (result.data or {})

    def test_dynamodb_get_item_on_missing_table_classifies_as_not_found(self, shield):
        result = shield.execute(
            lambda: shield.dynamodb.get_item(
                TableName="this-table-does-not-exist-smoke",
                Key={"id": {"S": "1"}},
            )
        )

        assert not result.is_success
        assert result.status in {
            OperationStatus.NOT_FOUND,
            OperationStatus.PERMANENT_ERROR,
        }

    def test_organizations_list_accounts_returns_result(self, shield):
        result = shield.execute(lambda: shield.organizations.list_accounts())

        assert result.status in {
            OperationStatus.SUCCESS,
            OperationStatus.UNAUTHORIZED,
        }

    def test_identity_store_list_users_returns_result(self, shield):
        identity_store_id = os.environ.get("AWS_SMOKE_IDENTITY_STORE_ID", "d-0000000000")
        result = shield.execute(
            lambda: shield.identity_store.list_users(IdentityStoreId=identity_store_id)
        )

        assert result.status in {
            OperationStatus.SUCCESS,
            OperationStatus.UNAUTHORIZED,
            OperationStatus.NOT_FOUND,
        }
