"""Unit tests for the env-name coverage audit.

``coverage_rows`` is called with hand-built doc-14 rows, terraform names and collected TSV entries, so
each gap is pinned without reading doc-14, ``terraform/ssm.tf``, GitHub or SSM. ``terraform_parameters``
reads a small ``ssm.tf`` written to a temporary directory.
"""

from pathlib import Path

import pytest

from bin.audit_env_coverage import coverage_rows, terraform_parameters

pytestmark = pytest.mark.unit

DOC14 = {
    "SLACK_BOT_TOKEN": ("secret SLACK__BOT_TOKEN, read by SlackSettings", "111.4, 111.9"),
    "TRELLO_ATIP_BOARD": ("secret TRELLO__ATIP_BOARD (non-public value)", "111.12"),
    "AWS_AUDIT_ACCOUNT_ROLE_ARN": (
        "secret AWS__TENANT__AUDIT_ROLE_ARN (non-public value; development only: production sets no audit role)",
        "111.11.1",
    ),
    "NOTIFY_API_URL": ("file [notify] api_url", "111.12"),
}
EXAMPLE = "file app/.env.example"
CODESPACES = "codespaces repo cds-snc/sre-bot"


def _rows(terraform: set[str], entries: list[tuple[str, str, str]]) -> dict[str, tuple[str, str]]:
    return {name: (verdict.action, verdict.reason) for name, _, verdict in coverage_rows(DOC14, terraform, entries)}


def _complete(name: str, old: str) -> list[tuple[str, str, str]]:
    return [
        ("ssm-param", name, "set"),
        ("ssm-blob sre-bot-config", old, "set"),
        (CODESPACES, name, "present"),
        (EXAMPLE, name, "commented"),
    ]


def test_a_parameter_terraform_creates_sets_and_every_place_provides_needs_nothing() -> None:
    """A doc-14 secret that terraform creates, SSM holds, Codespaces provides and .env.example names is none."""
    rows = _rows({"SLACK__BOT_TOKEN"}, _complete("SLACK__BOT_TOKEN", "SLACK_BOT_TOKEN"))

    assert rows["SLACK__BOT_TOKEN"][0] == "none"


def test_a_doc14_secret_terraform_does_not_create_is_a_check() -> None:
    """doc-14 moving a production value to a parameter that ssm.tf lacks is caught before the apply."""
    rows = _rows(set(), [("ssm-blob sre-bot-config", "TRELLO_ATIP_BOARD", "set")])

    action, reason = rows["TRELLO__ATIP_BOARD"]
    assert action == "check"
    assert "terraform/ssm.tf does not create it" in reason


def test_a_terraform_parameter_no_doc14_row_names_is_a_check() -> None:
    """A name in ssm.tf that no doc-14 row moves anything to has no recorded source."""
    rows = _rows({"GHOST__KEY"}, [("ssm-param", "GHOST__KEY", "set")])

    action, reason = rows["GHOST__KEY"]
    assert action == "check"
    assert "no doc-14 row" in reason


def test_a_development_only_name_terraform_creates_is_a_check() -> None:
    """A development-only value must have no parameter: its placeholder would reach production."""
    rows = _rows({"AWS__TENANT__AUDIT_ROLE_ARN"}, [])

    action, reason = rows["AWS__TENANT__AUDIT_ROLE_ARN"]
    assert action == "check"
    assert "development only" in reason


def test_a_development_only_name_without_a_parameter_needs_no_terraform() -> None:
    """A development-only value with no parameter, provided in Codespaces and the example, is none."""
    entries = [(CODESPACES, "AWS__TENANT__AUDIT_ROLE_ARN", "present"), (EXAMPLE, "AWS__TENANT__AUDIT_ROLE_ARN", "set")]

    assert _rows(set(), entries)["AWS__TENANT__AUDIT_ROLE_ARN"][0] == "none"


@pytest.mark.parametrize(
    ("blob_state", "expected"),
    [("set", "put-parameter from TRELLO_ATIP_BOARD"), (None, "no TRELLO_ATIP_BOARD line")],
)
def test_a_placeholder_parameter_names_its_source_line_or_its_absence(blob_state: str | None, expected: str) -> None:
    """A parameter still on the placeholder says where its value comes from, or that nothing supplies it."""
    entries = [("ssm-param", "TRELLO__ATIP_BOARD", "placeholder")]
    if blob_state:
        entries.append(("ssm-blob sre-bot-config", "TRELLO_ATIP_BOARD", blob_state))

    action, reason = _rows({"TRELLO__ATIP_BOARD"}, entries)["TRELLO__ATIP_BOARD"]
    assert action == "check"
    assert expected in reason


def test_a_parameter_terraform_has_not_created_yet_waits_for_the_apply() -> None:
    """A name in ssm.tf with no parameter in SSM is pending tf_apply."""
    entries = [("ssm-param", "SLACK__BOT_TOKEN", "set"), ("ssm-blob sre-bot-config", "TRELLO_ATIP_BOARD", "set")]

    action, reason = _rows({"SLACK__BOT_TOKEN", "TRELLO__ATIP_BOARD"}, entries)["TRELLO__ATIP_BOARD"]
    assert action == "check"
    assert "tf_apply" in reason


def test_ssm_states_are_not_judged_when_the_ssm_section_was_skipped() -> None:
    """Without any SSM rows (no AWS credentials) the parameter and source columns are unknown, not missing."""
    entries = [(CODESPACES, "TRELLO__ATIP_BOARD", "present"), (EXAMPLE, "TRELLO__ATIP_BOARD", "set")]

    assert _rows({"TRELLO__ATIP_BOARD"}, entries)["TRELLO__ATIP_BOARD"][0] == "none"


def test_codespaces_holding_only_the_old_name_is_a_check() -> None:
    """A Codespace still provides the old name but not the new one: development loses the value."""
    entries = [*_complete("TRELLO__ATIP_BOARD", "TRELLO_ATIP_BOARD")[:2], (CODESPACES, "TRELLO_ATIP_BOARD", "present")]
    entries.append((EXAMPLE, "TRELLO__ATIP_BOARD", "commented"))

    action, reason = _rows({"TRELLO__ATIP_BOARD"}, entries)["TRELLO__ATIP_BOARD"]
    assert action == "check"
    assert "Codespaces has TRELLO_ATIP_BOARD" in reason


def test_a_name_missing_from_the_env_example_is_a_check() -> None:
    """Every name supplied through the environment has a line in app/.env.example, commented or not."""
    entries = [e for e in _complete("SLACK__BOT_TOKEN", "SLACK_BOT_TOKEN") if e[0] != EXAMPLE]
    entries.append((EXAMPLE, "OTHER", "set"))

    action, reason = _rows({"SLACK__BOT_TOKEN"}, entries)["SLACK__BOT_TOKEN"]
    assert action == "check"
    assert "app/.env.example" in reason


def test_terraform_parameters_reads_the_secret_names_set(tmp_path: Path) -> None:
    """The names come from the sre_bot_secret_names set, not from other quoted strings in the file."""
    tf = tmp_path / "ssm.tf"
    tf.write_text(
        'resource "aws_ssm_parameter" "x" {\n  name = "gcp_sre_service_account_key"\n}\n'
        'locals {\n  sre_bot_secret_names = toset([\n    "SLACK__BOT_TOKEN",\n    "TRELLO__ATIP_BOARD",\n  ])\n}\n'
    )

    assert terraform_parameters(tf) == {"SLACK__BOT_TOKEN", "TRELLO__ATIP_BOARD"}


def test_a_parameter_not_created_yet_also_says_whether_its_source_line_exists() -> None:
    """Before the apply, a pending parameter whose blob line is absent is flagged, so it is dropped from ssm.tf."""
    entries = [("ssm-param", "SLACK__BOT_TOKEN", "set"), ("ssm-blob sre-bot-config", "SLACK_BOT_TOKEN", "set")]

    _, reason = _rows({"SLACK__BOT_TOKEN", "TRELLO__ATIP_BOARD"}, entries)["TRELLO__ATIP_BOARD"]
    assert "tf_apply pending" in reason
    assert "no TRELLO_ATIP_BOARD line" in reason


def test_a_development_only_name_production_sets_is_a_check() -> None:
    """doc-14 calling a value development only while a production blob line sets it would drop it in production."""
    entries = [
        ("ssm-param", "SLACK__BOT_TOKEN", "set"),
        ("ssm-blob sre-bot-config", "AWS_AUDIT_ACCOUNT_ROLE_ARN", "set"),
        (CODESPACES, "AWS__TENANT__AUDIT_ROLE_ARN", "present"),
    ]

    action, reason = _rows({"SLACK__BOT_TOKEN"}, entries)["AWS__TENANT__AUDIT_ROLE_ARN"]
    assert action == "check"
    assert "production sets AWS_AUDIT_ACCOUNT_ROLE_ARN" in reason


def test_the_env_example_is_judged_only_for_names_the_app_reads() -> None:
    """A parameter staged ahead of its slice needs no example line yet; one the app reads does."""
    entries = [("ssm-param", "TRELLO__TOKEN", "set"), ("ssm-param", "SLACK__BOT_TOKEN", "set"), (EXAMPLE, "OTHER", "set")]

    rows = {
        name: verdict
        for name, _, verdict in coverage_rows(DOC14, {"TRELLO__TOKEN", "SLACK__BOT_TOKEN"}, entries, read={"SLACK__BOT_TOKEN"})
    }

    assert "app/.env.example" not in rows["TRELLO__TOKEN"].reason
    assert "app/.env.example" in rows["SLACK__BOT_TOKEN"].reason
