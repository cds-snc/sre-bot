"""Developer helper: say where each name supplied through the environment is missing.

``bin/env-checks.zsh`` (repository root) pipes the same TSV lines it gives ``bin.audit_env_names``
(``source<TAB>name<TAB>state``, names and states only, never values). That audit judges each name that
is present; this one starts from the names that must be supplied and checks every place that should
hold them:

    terraform  ``terraform/ssm.tf`` creates ``/sre-bot/<NAME>`` only for a name an env-only field reads
    ssm        the parameter is set, not missing or on the terraform placeholder
    codespaces a name whose metadata sends developers to a Codespaces secret has one, unless development
               leaves the vendor unconfigured (a [<slice>.tenant] entry in production.toml and none in
               local.toml): then the slice-level credential alone fails local boot, so a Codespace must not
               hold it

The names are the env-only settings fields (``contracts.configuration.env_only``, collected as
``bin/generate_env_example.py`` collects them) and the names ``terraform/ssm.tf`` creates; an env-only
name terraform does not create is development only. ``app/.env.example`` is not judged: it is generated
and a test fails when it drifts. A row is ``check`` when any place disagrees, ``none`` otherwise.
Without SSM rows (no AWS credentials) or Codespaces rows (no gh auth) that column is not judged.

Usage (from app/): ``uv run python -m bin.audit_env_coverage [--all] [PREFIX...] < names.tsv``; with
prefixes (the wrapper's name filters, which also limit what it collects) only matching names are judged.
"""

import re
import sys
import tomllib
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from bin.audit_env_names import APP_ROOT, REPO_ROOT, Verdict
from bin.generate_env_example import collect

SSM_TF = REPO_ROOT / "terraform/ssm.tf"
CONFIG_DIR = APP_ROOT / "config"
SECRET_NAMES = re.compile(r"sre_bot_secret_names\s*=\s*toset\(\[(.*?)\]\)", re.S)
QUOTED = re.compile(r'"([A-Z0-9_]+)"')

type Entry = tuple[str, str, str]


def terraform_parameters(path: Path = SSM_TF) -> set[str]:
    """The ``sre_bot_secret_names`` set of ``terraform/ssm.tf``: each becomes ``/sre-bot/<NAME>``."""
    match = SECRET_NAMES.search(path.read_text())
    return set(QUOTED.findall(match[1])) if match else set()


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


def unconfigured_in_development(name: str) -> str | None:
    """The tenant table a slice-level credential needs when production configures it and local does not, else None."""
    if "__" not in name or "__TENANT__" in name:
        return None
    tenant = f"{name.split('__')[0].lower()}.tenant"
    return tenant if config_table("production", tenant) and not config_table("local", tenant) else None


def _gaps(name: str, developer_source: str | None, terraform: set[str], entries: list[Entry]) -> list[str]:
    parameters = {n: s for source, n, s in entries if source == "ssm-param"}
    codespaces = {n for source, n, _ in entries if source.startswith("codespaces")}
    gaps: list[str] = []

    if name in terraform and developer_source is None:
        gaps.append("terraform/ssm.tf creates it, but no env-only settings field reads it")
    if name in terraform and parameters:
        param_state = parameters.get(name, "missing")
        if param_state == "missing":
            gaps.append("terraform/ssm.tf creates it, but SSM has no parameter yet (tf_apply pending)")
        elif param_state != "set":
            gaps.append(f"parameter is {param_state}: set it with put-parameter")

    if tenant := unconfigured_in_development(name):
        if name in codespaces:
            gaps.append(f"Codespaces has {name}, but local.toml has no [{tenant}]: it fails local boot, delete it")
    elif developer_source == "codespaces" and codespaces and name not in codespaces:
        gaps.append("its metadata names a Codespaces secret, but no Codespaces secret provides it")
    return gaps


def coverage_rows(env_only: Mapping[str, str], terraform: set[str], entries: Iterable[Entry]) -> list[tuple[str, str, Verdict]]:
    """One row per name that must be supplied: (name, summary of where it is, verdict).

    ``env_only`` maps each env-only name to the developer source its metadata names.
    """
    collected = list(entries)
    parameters = {n: s for source, n, s in collected if source == "ssm-param"}
    rows = []
    for name in sorted(env_only.keys() | terraform):
        gaps = _gaps(name, env_only.get(name), terraform, collected)
        where = [
            "terraform" if name in terraform else "no terraform (development only)",
            f"ssm {parameters.get(name, 'missing')}" if parameters and name in terraform else "",
        ]
        verdict = Verdict("check", "; ".join(gaps)) if gaps else Verdict("none", "supplied everywhere it is needed")
        rows.append((name, ", ".join(w for w in where if w), verdict))
    return rows


def main(argv: list[str]) -> None:
    show_all = "--all" in argv
    prefixes = tuple(a for a in argv if a != "--all")
    entries: list[Entry] = []
    for line in sys.stdin:
        if len(fields := line.rstrip("\n").split("\t")) == 3:
            entries.append((fields[0], fields[1], fields[2]))
    env_only = {entry.name: entry.source for entry in collect()[0]}
    rows = [row for row in coverage_rows(env_only, terraform_parameters(), entries) if row[0].startswith(prefixes or "")]
    counts = Counter(verdict.action for _, _, verdict in rows)
    print("\n== coverage: names supplied through the environment == " + " ".join(f"{a}={n}" for a, n in sorted(counts.items())))
    for name, where, verdict in sorted(rows, key=lambda row: (row[2].action == "none", row[0])):
        if show_all or verdict.action != "none":
            print(f"{verdict.action:<6} {name} [{where}]: {verdict.reason}")
    if not show_all and counts["none"]:
        print("coverage rows with action none are hidden; rerun with --all to list them")


if __name__ == "__main__":
    main(sys.argv[1:])
