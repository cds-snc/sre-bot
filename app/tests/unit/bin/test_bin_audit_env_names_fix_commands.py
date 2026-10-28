"""The audit's fix commands: one reviewed shell line per row that needs an action, never for production.

Rows are classified as in the audit itself, then turned into commands. An env-file line is
removed or renamed with one sed per file; a GitHub secret or variable is deleted through gh,
under the user's own login; a retired Codespaces secret whose value moves to a new name is
copied from the running Codespace before the old one is deleted, because GitHub never returns a
secret's value. Production SSM rows and organization-level names produce no command.
"""

import io
from pathlib import Path

import pytest

from bin import audit_env_names
from bin.audit_env_names import GH, Context, Verdict, classify, fix_commands

pytestmark = pytest.mark.unit

REPO = "cds-snc/sre-bot"
CTX = Context(current={"NOTIFY__SRE_CLIENT_SECRET", "SLACK__BOT_TOKEN"})


def _rows(source: str, *names: str, state: str = "present") -> list[tuple[str, str, Verdict]]:
    return [(name, state, classify(source, name, state, CTX)) for name in names]


def test_env_file_lines_are_removed_with_one_sed_per_file() -> None:
    rows = _rows("file app/.env.example", "INCIDENT_CHANNEL", "GROUP_DOMAIN", state="commented")

    assert fix_commands({"file app/.env.example": rows}, REPO) == [
        "# file app/.env.example",
        "sed -i -E '/^[[:space:]]*#?[[:space:]]*(export[[:space:]]+)?(GROUP_DOMAIN|INCIDENT_CHANNEL)=/d' app/.env.example",
    ]


def test_a_secret_moving_to_a_new_name_is_copied_before_the_old_one_is_deleted() -> None:
    source = f"codespaces repo {REPO}"
    rows = _rows(source, "NOTIFY_SRE_CLIENT_SECRET")

    assert fix_commands({source: rows}, REPO) == [
        f"# {source}",
        "printenv NOTIFY_SRE_CLIENT_SECRET >/dev/null"
        f" && printenv NOTIFY_SRE_CLIENT_SECRET | {GH} secret set NOTIFY__SRE_CLIENT_SECRET --app codespaces --repo {REPO}"
        f" && {GH} secret delete NOTIFY_SRE_CLIENT_SECRET --app codespaces --repo {REPO}"
        ' || echo "kept NOTIFY_SRE_CLIENT_SECRET: set NOTIFY__SRE_CLIENT_SECRET by hand, then delete it"',
    ]


def test_a_secret_whose_new_name_is_already_set_is_only_deleted() -> None:
    """An existing new secret is never overwritten with the old value."""
    source = f"codespaces repo {REPO}"
    rows = [*_rows(source, "NOTIFY_SRE_CLIENT_SECRET"), ("NOTIFY__SRE_CLIENT_SECRET", "present", Verdict("none", "read"))]

    assert fix_commands({source: rows}, REPO) == [
        f"# {source}",
        f"{GH} secret delete NOTIFY_SRE_CLIENT_SECRET --app codespaces --repo {REPO}",
    ]


def test_a_codespaces_name_whose_value_moved_to_the_files_is_deleted() -> None:
    source = f"codespaces repo {REPO}"
    rows = _rows(source, "INCIDENT_CHANNEL", "GROUP_DOMAIN")

    assert fix_commands({source: rows}, REPO) == [
        f"# {source}",
        f"{GH} secret delete GROUP_DOMAIN --app codespaces --repo {REPO}",
        f"{GH} secret delete INCIDENT_CHANNEL --app codespaces --repo {REPO}",
    ]


@pytest.mark.parametrize(
    ("source", "command"),
    [
        (f"actions secret repo {REPO}", f"{GH} secret delete OLD_NAME --repo {REPO}"),
        (f"actions variable repo {REPO}", f"{GH} variable delete OLD_NAME --repo {REPO}"),
        (f"dependabot secret repo {REPO}", f"{GH} secret delete OLD_NAME --app dependabot --repo {REPO}"),
        ("actions secret environment production", f"{GH} secret delete OLD_NAME --env production --repo {REPO}"),
        ("actions variable environment production", f"{GH} variable delete OLD_NAME --env production --repo {REPO}"),
        (f"codespaces user (reaches {REPO})", f"{GH} secret delete OLD_NAME --user"),
    ],
)
def test_each_github_source_gets_its_delete_command(source: str, command: str) -> None:
    rows = [("OLD_NAME", "present", Verdict("delete", "no workflow under .github/ references it"))]

    assert fix_commands({source: rows}, REPO) == [f"# {source}", command]


@pytest.mark.parametrize(
    "source",
    ["ssm-blob sre-bot-config", "ssm /sre-bot/<NAME> secret parameters", "codespaces org cds-snc (may not reach this repo)"],
)
def test_production_and_organization_rows_get_no_command(source: str) -> None:
    rows = [("OLD_NAME", "present", Verdict("delete", "x")), ("OTHER", "missing", Verdict("check", "y"))]

    assert fix_commands({source: rows}, REPO) == []


def test_rows_needing_no_action_or_a_check_get_no_command() -> None:
    source = f"actions secret repo {REPO}"
    rows = [("KEPT", "present", Verdict("none", "used")), ("ODD", "present", Verdict("check", "investigate"))]

    assert fix_commands({source: rows}, REPO) == []


def test_an_env_file_line_with_a_new_name_is_renamed_in_place() -> None:
    rows = [("OLD_NAME", "set", Verdict("rename", "set NEW__NAME to the same value, then delete OLD_NAME", new="NEW__NAME"))]

    assert fix_commands({"file app/.env": rows}, REPO) == [
        "# file app/.env",
        "sed -i -E 's/^([[:space:]]*#?[[:space:]]*(export[[:space:]]+)?)OLD_NAME=/\\1NEW__NAME=/' app/.env",
    ]


def test_an_env_file_line_whose_value_moves_to_a_secret_name_is_renamed_not_deleted() -> None:
    rows = _rows("file app/.env", "NOTIFY_SRE_CLIENT_SECRET", state="set")

    assert fix_commands({"file app/.env": rows}, REPO) == [
        "# file app/.env",
        "sed -i -E 's/^([[:space:]]*#?[[:space:]]*(export[[:space:]]+)?)NOTIFY_SRE_CLIENT_SECRET=/\\1NOTIFY__SRE_CLIENT_SECRET=/' app/.env",
    ]


def test_the_plan_file_holds_exactly_the_printed_commands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The audit only writes the plan; applying it is a separate, confirmed step of bin/env-checks.zsh."""
    plan = tmp_path / "x.plan.sh"
    monkeypatch.setenv("REPO_SLUG", REPO)
    monkeypatch.setenv("PLAN_FILE", str(plan))
    monkeypatch.setattr(audit_env_names, "env_names", lambda root: set())
    monkeypatch.setattr(audit_env_names, "baseline_names", lambda sha, tree: set())
    monkeypatch.setattr(audit_env_names, "workflow_references", lambda: {})
    monkeypatch.setattr(audit_env_names, "setup_references", lambda: {})
    monkeypatch.setattr(audit_env_names, "doc14_destinations", lambda: {})
    monkeypatch.setattr("sys.stdin", io.StringIO(f"actions secret repo {REPO}\tOLD_NAME\tpresent\n"))

    audit_env_names.main(["abc123"])

    assert plan.read_text() == f"# actions secret repo {REPO}\n{GH} secret delete OLD_NAME --repo {REPO}\n"
    assert "nothing has run" in capsys.readouterr().out
