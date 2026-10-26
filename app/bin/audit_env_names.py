"""Developer helper: say what to do with each environment name set outside the code.

``bin/env-checks.zsh`` (repository root) collects names, never values, and pipes TSV lines to this
module: ``source<TAB>name<TAB>state``, where state is set, empty, commented, present or placeholder.
Each name gets one action:

    none    nothing to do
    delete  remove the line or the secret
    rename  set the new name to the same value, then delete the old one
    check   something disagrees (a destination, a parameter, a workflow reference): investigate

Durable part: env files, Codespaces and GitHub Actions names are judged against what the app reads
(derived the way CI derives it: ``check_settings_key_ownership`` scans the settings classes with ``ast``)
and what the workflows under ``.github/`` reference.

Migration part (TASK-111.15.2 deletes it with the SSM blobs, along with HINTS and SUPERSEDED): retired names are those the baseline tree
(the parent of TASK-111.1; the wrapper extracts it with ``git archive``) read and the app no longer
reads; production blob names are judged against doc-14 and ``config/{base,production}.toml``.

Usage (from app/): ``uv run python -m bin.audit_env_names [--all] BASELINE_SHA [BASELINE_APP_DIR] < names.tsv``;
the baseline directory is needed only when the cached names are for another commit.
"""

import re
import sys
import tomllib
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bin import check_settings_key_ownership as checker

APP_ROOT = checker.APP_ROOT
REPO_ROOT = APP_ROOT.parent
CACHE = REPO_ROOT / "tmp/env-checks/.baseline-names.txt"
CONFIG_DIR = APP_ROOT / "config"
WORKFLOW_DIR = REPO_ROOT / ".github"
ACTIONS_LISTED = "actions-listed"  # marker source: the repository's Actions secrets could be listed

# Read by the platform, an SDK or uvicorn, never by a settings class.
RUNTIME = frozenset(
    {
        "ENVIRONMENT",
        "GIT_SHA",
        "FORWARDED_ALLOW_IPS",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "AWS_CONFIG_FILE",
        "AWS_SHARED_CREDENTIALS_FILE",
    }
)
RUNTIME_PREFIXES = ("AWS_ENDPOINT_URL", "UVICORN_", "OTEL_")

# Retired switches whose replacement is a configuration key, not a renamed variable.
HINTS = {
    "ACCESS_SYNC_ENABLED": '[plugins.platform_access] "access.sync" (locally PLUGINS__PLATFORM_ACCESS)',
    "ACCESS_REQUESTS_ENABLED": '[plugins.platform_access] "access.request" (locally PLUGINS__PLATFORM_ACCESS)',
    "ACCESS_CATALOG_ENABLED": '[plugins.platform_access] "access.catalog" (locally PLUGINS__PLATFORM_ACCESS)',
    "SLACK_ENABLED": "[slack_transport] enabled",
    "SLACK_SOCKET_MODE": "[slack_transport] socket_mode",
    "SLACK_TEAM_ID": "[slack.tenant] team_id",
    "ISSUER_CONFIG": "[[security.issuers]]",
}

# Names whose values moved before the configuration migration (#975 folded the Google IDs into the one
# GOOGLE_RESOURCES JSON secret; #976 removed the frontend). Their old secrets are leftovers.
SUPERSEDED = {
    "SRE_DRIVE_ID": "GOOGLE_RESOURCES inc.d",
    "SRE_INCIDENT_FOLDER": "GOOGLE_RESOURCES inc.f",
    "INCIDENT_TEMPLATE": "GOOGLE_RESOURCES inc.t",
    "INCIDENT_LIST": "GOOGLE_RESOURCES inc.l",
    "INTERNAL_TALENT_FOLDER": "GOOGLE_RESOURCES tal.i",
    "SCORING_GUIDE_TEMPLATE": "GOOGLE_RESOURCES tal.s",
    "TEMPLATES_FOLDER": "GOOGLE_RESOURCES tal.t",
    "CORE_VALUES_INTERVIEW_NOTES_TEMPLATE": "GOOGLE_RESOURCES tal.c",
    "TECHNICAL_INTERVIEW_NOTES_TEMPLATE": "GOOGLE_RESOURCES tal.tech",
    "INTAKE_FORM_TEMPLATE": "GOOGLE_RESOURCES tal.int",
    "PHONE_SCREEN_TEMPLATE": "GOOGLE_RESOURCES tal.ph",
    "RECRUITMENT_FEEDBACK_TEMPLATE": "GOOGLE_RESOURCES tal.rec",
    "PANELIST_GUIDEBOOK_TEMPLATE": "GOOGLE_RESOURCES tal.pan",
    "SPENDING_SHEET_ID": "GOOGLE_RESOURCES aws.s",
    "GOOGLE_SRE_CALENDAR_ID": "GOOGLE_RESOURCES cal.sre",
    "FOLDER_REPORTS_GOOGLE_GROUPS": "GOOGLE_RESOURCES rep.g (itself unread)",
    "FRONTEND_URL": "nothing (the frontend was removed in #976)",
}

FILE_DESTINATION = re.compile(r"(?:production\.toml |file )\[([a-z0-9_.]+)\] ?([a-z0-9_]*)")
SECRET_DESTINATION = re.compile(r"secret ([A-Z0-9_]+)")
WORKFLOW_REFERENCE = re.compile(r"\b(?:secrets|vars)\.([A-Za-z0-9_]+)")
# Developer setup that reads the environment: devcontainer files, Makefiles and shell scripts.
SETUP_FILES = (".devcontainer/*", "Makefile", "app/Makefile", "app/bin/*.sh", "bin/*.sh")
SHELL_REFERENCE = re.compile(r"\$\{?([A-Z][A-Z0-9_]+)")
BLOB_END = "the line goes when the blob is deleted"

type Destinations = dict[str, tuple[str, str]]


@dataclass(frozen=True)
class Verdict:
    action: str
    reason: str


@dataclass(frozen=True)
class Context:
    current: set[str]
    retired: set[str] = field(default_factory=set)
    doc14: Destinations = field(default_factory=dict)
    parameter_states: dict[str, str] = field(default_factory=dict)
    workflow_refs: dict[str, list[str]] = field(default_factory=dict)
    setup_refs: dict[str, list[str]] = field(default_factory=dict)


def env_names(root: Path) -> set[str]:
    """Every environment name a settings class under ``root`` reads, upper-cased."""
    claims, _ = checker.collect_env_claims(root)
    return {claim.key.upper() for claim in claims}


def baseline_names(sha: str, tree: Path | None) -> set[str]:
    """Names the baseline tree read, cached by commit; ``tree`` is required on a cache miss."""
    if CACHE.exists() and CACHE.read_text().startswith(sha):
        return set(CACHE.read_text().split()[1:])
    if tree is None:
        raise SystemExit(f"no cached names for {sha}: pass the extracted baseline app directory")
    names = env_names(tree)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(" ".join([sha, *sorted(names)]))
    return names


def workflow_references(root: Path = WORKFLOW_DIR) -> dict[str, list[str]]:
    """Name -> workflow files that reference the NAME of a GitHub secret or variable."""
    refs: defaultdict[str, set[str]] = defaultdict(set)
    for path in sorted(root.rglob("*.y*ml")):
        for name in WORKFLOW_REFERENCE.findall(path.read_text()):
            refs[name].add(path.name)
    refs.pop("GITHUB_TOKEN", None)
    return {name: sorted(files) for name, files in refs.items()}


def setup_references(root: Path = REPO_ROOT) -> dict[str, list[str]]:
    """Name -> setup files that expand ``$NAME`` or ``${NAME}`` (shell locals included; harmless here)."""
    refs: defaultdict[str, set[str]] = defaultdict(set)
    for pattern in SETUP_FILES:
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                for name in SHELL_REFERENCE.findall(path.read_text(errors="ignore")):
                    refs[name].add(str(path.relative_to(root)))
    return {name: sorted(files) for name, files in refs.items()}


def doc14_destinations() -> Destinations:
    """Name -> (destination, subtask) from every doc-14 table that has a Destination column."""
    doc = next((REPO_ROOT / "backlog/docs").glob("doc-14 - *.md"))
    rows: Destinations = {}
    header: list[str] = []
    for line in doc.read_text().splitlines():
        if not line.startswith("|"):
            header = []
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not header:
            header = cells
            continue
        if set(cells[0]) <= {"-", " "} or "Destination" not in header:
            continue
        subtask = cells[header.index("Subtask")] if "Subtask" in header else ""
        rows[cells[0]] = (cells[header.index("Destination")], subtask)
    return rows


def config_table(environment: str, table: str) -> dict[str, Any]:
    """The merged ``[table]`` of base.toml and ``<environment>.toml``."""
    merged: dict[str, Any] = {}
    for name in ("base.toml", f"{environment}.toml"):
        path = CONFIG_DIR / name
        if not path.exists():
            continue
        data: Any = tomllib.loads(path.read_text())
        for part in table.split("."):
            data = data.get(part, {}) if isinstance(data, dict) else {}
        if isinstance(data, dict):
            merged.update(data)
    return merged


def replacement(name: str, current: Iterable[str]) -> str | None:
    """Guess the current name of a retired one: ``<TABLE>__<NAME>``, or its first '_' became '__'."""
    head, _, tail = name.partition("_")
    candidates = [c for c in current if c.endswith("__" + name) or (tail and c == f"{head}__{tail}")]
    return min(candidates, key=len) if candidates else None


def _is_runtime(name: str) -> bool:
    return name in RUNTIME or name.startswith(RUNTIME_PREFIXES)


def _developer(name: str, state: str, ctx: Context) -> Verdict:
    """An env-file line or a Codespaces secret: what a developer's process would read."""
    read = name in ctx.current or _is_runtime(name) or name in ctx.setup_refs
    if state == "commented":
        if read:
            return Verdict("none", "commented example of a name the app reads")
        now = HINTS.get(name) or replacement(name, ctx.current)
        return Verdict("delete", f"commented line of a name nothing reads{'; now ' + now if now else ''}")
    if name in ctx.current:
        return Verdict("none", "read by the app")
    if _is_runtime(name):
        return Verdict("none", "read by the platform, an SDK or uvicorn")
    if files := ctx.setup_refs.get(name):
        return Verdict("none", f"read by developer setup: {', '.join(files)}")
    if name in HINTS:
        return Verdict("delete", f"retired; set {HINTS[name]} instead")
    if name in SUPERSEDED:
        return Verdict("delete", f"superseded before the migration by {SUPERSEDED[name]}, which stays")
    if name in ctx.retired:
        if new := replacement(name, ctx.current):
            return Verdict("rename", f"set {new} to the same value, then delete {name}")
        return Verdict("delete", "retired by the configuration migration; the value lives in app/config/*.toml now")
    return Verdict("delete", "nothing in the repository reads it (confirm nobody uses it outside the repository)")


def _actions(source: str, name: str, ctx: Context) -> Verdict:
    """A GitHub Actions or Dependabot secret or variable: what the workflows read."""
    if files := ctx.workflow_refs.get(name):
        return Verdict("none", f"used by {', '.join(files)}")
    if " org" in source:
        return Verdict("none", "organization-level; other repositories may use it")
    return Verdict("delete", "no workflow under .github/ references it")


def _production_blob(name: str, ctx: Context) -> Verdict:
    """A line of the sre-bot-config blobs (migration part)."""
    if name in ctx.doc14:
        destination, _ = ctx.doc14[name]
        if destination.startswith("platform"):
            return Verdict("none", f"platform name the task definition also sets; {BLOB_END}")
        if name in ctx.current:
            return Verdict("none", f"still read from the blob; doc-14 moves it to {destination}")
        if destination.startswith("delete"):
            return Verdict("none", f"no reader; {BLOB_END}")
        if (match := FILE_DESTINATION.match(destination)) and (table := config_table("production", match[1])):
            if match[2] in table:
                return Verdict("none", f"migrated to [{match[1]}] {match[2]}; {BLOB_END}")
            if "structured" in destination:
                return Verdict("none", f"migrated to [{match[1]}] (restructured: {', '.join(sorted(table))}); {BLOB_END}")
            return Verdict("check", f"not read, and production [{match[1]}] has no {match[2]}: fix doc-14 or the config")
        if match := SECRET_DESTINATION.match(destination):
            status = ctx.parameter_states.get(match[1], "missing")
            if status == "set":
                return Verdict("none", f"migrated to secret {match[1]}; {BLOB_END}")
            return Verdict("check", f"migrated to secret {match[1]}, but /sre-bot/{match[1]} is {status}")
        return Verdict("check", f"not read, and doc-14's destination '{destination}' is not in production config")
    if name in ctx.current or _is_runtime(name):
        return Verdict("check", "read by the app but missing from doc-14: add its row")
    return Verdict("none", f"no reader; {BLOB_END}")


def classify(source: str, name: str, state: str, ctx: Context) -> Verdict:
    if source.startswith("ssm-blob"):
        return _production_blob(name, ctx)
    if source.startswith(("actions", "dependabot")):
        return _actions(source, name, ctx)
    return _developer(name, state, ctx)


def parameter_rows(ctx: Context) -> list[tuple[str, str, Verdict]]:
    """The /sre-bot/<NAME> parameters doc-14 names (migration part)."""
    wanted = sorted({m[1] for destination, _ in ctx.doc14.values() if (m := SECRET_DESTINATION.match(destination))})
    rows = []
    for name in wanted:
        state = ctx.parameter_states.get(name, "missing")
        if state == "set":
            why = "read by the app" if name in ctx.current else "set; the app reads it once its slice moves (doc-14)"
            rows.append((name, state, Verdict("none", why)))
        else:
            rows.append((name, state, Verdict("check", "set the value with put-parameter before its slice moves")))
    return rows


def unprovided_workflow_references(listed: set[str], ctx: Context) -> list[tuple[str, str, Verdict]]:
    """Names a workflow references that no listed secret or variable provides."""
    return [
        (
            name,
            "absent",
            Verdict("check", f"referenced by {', '.join(files)} but not listed (an org secret this repo cannot list?)"),
        )
        for name, files in sorted(ctx.workflow_refs.items())
        if name not in listed
    ]


LEGEND = """actions: none = nothing to do; delete = remove the line or secret; rename = set the new name to the same
value, then delete the old one; check = something disagrees, investigate. Production blob lines are never
edited by hand: the blobs are deleted as a whole (TASK-111.15), so their migrated or unread lines show none."""


def main(argv: list[str]) -> None:
    show_all = "--all" in argv
    args = [a for a in argv if a != "--all"]
    if not 1 <= len(args) <= 2:
        raise SystemExit("usage: python -m bin.audit_env_names [--all] BASELINE_SHA [BASELINE_APP_DIR] < names.tsv")
    current = env_names(APP_ROOT)
    entries = [line.rstrip("\n").split("\t") for line in sys.stdin if line.strip()]
    ctx = Context(
        current=current,
        retired=baseline_names(args[0], Path(args[1]) if len(args) == 2 else None) - current,
        doc14=doc14_destinations(),
        parameter_states={name: state for source, name, state in entries if source == "ssm-param"},
        workflow_refs=workflow_references(),
        setup_refs=setup_references(),
    )

    sections: defaultdict[str, list[tuple[str, str, Verdict]]] = defaultdict(list)
    for source, name, state in entries:
        if source not in {"ssm-param", ACTIONS_LISTED}:
            sections[source].append((name, state, classify(source, name, state, ctx)))
    if ctx.parameter_states:
        sections["ssm /sre-bot/<NAME> secret parameters"] = parameter_rows(ctx)
    if any(source == ACTIONS_LISTED for source, _, _ in entries):
        listed = {name for source, name, _ in entries if source.startswith(("actions", "dependabot"))}
        sections["github actions: workflow references with no secret or variable"] = unprovided_workflow_references(listed, ctx)

    print(LEGEND)
    totals: Counter[str] = Counter()
    for source, rows in sections.items():
        counts = Counter(verdict.action for _, _, verdict in rows)
        totals.update(counts)
        print(f"\n== {source} == " + " ".join(f"{action}={n}" for action, n in sorted(counts.items())))
        for name, state, verdict in sorted(rows, key=lambda row: (row[2].action == "none", row[2].action, row[0])):
            if show_all or verdict.action != "none":
                print(f"{verdict.action:<6} {name} [{state}]: {verdict.reason}")
    print("\ntotal: " + " ".join(f"{action}={n}" for action, n in sorted(totals.items())))
    if not show_all:
        print("rows with action none are hidden; rerun with --all to list them")


if __name__ == "__main__":
    main(sys.argv[1:])
