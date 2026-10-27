"""Developer helper: say where each name supplied through the environment is missing.

``bin/env-checks.zsh`` (repository root) pipes the same TSV lines it gives ``bin.audit_env_names``
(``source<TAB>name<TAB>state``, names and states only, never values). That audit judges each name that
is present; this one starts from the names that must be supplied and checks every place that should
hold them:

    terraform  ``terraform/ssm.tf`` creates ``/sre-bot/<NAME>`` (none for a development-only value)
    ssm        the parameter is set, not missing or on the terraform placeholder
    source     the production blob line doc-14 moves to it exists, while the parameter still needs it
    codespaces a Codespace that still has the old name also has the new one
    example    ``app/.env.example`` has a line for it, commented or not, once the app reads it

The names are the parameter destinations of doc-14 and the names ``terraform/ssm.tf`` creates. A row
is ``check`` when any place disagrees, ``none`` otherwise. Without SSM rows (no AWS credentials) the
ssm and source columns are not judged; without an ``app/.env.example`` row, the example column is not.

Usage (from app/): ``uv run python -m bin.audit_env_coverage [--all] [PREFIX...] < names.tsv``; with
prefixes (the wrapper's name filters, which also limit what it collects) only matching names are judged.
"""

import re
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from bin.audit_env_names import (
    APP_ROOT,
    PARAMETER_DESTINATION,
    REPO_ROOT,
    Destinations,
    Verdict,
    doc14_destinations,
    env_names,
)

SSM_TF = REPO_ROOT / "terraform/ssm.tf"
EXAMPLE_SOURCE = "file app/.env.example"
SECRET_NAMES = re.compile(r"sre_bot_secret_names\s*=\s*toset\(\[(.*?)\]\)", re.S)
QUOTED = re.compile(r'"([A-Z0-9_]+)"')
DEVELOPMENT_ONLY = "development only"

type Entry = tuple[str, str, str]


def terraform_parameters(path: Path = SSM_TF) -> set[str]:
    """The ``sre_bot_secret_names`` set of ``terraform/ssm.tf``: each becomes ``/sre-bot/<NAME>``."""
    match = SECRET_NAMES.search(path.read_text())
    return set(QUOTED.findall(match[1])) if match else set()


def _gaps(
    name: str, old: str | None, dev_only: bool, terraform: set[str], entries: list[Entry], read: set[str] | None
) -> list[str]:
    in_doc14 = old is not None
    parameters = {n: s for source, n, s in entries if source == "ssm-param"}
    blob = {n for source, n, s in entries if source.startswith("ssm-blob") and s == "set"}
    codespaces = {n for source, n, _ in entries if source.startswith("codespaces")}
    example = {n for source, n, _ in entries if source == EXAMPLE_SOURCE}
    gaps: list[str] = []

    if dev_only and old in blob:
        gaps.append(f"doc-14 says development only, but production sets {old}: it needs a parameter (fix doc-14)")
    elif dev_only and name in terraform:
        gaps.append("development only, but terraform/ssm.tf creates it (its placeholder would reach production)")
    elif in_doc14 and not dev_only and name not in terraform:
        gaps.append(f"doc-14 moves {old} here, but terraform/ssm.tf does not create it")
    if name in terraform and not in_doc14:
        gaps.append("terraform/ssm.tf creates it, but no doc-14 row moves a value to it")

    if name in terraform and parameters:
        state = parameters.get(name, "missing")
        if state == "missing":
            source = "" if old is None or old in blob else f", and there is no {old} line in the production blobs to copy"
            gaps.append(f"terraform/ssm.tf creates it, but SSM has no parameter yet (tf_apply pending){source}")
        elif state != "set" and old in blob:
            gaps.append(f"parameter is {state}: put-parameter from {old}")
        elif state != "set":
            gaps.append(f"parameter is {state}, and there is no {old} line in the production blobs to copy")

    if old and old in codespaces and name not in codespaces:
        gaps.append(f"Codespaces has {old} but not {name}: set {name} to the same value")
    if example and name not in example and (read is None or name in read):
        gaps.append("no line in app/.env.example: add one (commented is fine)")
    return gaps


def coverage_rows(
    doc14: Destinations, terraform: set[str], entries: Iterable[Entry], read: set[str] | None = None
) -> list[tuple[str, str, Verdict]]:
    """One row per name that must be supplied: (name, summary of where it is, verdict).

    ``read`` is the names the app reads now; only those need an ``app/.env.example`` line (a parameter staged
    ahead of its slice does not). ``None`` judges every name.
    """
    collected = list(entries)
    moves: dict[str, tuple[str, bool]] = {}
    for source_name, (destination, _) in doc14.items():
        if match := PARAMETER_DESTINATION.match(destination):
            moves[match[1]] = (source_name, DEVELOPMENT_ONLY in destination)
    parameters = {n: s for source, n, s in collected if source == "ssm-param"}
    rows = []
    for name in sorted(moves.keys() | terraform):
        old, dev_only = moves.get(name, (None, False))
        gaps = _gaps(name, old, dev_only, terraform, collected, read)
        where = [
            "terraform" if name in terraform else ("no terraform (development only)" if dev_only else "no terraform"),
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
    rows = [
        row
        for row in coverage_rows(doc14_destinations(), terraform_parameters(), entries, env_names(APP_ROOT))
        if row[0].startswith(prefixes or "")
    ]
    counts = Counter(verdict.action for _, _, verdict in rows)
    print("\n== coverage: names supplied through the environment == " + " ".join(f"{a}={n}" for a, n in sorted(counts.items())))
    for name, where, verdict in sorted(rows, key=lambda row: (row[2].action == "none", row[0])):
        if show_all or verdict.action != "none":
            print(f"{verdict.action:<6} {name} [{where}]: {verdict.reason}")
    if not show_all and counts["none"]:
        print("coverage rows with action none are hidden; rerun with --all to list them")


if __name__ == "__main__":
    main(sys.argv[1:])
