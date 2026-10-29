"""The env-name audit's evidence rule: a check names its last git reference, a blind scan keeps secrets.

``classify`` is called with a hand-built ``Context`` holding the wrapper's last references; the dynamic
reference scan and the two-pass ``main`` read temporary workflow and reference files, so no git command,
GitHub call or real workflow is involved.
"""

import io
from pathlib import Path

import pytest

from bin import audit_env_names
from bin.audit_env_names import Context, classify, pass_through_workflow_files, read_last_refs

pytestmark = pytest.mark.unit

REPO = "cds-snc/sre-bot"
SECRET_SOURCE = f"actions secret repo {REPO}"


def test_an_unreferenced_secret_is_a_check_showing_its_last_reference() -> None:
    ctx = Context(
        current=set(), last_refs={"OLD_WEBHOOK": "46ce4a17 2025-02-21 Update build_and_deploy.yml (unmerged branch only)"}
    )

    verdict = classify(SECRET_SOURCE, "OLD_WEBHOOK", "present", ctx)

    assert verdict.action == "check"
    assert verdict.lookup == "workflow"
    assert "46ce4a17 2025-02-21 Update build_and_deploy.yml (unmerged branch only)" in verdict.reason


def test_a_name_nothing_reads_is_a_repo_check_until_its_reference_is_looked_up() -> None:
    verdict = classify(f"codespaces repo {REPO}", "UNREAD_NAME", "present", Context(current=set()))

    assert (verdict.action, verdict.lookup) == ("check", "repo")
    assert "last reference: not looked up" in verdict.reason


@pytest.mark.parametrize(
    "line",
    [
        "    secrets: inherit",
        "      token: ${{ secrets[matrix.name] }}",
        "      all: ${{ toJSON(secrets) }}",
        "      parsed: ${{ fromJSON(secrets.BLOB) }}",
    ],
)
def test_a_dynamic_secret_reference_is_found(tmp_path: Path, line: str) -> None:
    (tmp_path / "workflows").mkdir()
    (tmp_path / "workflows" / "ci.yml").write_text(f"jobs:\n  a:\n{line}\n")

    assert pass_through_workflow_files(tmp_path) == ["workflows/ci.yml"]


def test_named_secret_references_are_not_dynamic(tmp_path: Path) -> None:
    (tmp_path / "ci.yaml").write_text("env:\n  TOKEN: ${{ secrets.NAMED }}\n  JSON: ${{ toJSON(github) }}\n")

    assert pass_through_workflow_files(tmp_path) == []


@pytest.mark.parametrize("name", ["UNUSED_SECRET", "SLACK_ENABLED"])
def test_a_blind_scan_turns_every_repo_secret_into_none(name: str) -> None:
    ctx = Context(current=set(), retired={"SLACK_ENABLED": "[slack_transport] enabled"}, workflow_scan_blind=True)

    verdict = classify(SECRET_SOURCE, name, "present", ctx)

    assert verdict.action == "none"
    assert "blind" in verdict.reason


def test_a_blind_scan_still_judges_variables() -> None:
    """Secrets are what a reusable workflow inherits; variables are always named in the workflow."""
    ctx = Context(current=set(), workflow_scan_blind=True)

    assert classify(f"actions variable repo {REPO}", "UNUSED_VARIABLE", "present", ctx).action == "check"


def test_last_refs_file_is_read_as_name_and_reference(tmp_path: Path) -> None:
    refs = tmp_path / "refs.tsv"
    refs.write_text("A\tabc1234 2025-01-01 subject\twith tab\nB\tno reference in git history\n")

    assert read_last_refs(str(refs)) == {"A": "abc1234 2025-01-01 subject\twith tab", "B": "no reference in git history"}
    assert read_last_refs(None) == {}
    assert read_last_refs(str(tmp_path / "missing")) == {}


@pytest.fixture
def _pure_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PLAN_FILE", raising=False)
    monkeypatch.delenv("REPO_SLUG", raising=False)
    monkeypatch.setattr(audit_env_names, "env_names", lambda root: {"READ__NAME"})
    monkeypatch.setattr(audit_env_names, "RETIRED", {"RETIRED_NAME": "nothing (no reader)"})
    monkeypatch.setattr(audit_env_names, "workflow_references", lambda: {})
    monkeypatch.setattr(audit_env_names, "setup_references", lambda: {})
    monkeypatch.setattr(audit_env_names, "pass_through_workflow_files", lambda: [])
    rows = [
        f"{SECRET_SOURCE}\tUNUSED_SECRET\tpresent",
        f"codespaces repo {REPO}\tUNREAD_NAME\tpresent",
        f"codespaces repo {REPO}\tRETIRED_NAME\tpresent",
        f"codespaces repo {REPO}\tREAD__NAME\tpresent",
    ]
    monkeypatch.setattr("sys.stdin", io.StringIO("".join(f"{row}\n" for row in rows)))


@pytest.mark.usefixtures("_pure_audit")
def test_the_lookup_pass_lists_only_the_unevidenced_checks(capsys: pytest.CaptureFixture[str]) -> None:
    audit_env_names.main(["--lookups"])

    assert capsys.readouterr().out == "repo\tUNREAD_NAME\nworkflow\tUNUSED_SECRET\n"


@pytest.mark.usefixtures("_pure_audit")
def test_the_report_pass_shows_the_looked_up_reference(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    refs = tmp_path / "refs.tsv"
    refs.write_text("UNUSED_SECRET\t26ecfff1 2024-06-20 Adding workflow\n")
    monkeypatch.setenv("LAST_REFS_FILE", str(refs))

    audit_env_names.main([])

    out = capsys.readouterr().out
    assert "check  UNUSED_SECRET [present]: no workflow under .github/ on the default branch references it" in out
    assert "last reference: 26ecfff1 2024-06-20 Adding workflow" in out
    assert "delete RETIRED_NAME" in out
