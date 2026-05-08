#!/usr/bin/env python3
"""Generate a unified ADR index from frontmatter in docs/adr/.

Reads all ADR markdown files, parses YAML frontmatter, and writes a single
index file: docs/adr/INDEX.md

The index is organized by governance domain → tier → concern tags, providing
multiple views into the same corpus for discoverability.
"""

import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ADR_DIR = REPO_ROOT / "docs/adr"

TODAY = date.today()
TODAY_STR = TODAY.isoformat()

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)

VALID_TIERS = {"Tier-0", "Tier-1", "Tier-2", "Tier-3"}
VALID_TYPES = {"Governance", "Principle", "Standard", "Selection", "Deprecation"}
VALID_DOMAINS = {"application", "operations"}
VALID_STATUSES = {
    "Draft",
    "Proposed",
    "Accepted",
    "Superseded",
    "Deprecated",
    "Rejected",
}

TIER_ORDER = {"Tier-0": 0, "Tier-1": 1, "Tier-2": 2, "Tier-3": 3}
TIER_NAMES = {
    "Tier-0": "Governance",
    "Tier-1": "Foundational",
    "Tier-2": "Cross-cutting",
    "Tier-3": "Scoped",
}


def parse_frontmatter(filepath: Path) -> dict[str, Any] | None:
    text = filepath.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        print(
            f"WARN: Failed to parse frontmatter in {filepath}: {exc}", file=sys.stderr
        )
        return None


def validate_frontmatter(fm: dict, filename: str) -> list[str]:
    """Validate frontmatter against the governance metadata contract."""
    errors: list[str] = []

    # Required fields
    for field in ("title", "status", "type", "tier", "date", "decision_makers"):
        if not fm.get(field):
            errors.append(f"Missing required field: {field}")

    # Enum validations
    if fm.get("tier") and fm["tier"] not in VALID_TIERS:
        errors.append(f"Invalid tier: {fm['tier']} (allowed: {VALID_TIERS})")

    if fm.get("type") and fm["type"] not in VALID_TYPES:
        errors.append(f"Invalid type: {fm['type']} (allowed: {VALID_TYPES})")

    if fm.get("status") and fm["status"] not in VALID_STATUSES:
        errors.append(f"Invalid status: {fm['status']} (allowed: {VALID_STATUSES})")

    # Tier-1+ must have governance_domain and concerns
    tier = fm.get("tier", "")
    if tier in ("Tier-1", "Tier-2", "Tier-3"):
        domains = fm.get("governance_domain", [])
        if not domains:
            errors.append("Tier-1+ records must declare governance_domain")
        elif isinstance(domains, list):
            for d in domains:
                if d not in VALID_DOMAINS:
                    errors.append(f"Invalid governance_domain: {d}")
        elif isinstance(domains, str):
            if domains not in VALID_DOMAINS:
                errors.append(f"Invalid governance_domain: {domains}")

        if not fm.get("concerns"):
            errors.append("Tier-1+ records must declare concerns")

    # Deprecation type must have retirement_date
    if fm.get("type") == "Deprecation" and not fm.get("retirement_date"):
        errors.append("Deprecation type requires retirement_date")

    return errors


def load_adrs() -> list[dict]:
    """Load all ADRs from docs/adr/, excluding template/index files."""
    adrs: list[dict] = []
    skip_dirs = {"templates", "superseded"}
    skip_prefixes = ("index-", "INDEX")

    for filepath in sorted(ADR_DIR.glob("*.md")):
        if filepath.name.startswith(tuple(skip_prefixes)):
            continue
        if any(part in skip_dirs for part in filepath.parts):
            continue

        fm = parse_frontmatter(filepath)
        if not fm:
            continue

        # Only include records with minimum required fields
        if not fm.get("title") or not fm.get("tier"):
            continue

        fm["_filename"] = filepath.name
        fm["_errors"] = validate_frontmatter(fm, filepath.name)
        adrs.append(fm)

    return adrs


def normalize_list(value: Any) -> list[str]:
    """Normalize a field value to a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def format_adr_entry(adr: dict) -> str:
    """Format a single ADR as a markdown list item."""
    filename = adr["_filename"]
    title = adr.get("title", "").strip('"')
    status = adr.get("status", "Draft")
    adr_type = adr.get("type", "Unknown")
    concerns = normalize_list(adr.get("concerns"))

    status_badge = f"`{status}`"
    type_badge = f"`{adr_type}`"
    concern_str = ", ".join(f"`{c}`" for c in concerns) if concerns else "—"

    return (
        f"- [{filename}]({filename}) — **{title}**\n"
        f"  - {type_badge} · {status_badge} · {concern_str}"
    )


def write_index(adrs: list[dict]) -> None:
    """Write the unified INDEX.md file."""
    lines = [
        "# Decision Record Index",
        "",
        f"**Generated:** {TODAY_STR} · **Total records:** {len(adrs)}",
        "",
        "---",
        "",
    ]

    # --- Summary table ---
    lines.append("## Summary")
    lines.append("")
    lines.append("| Tier | Application | Operations | Cross-domain |")
    lines.append("|------|-------------|------------|--------------|")

    for tier in sorted(VALID_TIERS, key=lambda t: TIER_ORDER[t]):
        tier_adrs = [a for a in adrs if a.get("tier") == tier]
        if tier == "Tier-0":
            lines.append(f"| {tier} ({TIER_NAMES[tier]}) | — | — | {len(tier_adrs)} |")
        else:
            app_count = sum(
                1
                for a in tier_adrs
                if "application" in normalize_list(a.get("governance_domain"))
                and "operations" not in normalize_list(a.get("governance_domain"))
            )
            ops_count = sum(
                1
                for a in tier_adrs
                if "operations" in normalize_list(a.get("governance_domain"))
                and "application" not in normalize_list(a.get("governance_domain"))
            )
            cross_count = sum(
                1
                for a in tier_adrs
                if "application" in normalize_list(a.get("governance_domain"))
                and "operations" in normalize_list(a.get("governance_domain"))
            )
            lines.append(
                f"| {tier} ({TIER_NAMES[tier]}) | {app_count} | {ops_count} | {cross_count} |"
            )

    lines.append("")
    lines.append("---")
    lines.append("")

    # --- By Domain → Tier ---
    lines.append("## By Domain")
    lines.append("")

    # Tier-0 (no domain)
    tier0_adrs = [a for a in adrs if a.get("tier") == "Tier-0"]
    if tier0_adrs:
        lines.append("### Tier-0: Governance")
        lines.append("")
        for adr in tier0_adrs:
            lines.append(format_adr_entry(adr))
        lines.append("")

    # Application domain
    app_adrs = [
        a
        for a in adrs
        if a.get("tier") != "Tier-0"
        and "application" in normalize_list(a.get("governance_domain"))
    ]
    if app_adrs:
        lines.append("### Application")
        lines.append("")
        for tier in ("Tier-1", "Tier-2", "Tier-3"):
            tier_subset = [a for a in app_adrs if a.get("tier") == tier]
            if tier_subset:
                lines.append(f"#### {tier}: {TIER_NAMES[tier]}")
                lines.append("")
                for adr in tier_subset:
                    lines.append(format_adr_entry(adr))
                lines.append("")

    # Operations domain
    ops_adrs = [
        a
        for a in adrs
        if a.get("tier") != "Tier-0"
        and "operations" in normalize_list(a.get("governance_domain"))
    ]
    if ops_adrs:
        lines.append("### Operations")
        lines.append("")
        for tier in ("Tier-1", "Tier-2", "Tier-3"):
            tier_subset = [a for a in ops_adrs if a.get("tier") == tier]
            if tier_subset:
                lines.append(f"#### {tier}: {TIER_NAMES[tier]}")
                lines.append("")
                for adr in tier_subset:
                    lines.append(format_adr_entry(adr))
                lines.append("")

    lines.append("---")
    lines.append("")

    # --- By Concern Tag ---
    lines.append("## By Concern")
    lines.append("")

    concern_map: dict[str, list[dict]] = defaultdict(list)
    for adr in adrs:
        for concern in normalize_list(adr.get("concerns")):
            concern_map[concern].append(adr)

    for concern in sorted(concern_map.keys()):
        lines.append(f"### `{concern}`")
        lines.append("")
        for adr in concern_map[concern]:
            lines.append(format_adr_entry(adr))
        lines.append("")

    # --- Validation errors ---
    error_adrs = [a for a in adrs if a.get("_errors")]
    if error_adrs:
        lines.append("---")
        lines.append("")
        lines.append("## Validation Issues")
        lines.append("")
        lines.append(
            "The following records have metadata issues per "
            "[decision-record-governance.md](decision-record-governance.md):"
        )
        lines.append("")
        for adr in error_adrs:
            filename = adr["_filename"]
            lines.append(f"- **{filename}**")
            for err in adr["_errors"]:
                lines.append(f"  - ⚠️ {err}")
        lines.append("")

    output_path = ADR_DIR / "INDEX.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Written: INDEX.md ({len(adrs)} records)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    if not ADR_DIR.is_dir():
        print(f"ERROR: ADR directory not found: {ADR_DIR}", file=sys.stderr)
        sys.exit(1)

    adrs = load_adrs()
    if not adrs:
        print("WARN: No ADRs with valid frontmatter found.", file=sys.stderr)
        # Write an empty index rather than failing
        (ADR_DIR / "INDEX.md").write_text(
            f"# Decision Record Index\n\n**Generated:** {TODAY_STR} · **Total records:** 0\n\nNo decision records found.\n",
            encoding="utf-8",
        )
        print("  Written: INDEX.md (empty)")
        return

    print(f"Generating index for {len(adrs)} ADRs...")
    write_index(adrs)

    # Report validation summary
    error_count = sum(1 for a in adrs if a.get("_errors"))
    if error_count:
        print(f"  ⚠️  {error_count} record(s) have validation issues.")

    print("Done.")


if __name__ == "__main__":
    main()
