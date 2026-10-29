"""Unit tests for the security_setting_weakened warning raised in the configuration phase.

warn_on_weakened_security reads a HostInfo and a SecuritySettings built with explicit
values; capture_logs records the events. The warning names the setting at fault in
its ``setting`` field and carries no configured value. Production with the dev bypass
on is refused earlier by refuse_dev_bypass_in_production, so the warning never has to
cover it.
"""

import pytest
from structlog.testing import capture_logs

from contracts.configuration import HostInfo
from infrastructure.security.settings import IssuerEntry, SecuritySettings
from server.configuration.host_configuration import warn_on_weakened_security

pytestmark = pytest.mark.unit

BYPASS_TOKEN = "dev-bypass-canary-0001"
ISSUER = IssuerEntry(issuer="https://issuer.example", jwks_uri="https://issuer.example/jwks", audience="aud-canary-0001")


def _host(environment: str) -> HostInfo:
    return HostInfo(environment=environment, git_sha="abc123", public_base_url="http://127.0.0.1:8000")  # type: ignore[arg-type]


def _warnings(host: HostInfo, security: SecuritySettings) -> list[dict[str, object]]:
    with capture_logs() as events:
        warn_on_weakened_security(host, security)
    return [event for event in events if event["event"] == "security_setting_weakened"]


@pytest.mark.parametrize("environment", ["local", "ci"])
def test_the_dev_bypass_outside_production_warns_naming_the_setting(environment: str) -> None:
    """The bypass switched on in a non-production environment logs one WARNING naming it."""
    security = SecuritySettings(dev_bypass_enabled=True, dev_bypass_token=BYPASS_TOKEN, issuers=[ISSUER])

    (event,) = _warnings(_host(environment), security)

    assert event["log_level"] == "warning"
    assert event["setting"] == "security.dev_bypass_enabled"


def test_the_bypass_off_does_not_warn() -> None:
    """With the flag off and an issuer configured, nothing is weakened."""
    assert _warnings(_host("local"), SecuritySettings(issuers=[ISSUER])) == []


@pytest.mark.parametrize("environment", ["local", "ci", "production"])
def test_no_issuers_warns_in_every_environment(environment: str) -> None:
    """An empty issuer list leaves authenticated endpoints failing, so it warns everywhere."""
    (event,) = _warnings(_host(environment), SecuritySettings(issuers=[]))

    assert event["log_level"] == "warning"
    assert event["setting"] == "security.issuers"


def test_the_bypass_and_no_issuers_log_one_warning_each() -> None:
    """Two weakened settings are two events, so a deploy check can count them."""
    events = _warnings(_host("local"), SecuritySettings(dev_bypass_enabled=True, dev_bypass_token=BYPASS_TOKEN))

    assert sorted(str(event["setting"]) for event in events) == ["security.dev_bypass_enabled", "security.issuers"]


def test_no_event_carries_a_configured_value() -> None:
    """Neither the bypass token nor an issuer's audience reaches any field of any event."""
    security = SecuritySettings(dev_bypass_enabled=True, dev_bypass_token=BYPASS_TOKEN, issuers=[ISSUER])

    with capture_logs() as events:
        warn_on_weakened_security(_host("local"), security)

    rendered = str(events)
    assert BYPASS_TOKEN not in rendered
    assert "aud-canary-0001" not in rendered
