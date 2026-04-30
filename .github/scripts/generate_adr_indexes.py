#!/usr/bin/env python3
"""Generate ADR index files from frontmatter in docs/decisions/adr/.

Reads all ADR markdown files, parses YAML frontmatter, and writes:
  - docs/decisions/indexes/adr-index.md
  - docs/decisions/indexes/adr-by-domain.md
  - docs/decisions/indexes/adr-review-calendar.md
"""

import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ADR_DIR = REPO_ROOT / "docs/decisions/adr"
SUPERSEDED_DIR = ADR_DIR / "superseded"
INDEX_DIR = REPO_ROOT / "docs/decisions/indexes"

TODAY = date.today()
TODAY_STR = TODAY.isoformat()

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


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


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def compute_review_state(next_review_due: Any) -> str:
    due = _parse_date(next_review_due)
    if due is None:
        return "unknown"
    if due <= TODAY:
        return "stale"
    if due <= TODAY + timedelta(days=30):
        return "expiring-soon"
    return "current"


def _adr_sort_key(adr: dict) -> int:
    try:
        return int(adr["adr_id"].split("-")[1])
    except (KeyError, IndexError, ValueError):
        return 9999


def load_adrs() -> list[dict]:
    adrs: list[dict] = []

    for filepath in sorted(ADR_DIR.glob("*.md")):
        fm = parse_frontmatter(filepath)
        if not fm or not fm.get("adr_id"):
            continue
        fm["_rel_link"] = f"../adr/{filepath.name}"
        adrs.append(fm)

    for filepath in sorted(SUPERSEDED_DIR.glob("*.md")):
        fm = parse_frontmatter(filepath)
        if not fm or not fm.get("adr_id"):
            continue
        fm["_rel_link"] = f"../adr/superseded/{filepath.name}"
        adrs.append(fm)

    adrs.sort(key=_adr_sort_key)
    return adrs


# ---------------------------------------------------------------------------
# Index writers
# ---------------------------------------------------------------------------


def write_adr_index(adrs: list[dict]) -> None:
    active = [a for a in adrs if a.get("status", "").lower() != "superseded"]
    superseded = [a for a in adrs if a.get("status", "").lower() == "superseded"]

    lines = [
        "# ADR Index",
        "",
        f"**Last Updated:** {TODAY_STR}",
        "",
        "This is the complete index of all Architecture Decision Records.",
        "",
        "## Active ADRs (Accepted & Proposed)",
        "",
        "| ID | Title | Status | Tier | Type |",
        "|---|---|---|---|---|",
    ]

    for a in active:
        adr_id = a["adr_id"]
        title = a.get("title", "").strip('"')
        status = a.get("status", "")
        tier = a.get("tier", "").replace("Tier-", "")
        dtype = a.get("decision_type", "")
        link = a["_rel_link"]
        lines.append(f"| [{adr_id}]({link}) | {title} | {status} | {tier} | {dtype} |")

    if superseded:
        lines += [
            "",
            "## Superseded ADRs",
            "",
            "| ID | Title | Superseded By |",
            "|---|---|---|",
        ]
        for a in superseded:
            adr_id = a["adr_id"]
            title = a.get("title", "").strip('"')
            link = a["_rel_link"]
            superseded_by: list[str] = a.get("superseded_by") or []
            by_str = ", ".join(str(x) for x in superseded_by) if superseded_by else "—"
            lines.append(f"| [{adr_id}]({link}) | {title} | {by_str} |")

    lines.append("")
    (INDEX_DIR / "adr-index.md").write_text("\n".join(lines), encoding="utf-8")
    print("  Written: adr-index.md")


def write_adr_by_domain(adrs: list[dict]) -> None:
    active = [a for a in adrs if a.get("status", "").lower() != "superseded"]
    tiers: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))

    for a in active:
        tier = a.get("tier", "Unknown")
        dtype = a.get("decision_type", "Unknown")
        tiers[tier][dtype].append(a)

    def tier_sort_key(t: str) -> int:
        parts = t.split("-")
        return int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 99

    lines = [
        "# ADRs by Tier and Type",
        "",
        f"**Last Updated:** {TODAY_STR}",
        "",
    ]

    for tier in sorted(tiers.keys(), key=tier_sort_key):
        lines.append(f"## {tier}")
        lines.append("")
        for dtype in sorted(tiers[tier].keys()):
            # Pluralise heading: Principle -> Principles, Standard -> Standards, etc.
            heading = dtype + "s" if not dtype.endswith("s") else dtype
            lines.append(f"### {heading}")
            lines.append("")
            for a in tiers[tier][dtype]:
                adr_id = a["adr_id"]
                title = a.get("title", "").strip('"')
                status = a.get("status", "")
                link = a["_rel_link"]
                lines.append(f"- [{adr_id}]({link}): {title} - **{status}**")
            lines.append("")

    (INDEX_DIR / "adr-by-domain.md").write_text("\n".join(lines), encoding="utf-8")
    print("  Written: adr-by-domain.md")


def write_review_calendar(adrs: list[dict]) -> None:
    active = [a for a in adrs if a.get("status", "").lower() != "superseded"]

    def calendar_sort_key(a: dict) -> str:
        due = _parse_date(a.get("next_review_due"))
        return due.isoformat() if due else "9999-12-31"

    lines = [
        "# ADR Review Calendar",
        "",
        f"**Last Updated:** {TODAY_STR}",
        "",
        "| ID | Title | Due Date | Status | Review State |",
        "|---|---|---|---|---|",
    ]

    for a in sorted(active, key=calendar_sort_key):
        adr_id = a["adr_id"]
        title = a.get("title", "").strip('"')
        link = a["_rel_link"]
        due_raw = a.get("next_review_due", "")
        due_str = (
            _parse_date(due_raw).isoformat() if _parse_date(due_raw) else str(due_raw)
        )
        status = a.get("status", "")
        review_state = compute_review_state(due_raw)
        lines.append(
            f"| [{adr_id}]({link}) | {title} | {due_str} | {status} | {review_state} |"
        )

    lines.append("")
    (INDEX_DIR / "adr-review-calendar.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print("  Written: adr-review-calendar.md")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    if not ADR_DIR.is_dir():
        print(f"ERROR: ADR directory not found: {ADR_DIR}", file=sys.stderr)
        sys.exit(1)

    adrs = load_adrs()
    if not adrs:
        print("ERROR: No ADRs with valid frontmatter found.", file=sys.stderr)
        sys.exit(1)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Generating indexes for {len(adrs)} ADRs...")
    write_adr_index(adrs)
    write_adr_by_domain(adrs)
    write_review_calendar(adrs)
    print("Done.")


if __name__ == "__main__":
    main()
