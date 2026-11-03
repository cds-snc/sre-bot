"""The edge allow-list agrees with every route the application can mount.

decisions/security.md: every mounted route is reachable at the edge, the WAF allow-list only
drops paths nothing serves, and authentication stays in the application. The route table comes
from edge_route_probe, run in a fresh interpreter: the real create_app plus every installed
plugin's register_routes, enabled or not, so a new plugin's routes are checked with no change
here. The allow-list is terraform/authorized_endpoints.json, the file the WAF rule reads.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from server.plugins.manager import installed_plugin_names
from tests.unit.server.edge_allow_list import (
    ALLOW_LIST_FILE,
    REPO_ROOT,
    MountedRoute,
    authentication_violations,
    edge_violations,
    load_allow_list,
)
from tests.unit.server.edge_route_probe import MARKER

APP_DIR = Path(__file__).resolve().parents[3]
PROBE_TIMEOUT_SECONDS = 120
API_PREFIX = "/api/v1/"

# Mounted routes the edge must block, each with the reason. Every other mounted route is public
# at the edge; an entry here is a reviewed decision, never a way to hide a served route.
INTENTIONALLY_INTERNAL: dict[str, str] = {}

# Routes under /api/v1/ that answer without a Backstage token, each with the decision behind it.
PUBLIC_BY_DECISION = {
    "/api/v1/hook/{webhook_id}": "webhook tier (decisions/security.md), the /hook/{webhook_id} handler at its second mount point",
}

# Allow-list entries the load balancer answers before the app sees the request.
ALB_SERVED = {"/.well-known/security.txt": "fixed-response listener rule in terraform/alb.tf"}


@pytest.fixture(scope="module")
def inventory() -> dict[str, object]:
    env = {**os.environ, "PYTHONPATH": str(APP_DIR), "PYTHONWARNINGS": "ignore"}
    env.update({"AWS_ACCESS_KEY_ID": "edge-probe", "AWS_SECRET_ACCESS_KEY": "edge-probe", "AWS_EC2_METADATA_DISABLED": "true"})
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "tests.unit.server.edge_route_probe"],
        cwd=APP_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=PROBE_TIMEOUT_SECONDS,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    marked = [line for line in result.stdout.splitlines() if line.startswith(MARKER)]
    assert len(marked) == 1, result.stdout[-2000:]
    return json.loads(marked[0].removeprefix(MARKER))


@pytest.fixture(scope="module")
def routes(inventory: dict[str, object]) -> list[MountedRoute]:
    rows = inventory["routes"]
    assert isinstance(rows, list)
    return [MountedRoute(row["path"], tuple(row["methods"]), row["kind"], row["authenticated"]) for row in rows]


def test_inventory_covers_every_installed_plugin(inventory: dict[str, object]) -> None:
    """A plugin left out of the probe would hide its routes from the edge check."""
    assert inventory["plugins"] == installed_plugin_names()


def test_every_mounted_route_is_reachable_or_listed_internal(routes: list[MountedRoute]) -> None:
    assert edge_violations(routes, load_allow_list(), INTENTIONALLY_INTERNAL, ALB_SERVED) == []


def test_every_api_route_authenticates_unless_public_by_decision(routes: list[MountedRoute]) -> None:
    """Opening the /api/v1/ prefix at the edge leaves the app's authentication as the only gate."""
    assert any(route.authenticated for route in routes), (
        "probe found no authenticated route: get_current_user detection is broken"
    )
    assert authentication_violations(routes, API_PREFIX, PUBLIC_BY_DECISION) == []


def test_the_waf_rule_reads_the_allow_list_file() -> None:
    """The file this test checks is the one terraform applies, and no second copy exists."""
    terraform = REPO_ROOT / "terraform"
    assert f'jsondecode(file("${{path.module}}/{ALLOW_LIST_FILE.name}"))' in (terraform / "local.tf").read_text()
    assert "for_each = local.authorized_endpoints" in (terraform / "waf.tf").read_text()
    assert "authorized_endpoints_with_constraints" not in (terraform / "variables.tf").read_text()
