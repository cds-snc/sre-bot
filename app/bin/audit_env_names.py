"""Developer helper: say what to do with each environment name set outside the code.

``bin/env-checks.zsh`` (repository root) collects names, never values, and pipes TSV lines to this
module: ``source<TAB>name<TAB>state``, where state is set, empty, commented, present or placeholder.
Each name gets one action:

    none    nothing to do
    delete  remove the line or the secret (a value that moves to a new name is copied there first)
    check   something disagrees (a destination, a parameter, a workflow reference): investigate

A delete needs positive evidence of retirement: a ``RETIRED`` entry, which the task that retires a name
adds. Absence of a reference is not evidence (a workflow on another branch, a reusable workflow's
``secrets: inherit`` or a dynamic ``secrets[...]`` is invisible to the scan), so a name nothing in the
repository reads, or a repository Actions secret or variable no workflow on the default branch references, is
a check showing its last reference in git history. When ``.github`` passes secrets dynamically, the workflow
scan is blind and every repository Actions secret is none.

The audit stays pure; git history is looked up by the wrapper in two passes. ``--lookups`` prints
``kind<TAB>name`` for each check row that needs its last reference (kind ``workflow``: a
``secrets.NAME``/``vars.NAME`` in ``.github``; kind ``repo``: the name anywhere outside the planning docs),
then the wrapper runs ``git log`` for those names only and passes the ``name<TAB>reference`` file it wrote as
``LAST_REFS_FILE`` to the second, reporting pass.

Env files, Codespaces and GitHub Actions names are judged against what the app reads (derived the way CI
derives it: ``check_settings_key_ownership`` scans the settings classes with ``ast``) and what the
workflows under ``.github/`` reference.

Usage (from app/): ``uv run python -m bin.audit_env_names [--all | --lookups] < names.tsv``.
"""

import os
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from bin import check_settings_key_ownership as checker

APP_ROOT = checker.APP_ROOT
REPO_ROOT = APP_ROOT.parent
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

# Names no longer read, each with what replaced it: "secret <NAME>" (a Codespaces value is copied there
# first), a configuration key, or "nothing (...)". The task that retires a name adds it here: this is the
# only evidence that plans a delete. MAXMIND_KEY is never listed (the devcontainer's GeoIP updater needs it).
RETIRED = {
    "GCP_SRE_SERVICE_ACCOUNT_KEY_FILE": "nothing (fed terraform's destroyed gcp_sre_service_account_key parameter;"
    " the key is secret GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY)",
    "GOOGLE_PICKLE_STRING": "nothing (fed TF_VAR_google_oauth_pickle_string, which no terraform variable read)",
}

PARAMETER_DESTINATION = re.compile(r"secret ([A-Z0-9_]+)")
WORKFLOW_REFERENCE = re.compile(r"\b(?:secrets|vars)\.([A-Za-z0-9_]+)")
# Secrets passed without naming them: every repository secret may be read.
DYNAMIC_SECRETS = re.compile(r"secrets:\s*inherit\b|\bsecrets\[|\b(?:toJSON|fromJSON)\(\s*secrets\b")
# Developer setup that reads the environment: devcontainer files, Makefiles and shell scripts.
SETUP_FILES = (".devcontainer/*", "Makefile", "app/Makefile", "app/bin/*.sh", "bin/*.sh")
SHELL_REFERENCE = re.compile(r"\$\{?([A-Z][A-Z0-9_]+)")


@dataclass(frozen=True)
class Verdict:
    action: str
    reason: str
    new: str | None = None  # the name the value moves to, when it still has to be copied
    lookup: str | None = None  # a check whose last git reference the wrapper looks up: "workflow" or "repo"


@dataclass(frozen=True)
class Context:
    current: set[str]
    retired: Mapping[str, str] = field(default_factory=dict)  # RETIRED, injected so tests hand-build it
    workflow_refs: dict[str, list[str]] = field(default_factory=dict)
    setup_refs: dict[str, list[str]] = field(default_factory=dict)
    last_refs: dict[str, str] = field(default_factory=dict)  # name -> its last reference in git history
    workflow_scan_blind: bool = False  # .github passes secrets dynamically: any repository secret may be read


def env_names(root: Path) -> set[str]:
    """Every environment name a settings class under ``root`` reads, upper-cased."""
    claims, _ = checker.collect_env_claims(root)
    return {claim.key.upper() for claim in claims}


def workflow_references(root: Path = WORKFLOW_DIR) -> dict[str, list[str]]:
    """Name -> workflow files that reference the NAME of a GitHub secret or variable."""
    refs: defaultdict[str, set[str]] = defaultdict(set)
    for path in sorted(root.rglob("*.y*ml")):
        for name in WORKFLOW_REFERENCE.findall(path.read_text()):
            refs[name].add(path.name)
    refs.pop("GITHUB_TOKEN", None)
    return {name: sorted(files) for name, files in refs.items()}


def pass_through_workflow_files(root: Path = WORKFLOW_DIR) -> list[str]:
    """Workflow files under ``root`` that pass secrets without naming them (``secrets: inherit``, ``secrets[...]``)."""
    return sorted(str(path.relative_to(root)) for path in root.rglob("*.y*ml") if DYNAMIC_SECRETS.search(path.read_text()))


def setup_references(root: Path = REPO_ROOT) -> dict[str, list[str]]:
    """Name -> setup files that expand ``$NAME`` or ``${NAME}`` (shell locals included; harmless here)."""
    refs: defaultdict[str, set[str]] = defaultdict(set)
    for pattern in SETUP_FILES:
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                for name in SHELL_REFERENCE.findall(path.read_text(errors="ignore")):
                    refs[name].add(str(path.relative_to(root)))
    return {name: sorted(files) for name, files in refs.items()}


def _is_runtime(name: str) -> bool:
    return name in RUNTIME or name.startswith(RUNTIME_PREFIXES)


def _unevidenced(what: str, name: str, kind: str, ctx: Context) -> Verdict:
    """A check for a name with no reader and no evidence of retirement, showing its last git reference."""
    last = ctx.last_refs.get(name, "not looked up")
    return Verdict("check", f"{what}, and nothing records its retirement; last reference: {last}", lookup=kind)


def _developer(name: str, state: str, ctx: Context) -> Verdict:
    """An env-file line or a Codespaces secret: what a developer's process would read."""
    read = name in ctx.current or _is_runtime(name) or name in ctx.setup_refs
    if state == "commented":
        if read:
            return Verdict("none", "commented example of a name the app reads")
        if name not in ctx.retired:
            return _unevidenced("commented line of a name nothing reads", name, "repo", ctx)
        return Verdict("delete", f"commented line of a retired name; now {ctx.retired[name]}")
    if name in ctx.current:
        return Verdict("none", "read by the app")
    if _is_runtime(name):
        return Verdict("none", "read by the platform, an SDK or uvicorn")
    if files := ctx.setup_refs.get(name):
        return Verdict("none", f"read by developer setup: {', '.join(files)}")
    if now := ctx.retired.get(name):
        if now.startswith("nothing"):
            return Verdict("delete", f"retired; {now}")
        secret = PARAMETER_DESTINATION.match(now)
        return Verdict("delete", f"retired; set {now} instead", new=secret[1] if secret else None)
    return _unevidenced("nothing in the repository reads it", name, "repo", ctx)


def _actions(source: str, name: str, ctx: Context) -> Verdict:
    """A GitHub Actions or Dependabot secret or variable: what the workflows read."""
    if files := ctx.workflow_refs.get(name):
        return Verdict("none", f"used by {', '.join(files)}")
    if " org" in source:
        return Verdict("none", "organization-level; other repositories may use it")
    if ctx.workflow_scan_blind and " secret " in source:
        return Verdict("none", "the scan is blind: a workflow passes secrets without naming them")
    if name in ctx.retired:
        return _developer(name, "present", ctx)
    return _unevidenced("no workflow under .github/ on the default branch references it", name, "workflow", ctx)


def classify(source: str, name: str, state: str, ctx: Context) -> Verdict:
    if source.startswith(("actions", "dependabot")):
        return _actions(source, name, ctx)
    return _developer(name, state, ctx)


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


GH = "env -u GITHUB_TOKEN -u GH_TOKEN gh"  # the user's own login: the Codespace token cannot write secrets
ENV_PREFIX = "[[:space:]]*#?[[:space:]]*(export[[:space:]]+)?"  # an env-file line, commented or exported


def _github_target(source: str, repo: str) -> str | None:
    """The gh flags that address a GitHub secret source; None for organization and SSM sources."""
    words = source.split()
    if source.startswith("codespaces repo"):
        return f"secret {{verb}} {{name}} --app codespaces --repo {repo}"
    if source.startswith("codespaces user"):
        return "secret {verb} {name} --user"
    if source.startswith(("actions secret repo", "actions variable repo", "dependabot secret repo")):
        kind = "variable" if words[1] == "variable" else "secret"
        app = " --app dependabot" if words[0] == "dependabot" else ""
        return f"{kind} {{verb}} {{name}}{app} --repo {repo}"
    if source.startswith(("actions secret environment", "actions variable environment")):
        return f"{words[1]} {{verb}} {{name}} --env {words[3]} --repo {repo}"
    return None


def fix_commands(sections: dict[str, list[tuple[str, str, Verdict]]], repo: str) -> list[str]:
    """Shell lines that apply each delete row; SSM and organization rows get none."""
    lines: list[str] = []
    for source, rows in sections.items():
        acting = sorted(((name, verdict) for name, _, verdict in rows if verdict.action == "delete"), key=lambda row: row[0])
        commands: list[str] = []
        if source.startswith("file "):
            path = source.removeprefix("file ")
            renamed = [(name, verdict.new) for name, verdict in acting if verdict.new]
            dropped = [name for name, verdict in acting if not verdict.new]
            commands += [f"sed -i -E 's/^({ENV_PREFIX}){old}=/\\1{new}=/' {path}" for old, new in renamed]
            if dropped:
                commands.append(f"sed -i -E '/^{ENV_PREFIX}({'|'.join(dropped)})=/d' {path}")
        elif (target := _github_target(source, repo)) is not None:
            present = {name for name, _, _ in rows}
            for name, verdict in acting:
                delete = f"{GH} {target.format(verb='delete', name=name)}"
                if verdict.new and verdict.new not in present and source.startswith("codespaces"):
                    copy = f"printenv {name} | {GH} {target.format(verb='set', name=verdict.new)}"
                    kept = f'echo "kept {name}: set {verdict.new} by hand, then delete it"'
                    commands.append(f"printenv {name} >/dev/null && {copy} && {delete} || {kept}")
                else:
                    commands.append(delete)
        if commands:
            lines += [f"# {source}", *commands]
    return lines


LEGEND = """actions: none = nothing to do; delete = remove the line or secret (a value that moves to a new name is
copied there first); check = something disagrees, investigate."""


def read_last_refs(path: str | None) -> dict[str, str]:
    """The wrapper's ``name<TAB>reference`` lines; empty when it looked nothing up."""
    if not path or not Path(path).exists():
        return {}
    lines = (line.partition("\t") for line in Path(path).read_text().splitlines() if "\t" in line)
    return {name: ref for name, _, ref in lines}


def main(argv: list[str]) -> None:
    show_all = "--all" in argv
    lookups = "--lookups" in argv
    args = [a for a in argv if a not in {"--all", "--lookups"}]
    if args:
        raise SystemExit("usage: python -m bin.audit_env_names [--all | --lookups] < names.tsv")
    pass_through = pass_through_workflow_files()
    entries = [line.rstrip("\n").split("\t") for line in sys.stdin if line.strip()]
    ctx = Context(
        current=env_names(APP_ROOT),
        retired=RETIRED,
        workflow_refs=workflow_references(),
        setup_refs=setup_references(),
        last_refs=read_last_refs(os.environ.get("LAST_REFS_FILE")),
        workflow_scan_blind=bool(pass_through),
    )

    sections: defaultdict[str, list[tuple[str, str, Verdict]]] = defaultdict(list)
    for source, name, state in entries:
        if source not in {"ssm-param", ACTIONS_LISTED}:
            sections[source].append((name, state, classify(source, name, state, ctx)))
    if any(source == ACTIONS_LISTED for source, _, _ in entries):
        listed = {name for source, name, _ in entries if source.startswith(("actions", "dependabot"))}
        sections["github actions: workflow references with no secret or variable"] = unprovided_workflow_references(listed, ctx)

    if lookups:
        wanted = {(verdict.lookup, name) for rows in sections.values() for name, _, verdict in rows if verdict.lookup}
        print("".join(f"{kind}\t{name}\n" for kind, name in sorted(wanted)), end="")
        return

    print(LEGEND)
    if pass_through:
        print(f"workflow scan blind for repository secrets: {', '.join(pass_through)} pass values through without naming them")
    totals: Counter[str] = Counter()
    for source, rows in sections.items():
        counts = Counter(verdict.action for _, _, verdict in rows)
        totals.update(counts)
        print(f"\n== {source} == " + " ".join(f"{action}={n}" for action, n in sorted(counts.items())))
        for name, state, verdict in sorted(rows, key=lambda row: (row[2].action == "none", row[2].action, row[0])):
            if show_all or verdict.action != "none":
                print(f"{verdict.action:<6} {name} [{state}]: {verdict.reason}")
    print("\ntotal: " + " ".join(f"{action}={n}" for action, n in sorted(totals.items())))
    repo = os.environ.get("REPO_SLUG")
    commands = fix_commands(sections, repo) if repo else []
    if commands:
        print("\n== plan: commands for the delete rows (nothing has run) ==")
        print("# A secret whose value moves is copied from this Codespace first; GitHub never returns a value.")
        print("\n".join(commands))
    if plan := os.environ.get("PLAN_FILE"):
        Path(plan).write_text("".join(f"{line}\n" for line in commands))
    if not show_all:
        print("rows with action none are hidden; rerun with --all to list them")


if __name__ == "__main__":
    main(sys.argv[1:])
