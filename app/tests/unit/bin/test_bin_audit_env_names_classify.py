"""Unit tests for the env-name audit's actions.

``classify`` is called with a small hand-built ``Context`` (read names, a retired map and workflow and
setup references), so each action is pinned without reading the env files or GitHub. The real
``RETIRED`` map and the real setup files are read only where the test is about them.
"""

import pytest

from bin.audit_env_names import (
    RETIRED,
    Context,
    classify,
    setup_references,
    unprovided_workflow_references,
)

pytestmark = pytest.mark.unit

CTX = Context(
    current={"SLACK__BOT_TOKEN", "LOGGING__LOG_LEVEL"},
    retired={
        "SLACK_BOT_TOKEN": "secret SLACK__BOT_TOKEN",
        "SLACK_ENABLED": "[slack_transport] enabled",
        "SESSION_SECRET_KEY": "nothing (no reader)",
    },
    workflow_refs={"GEO_DB_BUCKET": ["refresh_geodb.yml"], "LOG_ANALYTICS_WORKSPACE_ID": ["ci_code.yml"]},
    setup_refs={"GEO_DB_BUCKET": [".devcontainer/maxmind-create.sh"]},
)
SOURCES = (
    "file app/.env",
    "codespaces repo cds-snc/sre-bot",
    "codespaces user (reaches cds-snc/sre-bot)",
    "actions secret repo cds-snc/sre-bot",
    "actions variable repo cds-snc/sre-bot",
    "dependabot secret repo cds-snc/sre-bot",
)


def _action(source: str, name: str, state: str = "set", ctx: Context = CTX) -> str:
    return classify(source, name, state, ctx).action


@pytest.mark.parametrize(
    ("name", "state", "action"),
    [
        ("SLACK__BOT_TOKEN", "set", "none"),
        ("AWS_PROFILE", "set", "none"),
        ("LOGGING__LOG_LEVEL", "commented", "none"),
        ("SLACK_BOT_TOKEN", "set", "delete"),
        ("SESSION_SECRET_KEY", "set", "delete"),
        ("SLACK_ENABLED", "set", "delete"),
        ("SESSION_SECRET_KEY", "commented", "delete"),
        ("REACT_APP_API_URL", "present", "check"),
        ("UNREAD_LINE", "commented", "check"),
        ("GEO_DB_BUCKET", "present", "none"),
    ],
)
def test_developer_names_get_one_action(name: str, state: str, action: str) -> None:
    assert _action("file app/.env", name, state) == action


def test_a_retired_name_whose_value_moved_to_a_secret_names_the_secret_to_copy_to() -> None:
    verdict = classify("codespaces repo cds-snc/sre-bot", "SLACK_BOT_TOKEN", "present", CTX)

    assert verdict.action == "delete"
    assert verdict.new == "SLACK__BOT_TOKEN"


def test_a_retired_switch_points_to_its_configuration_key() -> None:
    verdict = classify("file app/.env", "SLACK_ENABLED", "set", CTX)

    assert verdict.reason == "retired; set [slack_transport] enabled instead"
    assert verdict.new is None


def test_the_real_setup_scripts_read_the_geodb_bucket() -> None:
    assert ".devcontainer/maxmind-create.sh" in setup_references()["GEO_DB_BUCKET"]


@pytest.mark.parametrize("name", ["AWS_REGION", "AWS_DEFAULT_REGION", "AWS_ENDPOINT_URL_DYNAMODB", "AWS_ACCESS_KEY_ID"])
def test_an_aws_sdk_name_is_kept(name: str) -> None:
    """The SDK reads these names itself."""
    assert classify("codespaces repo cds-snc/sre-bot", name, "present", CTX).action == "none"


@pytest.mark.parametrize(
    ("source", "name", "action"),
    [
        ("actions secret repo cds-snc/sre-bot", "GEO_DB_BUCKET", "none"),
        ("actions secret repo cds-snc/sre-bot", "OLD_SECRET", "check"),
        ("actions secret org cds-snc (shared with this repo)", "OLD_SECRET", "none"),
        ("dependabot secret repo cds-snc/sre-bot", "OLD_SECRET", "check"),
        ("actions secret repo cds-snc/sre-bot", "SLACK_ENABLED", "delete"),
        ("actions variable repo cds-snc/sre-bot", "SESSION_SECRET_KEY", "delete"),
    ],
)
def test_actions_names_are_judged_by_workflow_references(source: str, name: str, action: str) -> None:
    assert _action(source, name, "present") == action


def test_a_workflow_reference_with_no_listed_secret_is_a_check() -> None:
    rows = unprovided_workflow_references({"GEO_DB_BUCKET"}, CTX)

    assert [(name, verdict.action) for name, _, verdict in rows] == [("LOG_ANALYTICS_WORKSPACE_ID", "check")]


@pytest.mark.parametrize("name", ["GCP_SRE_SERVICE_ACCOUNT_KEY_FILE", "GOOGLE_PICKLE_STRING"])
def test_the_retired_terraform_inputs_are_deleted_from_actions(name: str) -> None:
    """Their workflow lines and terraform variable are gone; the retired map is the evidence."""
    ctx = Context(current=set(), retired=RETIRED)

    assert _action("actions secret repo cds-snc/sre-bot", name, "present", ctx) == "delete"
    assert _action("dependabot secret repo cds-snc/sre-bot", name, "present", ctx) == "delete"


@pytest.mark.parametrize("source", SOURCES)
def test_maxmind_key_is_never_deleted(source: str) -> None:
    """The devcontainer passes MAXMIND_KEY to the GeoIP updater as LICENSE_KEY; it is never retired, even
    when no reference is found, so no audit row may plan its deletion."""
    ctx = Context(current=set(), retired=RETIRED)

    assert "MAXMIND_KEY" not in RETIRED
    assert _action(source, "MAXMIND_KEY", "present", ctx) != "delete"
    assert _action(source, "MAXMIND_KEY", "commented", ctx) != "delete"
