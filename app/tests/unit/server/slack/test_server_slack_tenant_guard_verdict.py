"""Unit tests for the Slack tenant rule: which received ids match the configured tenant.

check_slack_tenant is pure: it takes the configured tenant entry and the
installation-scoped ids a request carries and returns the mismatch or None.
Each case states one configuration and one request, so a failure names the
rule that broke.
"""

import pytest

from integrations.slack.settings import SlackTenant
from server.slack.tenant_guard import TenantMismatch, check_slack_tenant

pytestmark = pytest.mark.unit

TEAM = SlackTenant(team_id="T0TEAM")
ORG = SlackTenant(enterprise_id="E0ORG")
BOTH = SlackTenant(team_id="T0TEAM", enterprise_id="E0ORG")


@pytest.mark.parametrize(
    ("tenant", "team_id", "enterprise_id"),
    [
        pytest.param(TEAM, "T0TEAM", None, id="configured team"),
        pytest.param(BOTH, "T0TEAM", "E0ORG", id="configured team and org"),
        pytest.param(ORG, "T0ANYWORKSPACE", "E0ORG", id="org-wide install, any workspace of the org"),
        pytest.param(ORG, None, "E0ORG", id="org-wide install, request without a workspace"),
    ],
)
def test_matching_request_has_no_mismatch(tenant: SlackTenant, team_id: str | None, enterprise_id: str | None) -> None:
    """A request naming the configured ids passes; an unconfigured team id is not compared."""
    assert check_slack_tenant(tenant, team_id=team_id, enterprise_id=enterprise_id) is None


@pytest.mark.parametrize(
    ("tenant", "team_id", "enterprise_id"),
    [
        pytest.param(TEAM, "T0OTHER", None, id="other workspace"),
        pytest.param(TEAM, None, None, id="no workspace against a configured team"),
        pytest.param(TEAM, "T0TEAM", "E0ORG", id="an Enterprise org the settings do not name"),
        pytest.param(ORG, "T0TEAM", "E0OTHER", id="other Enterprise org"),
        pytest.param(ORG, "T0TEAM", None, id="no Enterprise org against a configured org"),
        pytest.param(BOTH, "T0OTHER", "E0ORG", id="other workspace of the configured org"),
    ],
)
def test_mismatching_request_names_expected_and_received_ids(
    tenant: SlackTenant, team_id: str | None, enterprise_id: str | None
) -> None:
    """Any configured id the request does not carry, or an org the settings do not name, is a mismatch."""
    mismatch = check_slack_tenant(tenant, team_id=team_id, enterprise_id=enterprise_id)

    assert mismatch == TenantMismatch(
        expected_team_id=tenant.team_id,
        expected_enterprise_id=tenant.enterprise_id,
        received_team_id=team_id,
        received_enterprise_id=enterprise_id,
    )
