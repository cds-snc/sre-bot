"""Unit tests for the MaxMind client without a [maxmind.tenant] entry.

Each test installs files from tmp_path with every MaxMind variable removed and the cached
providers cleared (the autouse isolation fixture). ``geoip2.database.Reader`` is replaced by a
recording stub, so the tests prove no database is opened when MaxMind is not configured and the
configured path is the one opened when it is.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from contracts.operations import OperationStatus
from contracts.operations.codes import ErrorCode
from integrations.maxmind.client import get_maxmind_client
from tests.unit.integrations.maxmind.conftest import DATABASE_PATH, TENANT, install_maxmind_files

pytestmark = pytest.mark.unit


@pytest.fixture
def reader(monkeypatch: pytest.MonkeyPatch) -> Mock:
    factory = Mock()
    monkeypatch.setattr("geoip2.database.Reader", factory)
    return factory


@pytest.mark.parametrize("operation", ["geolocate", "healthcheck"])
def test_without_a_tenant_the_client_reports_not_configured(tmp_path: Path, reader: Mock, operation: str) -> None:
    install_maxmind_files(tmp_path)
    client = get_maxmind_client()

    result = client.geolocate("8.8.8.8") if operation == "geolocate" else client.healthcheck()

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.CONFIG_NOT_CONFIGURED
    reader.assert_not_called()


def test_with_a_tenant_the_client_opens_the_configured_database(tmp_path: Path, reader: Mock) -> None:
    install_maxmind_files(tmp_path, environment=TENANT)

    get_maxmind_client().geolocate("8.8.8.8")

    reader.assert_called_once_with(DATABASE_PATH)
