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
    parameter_rows,
    replacement,
    setup_references,
    unprovided_workflow_references,
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
    parameter_states={"SLACK__BOT_TOKEN": "set"},
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


def test_a_parameter_destination_set_ahead_of_its_reader_is_kept() -> None:
    ctx = Context(
        current=CTX.current,
        doc14={"SRE_BOT_EMAIL": ("secret GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL", "111.10.2")},
    )

    verdict = classify("codespaces repo cds-snc/sre-bot", "GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL", "present", ctx)

    assert verdict.action == "none"
    assert "SRE_BOT_EMAIL" in verdict.reason
    assert _action("codespaces repo cds-snc/sre-bot", "GOOGLE_WORKSPACE__TENANT__UNKNOWN", "present", ctx) == "delete"


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
    ("name", "destination"),
    [
        ("SRE_BOT_EMAIL", "secret GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL"),
        ("GCP_SRE_SERVICE_ACCOUNT_KEY_FILE", "secret GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY"),
        ("GOOGLE_WORKSPACE_CUSTOMER_ID", "secret GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID"),
        ("GOOGLE_API_NUM_RETRIES", "[google_workspace] api_num_retries"),
        ("GOOGLE_API_TIMEOUT_SECONDS", "[google_workspace] api_timeout_seconds"),
    ],
)
def test_a_retired_google_name_is_deleted_naming_its_destination(name: str, destination: str) -> None:
    verdict = classify("codespaces repo cds-snc/sre-bot", name, "present", CTX)

    assert verdict.action == "delete"
    assert destination in verdict.reason


@pytest.mark.parametrize(
    ("name", "destination"),
    [
        ("AWS_AUDIT_ACCOUNT_ROLE_ARN", "secret AWS__TENANT__AUDIT_ROLE_ARN"),
        ("AWS_ORG_ACCOUNT_ROLE_ARN", "secret AWS__TENANT__ORG_ROLE_ARN"),
        ("AWS_LOGGING_ACCOUNT_ROLE_ARN", "secret AWS__TENANT__LOGGING_ROLE_ARN"),
        ("AWS_SSO_INSTANCE_ID", "secret AWS__TENANT__INSTANCE_ID"),
        ("AWS_SSO_INSTANCE_ARN", "secret AWS__TENANT__INSTANCE_ARN"),
        ("AWS_SSO_SYSTEM_ADMIN_PERMISSIONS", "secret ACCESS_PERMISSION_SETS__SYSTEM_ADMIN_PERMISSIONS"),
        ("AWS_SSO_VIEW_ONLY_PERMISSIONS", "secret ACCESS_PERMISSION_SETS__VIEW_ONLY_PERMISSIONS"),
        ("AWS_RETRY_MAX_ATTEMPTS", "[aws] retry_max_attempts"),
        ("AWS_RETRY_MODE", "[aws] retry_mode"),
        ("AWS_CONNECT_TIMEOUT_SECONDS", "[aws] connect_timeout_seconds"),
        ("AWS_READ_TIMEOUT_SECONDS", "[aws] read_timeout_seconds"),
        ("AWS_TRANSIENT_RETRY_AFTER_SECONDS", "[aws] transient_retry_after_seconds"),
        ("AWS_NOT_FOUND_CODES", "[aws] not_found_codes"),
        ("AWS_UNAUTHORIZED_CODES", "[aws] unauthorized_codes"),
        ("AWS_TRANSIENT_CODES", "[aws] transient_codes"),
    ],
)
def test_a_retired_aws_name_is_deleted_naming_its_destination(name: str, destination: str) -> None:
    verdict = classify("codespaces repo cds-snc/sre-bot", name, "present", CTX)

    assert verdict.action == "delete"
    assert destination in verdict.reason


@pytest.mark.parametrize(
    ("name", "destination"),
    [
        ("OPENAI_API_KEY", "secret OPENAI__API_KEY"),
        ("OPENAI_BASE_URL", "[openai.tenant] base_url"),
        ("OPENAI_MODEL", "[openai.tenant] model"),
        ("OPENAI_MAX_OUTPUT_TOKENS", "[openai] max_output_tokens"),
        ("OPENAI_TEMPERATURE", "[openai] temperature"),
        ("OPENAI_TIMEOUT_SECONDS", "[openai] timeout_seconds"),
    ],
)
def test_a_retired_openai_name_is_deleted_naming_its_destination(name: str, destination: str) -> None:
    verdict = classify("codespaces repo cds-snc/sre-bot", name, "present", CTX)

    assert verdict.action == "delete"
    assert destination in verdict.reason


@pytest.mark.parametrize(
    ("name", "destination"),
    [
        ("NOTIFY_SRE_USER_NAME", "secret NOTIFY__SRE_USER_NAME"),
        ("NOTIFY_SRE_CLIENT_SECRET", "secret NOTIFY__SRE_CLIENT_SECRET"),
        ("NOTIFY_API_URL", "[notify.tenant] api_url"),
        ("TRELLO_APP_KEY", "secret TRELLO__TENANT__APP_KEY"),
        ("TRELLO_TOKEN", "secret TRELLO__TENANT__TOKEN"),
        ("TRELLO_ATIP_BOARD", "secret TRELLO__ATIP_BOARD"),
        ("OPSGENIE_INTEGRATIONS_KEY", "secret OPSGENIE__INTEGRATIONS_KEY"),
        ("MAXMIND_DB_PATH", "[maxmind.tenant] database_path"),
    ],
)
def test_a_retired_vendor_name_is_deleted_naming_its_destination(name: str, destination: str) -> None:
    verdict = classify("codespaces repo cds-snc/sre-bot", name, "present", CTX)

    assert verdict.action == "delete"
    assert destination in verdict.reason


@pytest.mark.parametrize("name", ["AWS_REGION", "AWS_DEFAULT_REGION", "AWS_ENDPOINT_URL_DYNAMODB", "AWS_ACCESS_KEY_ID"])
def test_an_aws_sdk_name_is_kept(name: str) -> None:
    """The SDK reads these names itself, so no AWS hint may turn them into a delete."""
    assert classify("codespaces repo cds-snc/sre-bot", name, "present", CTX).action == "none"


def test_the_retired_flat_lease_ttl_is_deleted_for_its_scheduler_key_not_renamed() -> None:
    """Without the hint the guess would be a SCHEDULER__ rename; the value is a configuration key."""
    ctx = Context(current={"SCHEDULER__DEFAULT_TIER2_LEASE_TTL_SECONDS"}, retired={"DEFAULT_TIER2_LEASE_TTL_SECONDS"})

    verdict = classify("file app/.env", "DEFAULT_TIER2_LEASE_TTL_SECONDS", "set", ctx)

    assert verdict.action == "delete"
    assert "[scheduler] default_tier2_lease_ttl_seconds" in verdict.reason


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
    rows = unprovided_workflow_references({"GEO_DB_BUCKET"}, CTX)

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
    ctx = Context(current=CTX.current, doc14=CTX.doc14, parameter_states={"SLACK__BOT_TOKEN": "placeholder"})

    assert _action("ssm-blob sre-bot-config", "SLACK_BOT_TOKEN", ctx=ctx) == "check"
    assert [verdict.action for _, _, verdict in parameter_rows(ctx)] == ["check"]


def test_replacement_prefers_the_shortest_table_prefixed_name() -> None:
    assert replacement("LOG_LEVEL", {"LOGGING__LOG_LEVEL", "OTHER__LOGGING__LOG_LEVEL"}) == "LOGGING__LOG_LEVEL"
