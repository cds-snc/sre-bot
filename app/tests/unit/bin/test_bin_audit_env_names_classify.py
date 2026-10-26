"""Unit tests for the env-name audit's actions.

``classify`` is called with a small hand-built ``Context`` (read, retired, doc-14 rows, parameters and
workflow references), so each action is pinned without reading the env files, GitHub or SSM. The
production-blob cases read the checked-in production configuration, which holds the migrated
``[slack_transport]`` table.
"""

import pytest

from bin.audit_env_names import (
    Context,
    classify,
    missing_workflow_secrets,
    replacement,
    secret_parameters,
    setup_references,
)

pytestmark = pytest.mark.unit

CTX = Context(
    current={"SLACK__BOT_TOKEN", "LOGGING__LOG_LEVEL", "ACCESS_CONFIG_SOURCE"},
    retired={"SLACK_BOT_TOKEN", "LOG_LEVEL", "SESSION_SECRET_KEY", "SLACK_ENABLED"},
    doc14={
        "SLACK_BOT_TOKEN": ("secret SLACK__BOT_TOKEN, read by SlackSettings", "111.4, 111.9"),
        "SLACK_ENABLED": ("production.toml [slack_transport] enabled = true", "112.1"),
        "APP_TOKEN": ("delete", "111.15"),
        "ACCESS_CONFIG_SOURCE": ("file [access] source", "TASK-166"),
        "ENVIRONMENT": ("platform (task definition already sets it)", "111.15"),
        "GHOST": ("file [nowhere] key", "111.99"),
    },
    secrets={"SLACK__BOT_TOKEN": "set"},
    workflow_refs={"GEO_DB_BUCKET": ["refresh_geodb.yml"], "LOG_ANALYTICS_WORKSPACE_ID": ["ci_code.yml"]},
    setup_refs={"GEO_DB_BUCKET": [".devcontainer/maxmind-create.sh"]},
)


def _action(source: str, name: str, state: str = "set", ctx: Context = CTX) -> str:
    return classify(source, name, state, ctx).action


@pytest.mark.parametrize(
    ("name", "state", "action"),
    [
        ("SLACK__BOT_TOKEN", "set", "none"),
        ("AWS_PROFILE", "set", "none"),
        ("LOGGING__LOG_LEVEL", "commented", "none"),
        ("SLACK_BOT_TOKEN", "set", "rename"),
        ("SESSION_SECRET_KEY", "set", "delete"),
        ("SLACK_ENABLED", "set", "delete"),
        ("LOG_LEVEL", "commented", "delete"),
        ("REACT_APP_API_URL", "present", "delete"),
        ("GEO_DB_BUCKET", "present", "none"),
    ],
)
def test_developer_names_get_one_action(name: str, state: str, action: str) -> None:
    assert _action("file app/.env", name, state) == action


def test_the_real_setup_scripts_read_the_geodb_bucket() -> None:
    assert ".devcontainer/maxmind-create.sh" in setup_references()["GEO_DB_BUCKET"]


def test_a_rename_names_the_successor() -> None:
    assert "set SLACK__BOT_TOKEN to the same value" in classify("file app/.env", "SLACK_BOT_TOKEN", "set", CTX).reason


def test_a_superseded_google_id_names_the_secret_that_holds_it_now() -> None:
    verdict = classify("codespaces repo cds-snc/sre-bot", "CORE_VALUES_INTERVIEW_NOTES_TEMPLATE", "present", CTX)

    assert verdict.action == "delete"
    assert "GOOGLE_RESOURCES tal.c" in verdict.reason


def test_a_retired_switch_points_to_its_configuration_key() -> None:
    assert "[slack_transport] enabled" in classify("file app/.env", "SLACK_ENABLED", "set", CTX).reason


@pytest.mark.parametrize(
    ("source", "name", "action"),
    [
        ("actions secret repo cds-snc/sre-bot", "GEO_DB_BUCKET", "none"),
        ("actions secret repo cds-snc/sre-bot", "OLD_SECRET", "delete"),
        ("actions secret org cds-snc (shared with this repo)", "OLD_SECRET", "none"),
        ("dependabot secret repo cds-snc/sre-bot", "OLD_SECRET", "delete"),
    ],
)
def test_actions_names_are_judged_by_workflow_references(source: str, name: str, action: str) -> None:
    assert _action(source, name, "present") == action


def test_a_workflow_reference_with_no_listed_secret_is_a_check() -> None:
    rows = missing_workflow_secrets({"GEO_DB_BUCKET"}, CTX)

    assert [(name, verdict.action) for name, _, verdict in rows] == [("LOG_ANALYTICS_WORKSPACE_ID", "check")]


@pytest.mark.parametrize(
    ("name", "action"),
    [
        ("ENVIRONMENT", "none"),
        ("ACCESS_CONFIG_SOURCE", "none"),
        ("APP_TOKEN", "none"),
        ("SLACK_ENABLED", "none"),
        ("SLACK_BOT_TOKEN", "none"),
        ("GHOST", "check"),
        ("LOGGING__LOG_LEVEL", "check"),
        ("UNLISTED_OLD_NAME", "none"),
    ],
)
def test_production_blob_lines_are_never_hand_edited(name: str, action: str) -> None:
    assert _action("ssm-blob sre-bot-config", name) == action


def test_a_migrated_secret_whose_parameter_is_not_set_is_a_check() -> None:
    ctx = Context(current=CTX.current, doc14=CTX.doc14, secrets={"SLACK__BOT_TOKEN": "placeholder"})

    assert _action("ssm-blob sre-bot-config", "SLACK_BOT_TOKEN", ctx=ctx) == "check"
    assert [verdict.action for _, _, verdict in secret_parameters(ctx)] == ["check"]


def test_replacement_prefers_the_shortest_table_prefixed_name() -> None:
    assert replacement("LOG_LEVEL", {"LOGGING__LOG_LEVEL", "OTHER__LOGGING__LOG_LEVEL"}) == "LOGGING__LOG_LEVEL"
