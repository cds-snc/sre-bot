"""Unit tests for the env-name coverage audit.

``coverage_rows`` is called with hand-built env-only names (name to the developer source their metadata
names), terraform names and collected TSV entries, so each gap is pinned without importing the settings
classes or reading ``terraform/ssm.tf``, GitHub or SSM. ``terraform_parameters`` reads a small ``ssm.tf``
written to a temporary directory; the development-unconfigured rule reads the checked-in configuration.
"""

from pathlib import Path

import pytest

from bin.audit_env_coverage import coverage_rows, terraform_parameters

pytestmark = pytest.mark.unit

ENV_ONLY = {"SLACK__BOT_TOKEN": "codespaces", "TRELLO__ATIP_BOARD": "codespaces", "GEO__LOCAL_ONLY": "local"}
CODESPACES = "codespaces repo cds-snc/sre-bot"


def _rows(terraform: set[str], entries: list[tuple[str, str, str]]) -> dict[str, tuple[str, str]]:
    return {name: (verdict.action, verdict.reason) for name, _, verdict in coverage_rows(ENV_ONLY, terraform, entries)}


def test_a_parameter_terraform_creates_sets_and_codespaces_provides_needs_nothing() -> None:
    entries = [("ssm-param", "SLACK__BOT_TOKEN", "set"), (CODESPACES, "SLACK__BOT_TOKEN", "present")]

    assert _rows({"SLACK__BOT_TOKEN"}, entries)["SLACK__BOT_TOKEN"][0] == "none"


def test_a_terraform_parameter_no_env_only_field_reads_is_a_check() -> None:
    """A name in ssm.tf that no settings field declares env-only has no reader: its parameter is unused."""
    action, reason = _rows({"GHOST__KEY"}, [("ssm-param", "GHOST__KEY", "set")])["GHOST__KEY"]

    assert action == "check"
    assert "no env-only settings field reads it" in reason


def test_an_env_only_name_without_a_parameter_is_development_only() -> None:
    """A name terraform does not create is supplied only to developers; nothing judges production for it."""
    rows = {name: (where, verdict.action) for name, where, verdict in coverage_rows(ENV_ONLY, set(), [])}

    assert rows["GEO__LOCAL_ONLY"] == ("no terraform (development only)", "none")


@pytest.mark.parametrize("state", ["placeholder", "empty"])
def test_a_parameter_not_set_is_a_check(state: str) -> None:
    entries = [("ssm-param", "TRELLO__ATIP_BOARD", state)]

    action, reason = _rows({"TRELLO__ATIP_BOARD"}, entries)["TRELLO__ATIP_BOARD"]
    assert action == "check"
    assert f"parameter is {state}: set it with put-parameter" in reason


def test_a_parameter_terraform_has_not_created_yet_waits_for_the_apply() -> None:
    entries = [("ssm-param", "SLACK__BOT_TOKEN", "set")]

    action, reason = _rows({"SLACK__BOT_TOKEN", "TRELLO__ATIP_BOARD"}, entries)["TRELLO__ATIP_BOARD"]
    assert action == "check"
    assert "tf_apply pending" in reason


def test_ssm_states_are_not_judged_when_the_ssm_section_was_skipped() -> None:
    """Without any SSM rows (no AWS credentials) the parameter state is unknown, not missing."""
    entries = [(CODESPACES, "TRELLO__ATIP_BOARD", "present")]

    assert _rows({"TRELLO__ATIP_BOARD"}, entries)["TRELLO__ATIP_BOARD"][0] == "none"


def test_a_codespaces_sourced_name_missing_from_codespaces_is_a_check() -> None:
    """The metadata says a developer gets the value from a Codespaces secret, and none provides it."""
    entries = [(CODESPACES, "SLACK__BOT_TOKEN", "present")]

    action, reason = _rows(set(), entries)["TRELLO__ATIP_BOARD"]
    assert action == "check"
    assert "no Codespaces secret provides it" in reason


def test_a_local_sourced_name_is_not_expected_in_codespaces() -> None:
    """A name whose metadata says the developer sets it in app/.env (Slack's signing secret, a user token) needs no Codespaces secret."""
    entries = [(CODESPACES, "SLACK__BOT_TOKEN", "present")]

    action, _ = _rows(set(), entries)["GEO__LOCAL_ONLY"]

    assert action == "none"


def test_codespaces_are_not_judged_when_none_were_listed() -> None:
    """Without any Codespaces rows (no gh auth) a missing secret is unknown, not absent."""
    assert _rows(set(), [])["TRELLO__ATIP_BOARD"][0] == "none"


def test_terraform_parameters_reads_the_secret_names_set(tmp_path: Path) -> None:
    """The names come from the sre_bot_secret_names set, not from other quoted strings in the file."""
    tf = tmp_path / "ssm.tf"
    tf.write_text(
        'resource "aws_ssm_parameter" "x" {\n  name = "OTHER_NAME"\n}\n'
        'locals {\n  sre_bot_secret_names = toset([\n    "SLACK__BOT_TOKEN",\n    "TRELLO__ATIP_BOARD",\n  ])\n}\n'
    )

    assert terraform_parameters(tf) == {"SLACK__BOT_TOKEN", "TRELLO__ATIP_BOARD"}


_NOTIFY = {"NOTIFY__SRE_USER_NAME": "codespaces"}


def test_a_credential_of_a_vendor_local_leaves_unconfigured_is_not_wanted_in_codespaces() -> None:
    """Notify has a tenant entry in production.toml and none in local.toml: its credential alone fails local boot.

    Reads the checked-in configuration files: the rule follows where each environment configures the vendor.
    """
    entries = [("ssm-param", "NOTIFY__SRE_USER_NAME", "set"), (CODESPACES, "OTHER", "present")]

    rows = {name: verdict for name, _, verdict in coverage_rows(_NOTIFY, {"NOTIFY__SRE_USER_NAME"}, entries)}

    assert rows["NOTIFY__SRE_USER_NAME"].action == "none"


def test_a_credential_of_a_vendor_local_leaves_unconfigured_in_codespaces_is_a_check() -> None:
    entries = [("ssm-param", "NOTIFY__SRE_USER_NAME", "set"), (CODESPACES, "NOTIFY__SRE_USER_NAME", "present")]

    rows = {name: verdict for name, _, verdict in coverage_rows(_NOTIFY, {"NOTIFY__SRE_USER_NAME"}, entries)}

    assert rows["NOTIFY__SRE_USER_NAME"].action == "check"
    assert "local.toml has no [notify.tenant]" in rows["NOTIFY__SRE_USER_NAME"].reason
