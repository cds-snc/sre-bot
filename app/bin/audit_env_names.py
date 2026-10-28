"""Developer helper: say what to do with each environment name set outside the code.

``bin/env-checks.zsh`` (repository root) collects names, never values, and pipes TSV lines to this
module: ``source<TAB>name<TAB>state``, where state is set, empty, commented, present or placeholder.
Each name gets one action:

    none    nothing to do
    delete  remove the line or the secret
    rename  set the new name to the same value, then delete the old one
    check   something disagrees (a destination, a parameter, a workflow reference): investigate

A delete needs positive evidence of retirement: a name the configuration migration retired, or a HINTS or
SUPERSEDED entry. Absence of a reference is not evidence (a workflow on another branch, a reusable workflow's
``secrets: inherit`` or a dynamic ``secrets[...]`` is invisible to the scan), so a name nothing in the
repository reads, or a repository Actions secret or variable no workflow on the default branch references, is
a check showing its last reference in git history. When ``.github`` passes secrets dynamically, the workflow
scan is blind and every repository Actions secret is none.

The audit stays pure; git history is looked up by the wrapper in two passes. ``--lookups`` prints
``kind<TAB>name`` for each check row that needs its last reference (kind ``workflow``: a
``secrets.NAME``/``vars.NAME`` in ``.github``; kind ``repo``: the name anywhere outside the planning docs),
then the wrapper runs ``git log`` for those names only and passes the ``name<TAB>reference`` file it wrote as
``LAST_REFS_FILE`` to the second, reporting pass.

Durable part: env files, Codespaces and GitHub Actions names are judged against what the app reads
(derived the way CI derives it: ``check_settings_key_ownership`` scans the settings classes with ``ast``)
and what the workflows under ``.github/`` reference.

Migration part (TASK-111.15.2 deletes it with the SSM blobs, along with HINTS and SUPERSEDED): retired names are those the baseline tree
(the parent of TASK-111.1; the wrapper extracts it with ``git archive``) read and the app no longer
reads; production blob names are judged against doc-14 and ``config/{base,production}.toml``.

Usage (from app/): ``uv run python -m bin.audit_env_names [--all | --lookups] BASELINE_SHA [BASELINE_APP_DIR] < names.tsv``;
the baseline directory is needed only when the cached names are for another commit.
"""

import os
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
    "DEFAULT_TIER2_LEASE_TTL_SECONDS": "[scheduler] default_tier2_lease_ttl_seconds",
    "SRE_BOT_EMAIL": "secret GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL",
    "GCP_SRE_SERVICE_ACCOUNT_KEY_FILE": "secret GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY",
    "GOOGLE_WORKSPACE_CUSTOMER_ID": "secret GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID",
    "GOOGLE_API_NUM_RETRIES": "[google_workspace] api_num_retries",
    "GOOGLE_API_TIMEOUT_SECONDS": "[google_workspace] api_timeout_seconds",
    "AWS_AUDIT_ACCOUNT_ROLE_ARN": "secret AWS__TENANT__AUDIT_ROLE_ARN",
    "AWS_ORG_ACCOUNT_ROLE_ARN": "secret AWS__TENANT__ORG_ROLE_ARN",
    "AWS_LOGGING_ACCOUNT_ROLE_ARN": "secret AWS__TENANT__LOGGING_ROLE_ARN",
    "AWS_SSO_INSTANCE_ID": "secret AWS__TENANT__INSTANCE_ID",
    "AWS_SSO_INSTANCE_ARN": "secret AWS__TENANT__INSTANCE_ARN",
    "AWS_SSO_SYSTEM_ADMIN_PERMISSIONS": "secret ACCESS_PERMISSION_SETS__SYSTEM_ADMIN_PERMISSIONS",
    "AWS_SSO_VIEW_ONLY_PERMISSIONS": "secret ACCESS_PERMISSION_SETS__VIEW_ONLY_PERMISSIONS",
    "AWS_RETRY_MAX_ATTEMPTS": "[aws] retry_max_attempts",
    "AWS_RETRY_MODE": "[aws] retry_mode",
    "AWS_CONNECT_TIMEOUT_SECONDS": "[aws] connect_timeout_seconds",
    "AWS_READ_TIMEOUT_SECONDS": "[aws] read_timeout_seconds",
    "AWS_TRANSIENT_RETRY_AFTER_SECONDS": "[aws] transient_retry_after_seconds",
    "AWS_NOT_FOUND_CODES": "[aws] not_found_codes",
    "AWS_UNAUTHORIZED_CODES": "[aws] unauthorized_codes",
    "AWS_TRANSIENT_CODES": "[aws] transient_codes",
    "OPENAI_API_KEY": "secret OPENAI__API_KEY",
    "OPENAI_BASE_URL": "[openai.tenant] base_url",
    "OPENAI_MODEL": "[openai.tenant] model",
    "OPENAI_MAX_OUTPUT_TOKENS": "[openai] max_output_tokens",
    "OPENAI_TEMPERATURE": "[openai] temperature",
    "OPENAI_TIMEOUT_SECONDS": "[openai] timeout_seconds",
    "NOTIFY_SRE_USER_NAME": "secret NOTIFY__SRE_USER_NAME",
    "NOTIFY_SRE_CLIENT_SECRET": "secret NOTIFY__SRE_CLIENT_SECRET",
    "NOTIFY_API_URL": "[notify.tenant] api_url",
    "TRELLO_APP_KEY": "secret TRELLO__TENANT__APP_KEY",
    "TRELLO_TOKEN": "secret TRELLO__TENANT__TOKEN",
    "TRELLO_ATIP_BOARD": "secret TRELLO__ATIP_BOARD",
    "OPSGENIE_INTEGRATIONS_KEY": "secret OPSGENIE__INTEGRATIONS_KEY",
    "MAXMIND_DB_PATH": "[maxmind.tenant] database_path",
    "DIRECTORY_REQUIRE_STARTUP_WARMUP": "[directory] require_startup_warmup",
    "DIRECTORY_PROVIDER": "nothing (deleted: the directory follows the IdP in the data, never a setting)",
    "DIRECTORY_CACHE_TTL_SECONDS": "nothing (deleted: no reader)",
    "DIRECTORY_STARTUP_WARMUP_TIMEOUT_SECONDS": "nothing (deleted: no reader)",
    "DRIVE_PROVIDER": "nothing (deleted: Google Drive is the only provider)",
    "SPREADSHEET_PROVIDER": "nothing (deleted: Google Sheets is the only provider)",
    "RETRY_ENABLED": "nothing (deleted: the retry store had no consumer)",
    "RETRY_BACKEND": "nothing (deleted: the retry store had no consumer)",
    "RETRY_DYNAMODB_TABLE_NAME": "nothing (deleted: the retry store had no consumer)",
    "RETRY_DYNAMODB_TTL_DAYS": "nothing (deleted: the retry store had no consumer)",
    "RETRY_MAX_ATTEMPTS": "nothing (deleted: the retry store had no consumer)",
    "RETRY_BASE_DELAY_SECONDS": "nothing (deleted: the retry store had no consumer)",
    "RETRY_MAX_DELAY_SECONDS": "nothing (deleted: the retry store had no consumer)",
    "RETRY_BATCH_SIZE": "nothing (deleted: the retry store had no consumer)",
    "RETRY_CLAIM_LEASE_SECONDS": "nothing (deleted: the retry store had no consumer)",
    "IDEMPOTENCY_TTL_SECONDS": "[coordination] record_ttl_seconds",
    "IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS": "[coordination] in_progress_ttl_seconds",
    "AUDIT_TABLE_NAME": "[audit] table_name",
    "INCIDENT_CHANNEL": "[incident] incident_channel",
    "SLACK_SECURITY_USER_GROUP_ID": "[incident] slack_security_user_group_id",
    "SLACK_NOTIFY_MGMT_USER_GROUP_ID": "[incident] slack_notify_mgmt_user_group_id",
    "SRE_OPS_CHANNEL_ID": "[sre_ops] sre_ops_channel_id",
    "AWS_ADMIN_GROUPS": "[cloud_operations] aws_admin_groups",
    "AWS_OPS_GROUP_NAME": "nothing (deleted: never set in production, the ops group assignment never ran)",
    "ATIP_ANNOUNCE_CHANNEL": "[atip] announce_channel_id",
    "GROUP_DOMAIN": "nothing (deleted: the groups slice had no reader)",
    "GROUP_PROVIDERS": "nothing (deleted: the groups slice had no reader)",
    "RECONCILIATION_ENABLED": "nothing (deleted: the groups slice had no reader)",
    "RECONCILIATION_BACKEND": "nothing (deleted: the groups slice had no reader)",
    "RECONCILIATION_MAX_ATTEMPTS": "nothing (deleted: the groups slice had no reader)",
    "RECONCILIATION_BASE_DELAY_SECONDS": "nothing (deleted: the groups slice had no reader)",
    "RECONCILIATION_MAX_DELAY_SECONDS": "nothing (deleted: the groups slice had no reader)",
    "CIRCUIT_BREAKER_ENABLED": "nothing (deleted: the groups slice had no reader)",
    "CIRCUIT_BREAKER_FAILURE_THRESHOLD": "nothing (deleted: the groups slice had no reader)",
    "CIRCUIT_BREAKER_TIMEOUT_SECONDS": "nothing (deleted: the groups slice had no reader)",
    "CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS": "nothing (deleted: the groups slice had no reader)",
    "REQUIRE_JUSTIFICATION": "nothing (deleted: the groups slice had no reader)",
    "MIN_JUSTIFICATION_LENGTH": "nothing (deleted: the groups slice had no reader)",
    # Not "secret <NAME>": the JSON value must never be copied into one of the per-id secrets.
    "GOOGLE_RESOURCES": "one secret per id (INCIDENT_CORE__FOLDER_ID, INCIDENT_CORE__REPORT_TEMPLATE_ID, "
    "INCIDENT_CORE__LIST_SHEET_ID, INCIDENT_RESPONSE__HANDBOOK_ID, INCIDENT_POSTMORTEM__CALENDAR_ID, "
    "CLOUD_OPERATIONS_SPENDING__SHEET_ID and the nine TALENT__* ids; doc-14 GOOGLE_RESOURCES ids)",
}

# Names whose values moved before the configuration migration (#975 folded the Google IDs into the one
# GOOGLE_RESOURCES JSON secret; #976 removed the frontend). Their old secrets are leftovers. TASK-111.10.3
# gave each id its own secret; inc.d and rep.g had no reader and were not carried.
SUPERSEDED = {
    "SRE_DRIVE_ID": "GOOGLE_RESOURCES inc.d, itself unread and not carried",
    "SRE_INCIDENT_FOLDER": "GOOGLE_RESOURCES inc.f, now secret INCIDENT_CORE__FOLDER_ID",
    "INCIDENT_TEMPLATE": "GOOGLE_RESOURCES inc.t, now secret INCIDENT_CORE__REPORT_TEMPLATE_ID",
    "INCIDENT_LIST": "GOOGLE_RESOURCES inc.l, now secret INCIDENT_CORE__LIST_SHEET_ID",
    "INTERNAL_TALENT_FOLDER": "GOOGLE_RESOURCES tal.i, now secret TALENT__INTERNAL_FOLDER_ID",
    "SCORING_GUIDE_TEMPLATE": "GOOGLE_RESOURCES tal.s, now secret TALENT__SCORING_GUIDE_TEMPLATE_ID",
    "TEMPLATES_FOLDER": "GOOGLE_RESOURCES tal.t, now secret TALENT__TEMPLATES_FOLDER_ID",
    "CORE_VALUES_INTERVIEW_NOTES_TEMPLATE": "GOOGLE_RESOURCES tal.c, now secret TALENT__CORE_VALUES_INTERVIEW_NOTES_ID",
    "TECHNICAL_INTERVIEW_NOTES_TEMPLATE": "GOOGLE_RESOURCES tal.tech, now secret TALENT__TECHNICAL_INTERVIEW_NOTES_ID",
    "INTAKE_FORM_TEMPLATE": "GOOGLE_RESOURCES tal.int, now secret TALENT__INTAKE_FORM_TEMPLATE_ID",
    "PHONE_SCREEN_TEMPLATE": "GOOGLE_RESOURCES tal.ph, now secret TALENT__PHONE_SCREEN_TEMPLATE_ID",
    "RECRUITMENT_FEEDBACK_TEMPLATE": "GOOGLE_RESOURCES tal.rec, now secret TALENT__RECRUITMENT_FEEDBACK_TEMPLATE_ID",
    "PANELIST_GUIDEBOOK_TEMPLATE": "GOOGLE_RESOURCES tal.pan, now secret TALENT__PANELIST_GUIDEBOOK_TEMPLATE_ID",
    "SPENDING_SHEET_ID": "GOOGLE_RESOURCES aws.s, now secret CLOUD_OPERATIONS_SPENDING__SHEET_ID",
    "GOOGLE_SRE_CALENDAR_ID": "GOOGLE_RESOURCES cal.sre, now secret INCIDENT_POSTMORTEM__CALENDAR_ID",
    "FOLDER_REPORTS_GOOGLE_GROUPS": "GOOGLE_RESOURCES rep.g, itself unread and not carried",
    "FRONTEND_URL": "nothing (the frontend was removed in #976)",
}

FILE_DESTINATION = re.compile(r"(?:production\.toml |file )\[([a-z0-9_.]+)\] ?([a-z0-9_]*)")
PARAMETER_DESTINATION = re.compile(r"secret ([A-Z0-9_]+)")
WORKFLOW_REFERENCE = re.compile(r"\b(?:secrets|vars)\.([A-Za-z0-9_]+)")
# Secrets passed without naming them: every repository secret may be read.
DYNAMIC_SECRETS = re.compile(r"secrets:\s*inherit\b|\bsecrets\[|\b(?:toJSON|fromJSON)\(\s*secrets\b")
# Developer setup that reads the environment: devcontainer files, Makefiles and shell scripts.
SETUP_FILES = (".devcontainer/*", "Makefile", "app/Makefile", "app/bin/*.sh", "bin/*.sh")
SHELL_REFERENCE = re.compile(r"\$\{?([A-Z][A-Z0-9_]+)")
BLOB_END = "the line goes when the blob is deleted"

type Destinations = dict[str, tuple[str, str]]


@dataclass(frozen=True)
class Verdict:
    action: str
    reason: str
    new: str | None = None  # the name the value moves to, when it still has to be copied
    lookup: str | None = None  # a check whose last git reference the wrapper looks up: "workflow" or "repo"


@dataclass(frozen=True)
class Context:
    current: set[str]
    retired: set[str] = field(default_factory=set)
    doc14: Destinations = field(default_factory=dict)
    parameter_states: dict[str, str] = field(default_factory=dict)
    workflow_refs: dict[str, list[str]] = field(default_factory=dict)
    setup_refs: dict[str, list[str]] = field(default_factory=dict)
    last_refs: dict[str, str] = field(default_factory=dict)  # name -> its last reference in git history
    secrets_scan_blind: bool = False  # .github passes secrets dynamically: any repository secret may be read


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


def dynamic_secret_references(root: Path = WORKFLOW_DIR) -> list[str]:
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


def staged_parameters(ctx: Context) -> dict[str, str]:
    """doc-14's /sre-bot/<NAME> parameter destinations, each mapped to the old name that moves there."""
    return {m[1]: old for old, (destination, _) in ctx.doc14.items() if (m := PARAMETER_DESTINATION.match(destination))}


def _is_retired(name: str, ctx: Context) -> bool:
    """Positive evidence of retirement: the migration retired it, or a HINTS or SUPERSEDED entry names it."""
    return name in ctx.retired or name in HINTS or name in SUPERSEDED


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
        if not _is_retired(name, ctx):
            return _unevidenced("commented line of a name nothing reads", name, "repo", ctx)
        now = HINTS.get(name) or SUPERSEDED.get(name) or replacement(name, ctx.current)
        return Verdict("delete", f"commented line of a retired name{'; now ' + now if now else ''}")
    if name in ctx.current:
        return Verdict("none", "read by the app")
    if _is_runtime(name):
        return Verdict("none", "read by the platform, an SDK or uvicorn")
    if files := ctx.setup_refs.get(name):
        return Verdict("none", f"read by developer setup: {', '.join(files)}")
    if old := staged_parameters(ctx).get(name):
        return Verdict("none", f"staged ahead of its reader: doc-14 moves {old} to this secret")
    if name in HINTS:
        if HINTS[name].startswith("nothing"):
            return Verdict("delete", f"retired; {HINTS[name]}")
        secret = PARAMETER_DESTINATION.match(HINTS[name])
        return Verdict("delete", f"retired; set {HINTS[name]} instead", new=secret[1] if secret else None)
    if name in SUPERSEDED:
        return Verdict("delete", f"superseded before the migration by {SUPERSEDED[name]}")
    if name in ctx.retired:
        if new := replacement(name, ctx.current):
            return Verdict("rename", f"set {new} to the same value, then delete {name}", new=new)
        return Verdict("delete", "retired by the configuration migration; the value lives in app/config/*.toml now")
    return _unevidenced("nothing in the repository reads it", name, "repo", ctx)


def _actions(source: str, name: str, ctx: Context) -> Verdict:
    """A GitHub Actions or Dependabot secret or variable: what the workflows read."""
    if files := ctx.workflow_refs.get(name):
        return Verdict("none", f"used by {', '.join(files)}")
    if " org" in source:
        return Verdict("none", "organization-level; other repositories may use it")
    if ctx.secrets_scan_blind and " secret " in source:
        return Verdict("none", "the scan is blind: a workflow passes secrets without naming them")
    if name in HINTS or name in SUPERSEDED or name in ctx.retired:
        return _developer(name, "present", ctx)
    return _unevidenced("no workflow under .github/ on the default branch references it", name, "workflow", ctx)


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
        if match := PARAMETER_DESTINATION.match(destination):
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
    wanted = sorted(staged_parameters(ctx))
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


GH = "env -u GITHUB_TOKEN -u GH_TOKEN gh"  # the user's own login: the Codespace token cannot write secrets
ENV_PREFIX = "[[:space:]]*#?[[:space:]]*(export[[:space:]]+)?"  # an env-file line, commented or exported


def _github_target(source: str, repo: str) -> str | None:
    """The gh flags that address a GitHub secret source; None for organization and production sources."""
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


GENERATED_ENV_EXAMPLE = "app/.env.example"


def fix_commands(sections: dict[str, list[tuple[str, str, Verdict]]], repo: str) -> list[str]:
    """Shell lines that apply each delete or rename row; production and organization rows get none."""
    lines: list[str] = []
    for source, rows in sections.items():
        acting = sorted(
            ((name, verdict) for name, _, verdict in rows if verdict.action in {"delete", "rename"}), key=lambda row: row[0]
        )
        commands: list[str] = []
        if source == f"file {GENERATED_ENV_EXAMPLE}":
            # Generated from the settings classes (make env-example); never edited by a plan.
            continue
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


LEGEND = """actions: none = nothing to do; delete = remove the line or secret; rename = set the new name to the same
value, then delete the old one; check = something disagrees, investigate. Production blob lines are never
edited by hand: the blobs are deleted as a whole (TASK-111.15), so their migrated or unread lines show none."""


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
    if not 1 <= len(args) <= 2:
        raise SystemExit("usage: python -m bin.audit_env_names [--all | --lookups] BASELINE_SHA [BASELINE_APP_DIR] < names.tsv")
    current = env_names(APP_ROOT)
    blind = dynamic_secret_references()
    entries = [line.rstrip("\n").split("\t") for line in sys.stdin if line.strip()]
    ctx = Context(
        current=current,
        retired=baseline_names(args[0], Path(args[1]) if len(args) == 2 else None) - current,
        doc14=doc14_destinations(),
        parameter_states={name: state for source, name, state in entries if source == "ssm-param"},
        workflow_refs=workflow_references(),
        setup_refs=setup_references(),
        last_refs=read_last_refs(os.environ.get("LAST_REFS_FILE")),
        secrets_scan_blind=bool(blind),
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

    if lookups:
        wanted = {(verdict.lookup, name) for rows in sections.values() for name, _, verdict in rows if verdict.lookup}
        print("".join(f"{kind}\t{name}\n" for kind, name in sorted(wanted)), end="")
        return

    print(LEGEND)
    if blind:
        print(f"workflow scan blind for repository secrets: {', '.join(blind)} pass secrets without naming them")
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
        print("\n== plan: commands for the delete and rename rows (nothing has run) ==")
        print("# A secret whose value moves is copied from this Codespace first; GitHub never returns a value.")
        print("\n".join(commands))
    if plan := os.environ.get("PLAN_FILE"):
        Path(plan).write_text("".join(f"{line}\n" for line in commands))
    if not show_all:
        print("rows with action none are hidden; rerun with --all to list them")


if __name__ == "__main__":
    main(sys.argv[1:])
