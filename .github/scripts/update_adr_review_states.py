#!/usr/bin/env python3
"""Update review_state frontmatter field in-place for all ADR files.

Computes review_state from next_review_due relative to today:
  current       - next_review_due is more than 30 days away
  expiring-soon - next_review_due falls within the next 30 days (inclusive)
  stale         - next_review_due is today or in the past
  unknown       - next_review_due is absent or unparseable

Only non-superseded ADRs are included in stale/expiring-soon notifications.

Writes:
  --summary-out  Path  JSON summary (default: /tmp/adr_review_summary.json)
  --report-out   Path  Markdown report for GitHub Issue body
                       (default: /tmp/adr_review_report.md)

Exit code:
  0 - completed successfully (stale/expiring-soon ADRs may still exist)
  1 - fatal error (missing ADR directory, YAML parse failure on >=1 file)
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ADR_DIR = REPO_ROOT / "docs/decisions/adr"

TODAY = date.today()
EXPIRING_SOON_DAYS = 30

# Matches the YAML front matter block at the start of a file.
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


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
    if due <= TODAY + timedelta(days=EXPIRING_SOON_DAYS):
        return "expiring-soon"
    return "current"


# ---------------------------------------------------------------------------
# In-place frontmatter updater
# ---------------------------------------------------------------------------


def update_file_review_state(filepath: Path) -> tuple[str | None, str | None, dict]:
    """Read filepath, compute correct review_state, update frontmatter in-place.

    Returns (old_state, new_state, frontmatter_dict).
    Returns (None, None, {}) when the file has no valid ADR frontmatter.
    Returns (state, state, fm) when no update was needed (old == new).
    """
    text = filepath.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, None, {}

    fm_content = match.group(1)
    try:
        fm: dict = yaml.safe_load(fm_content) or {}
    except yaml.YAMLError as exc:
        print(f"WARN: YAML parse error in {filepath.name}: {exc}", file=sys.stderr)
        return None, None, {}

    if not fm.get("adr_id"):
        return None, None, {}

    new_state = compute_review_state(fm.get("next_review_due"))
    old_state = str(fm.get("review_state", "unknown"))

    if old_state != new_state:
        updated_fm_content = _replace_review_state(fm_content, new_state)
        # Reconstruct full file: everything before group(1) + updated content + rest
        new_text = text[: match.start(1)] + updated_fm_content + text[match.end(1) :]
        filepath.write_text(new_text, encoding="utf-8")
        fm["review_state"] = new_state

    return old_state, new_state, fm


def _replace_review_state(fm_content: str, new_state: str) -> str:
    """Replace or append review_state in the raw frontmatter string."""
    pattern = re.compile(r"^(review_state:[ \t]*)\S+", re.MULTILINE)
    if pattern.search(fm_content):
        return pattern.sub(lambda m: m.group(1) + new_state, fm_content)
    # Field absent — append before end of content
    return fm_content.rstrip("\n") + f"\nreview_state: {new_state}"


# ---------------------------------------------------------------------------
# ADR file discovery  (supports both flat and future nested layouts)
# ---------------------------------------------------------------------------


def collect_adr_files() -> list[Path]:
    return sorted(ADR_DIR.rglob("*.md"))


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------


def _adr_row(fm: dict) -> dict:
    return {
        "adr_id": fm.get("adr_id", ""),
        "title": str(fm.get("title", "")).strip('"'),
        "next_review_due": str(fm.get("next_review_due", "")),
        "status": str(fm.get("status", "")),
    }


def build_summary(results: list[tuple[str | None, str | None, dict]]) -> dict:
    by_state: dict[str, list[dict]] = defaultdict(list)
    changed: list[dict] = []

    for old_state, new_state, fm in results:
        if new_state is None:
            continue
        by_state[new_state].append(_adr_row(fm))
        if old_state != new_state:
            changed.append(
                {
                    "adr_id": fm.get("adr_id", ""),
                    "from": old_state,
                    "to": new_state,
                }
            )

    return {
        "date": TODAY.isoformat(),
        "total": sum(len(v) for v in by_state.values()),
        "changed": len(changed),
        "changes": changed,
        "by_state": dict(by_state),
    }


def build_markdown_report(summary: dict) -> str:
    stale = summary["by_state"].get("stale", [])
    expiring = summary["by_state"].get("expiring-soon", [])
    current = summary["by_state"].get("current", [])
    unknown = summary["by_state"].get("unknown", [])

    lines: list[str] = [
        "## ADR Review Notification",
        "",
        f"**Generated:** {summary['date']}  ",
        f"**Total ADRs scanned:** {summary['total']}  ",
        f"**States updated this run:** {summary['changed']}",
        "",
    ]

    if not stale and not expiring:
        lines += [
            "> All ADRs are current or have no review date assigned.",
            "",
        ]
    else:
        lines += [
            "### Action Required",
            "",
        ]

    if stale:
        lines += [
            f"#### Stale ({len(stale)}) — review overdue",
            "",
            "| ADR | Title | Due Date | Status |",
            "|---|---|---|---|",
        ]
        for a in sorted(stale, key=lambda x: x["next_review_due"]):
            lines.append(
                f"| {a['adr_id']} | {a['title']} | {a['next_review_due']} | {a['status']} |"
            )
        lines.append("")

    if expiring:
        lines += [
            f"#### Expiring Soon ({len(expiring)}) — review due within {EXPIRING_SOON_DAYS} days",
            "",
            "| ADR | Title | Due Date | Status |",
            "|---|---|---|---|",
        ]
        for a in sorted(expiring, key=lambda x: x["next_review_due"]):
            lines.append(
                f"| {a['adr_id']} | {a['title']} | {a['next_review_due']} | {a['status']} |"
            )
        lines.append("")

    if current:
        lines += [
            f"#### Current ({len(current)}) — no action needed",
            "",
        ]

    if unknown:
        lines += [
            f"#### Unknown ({len(unknown)}) — missing or invalid next_review_due",
            "",
            "| ADR | Title |",
            "|---|---|",
        ]
        for a in unknown:
            lines.append(f"| {a['adr_id']} | {a['title']} |")
        lines.append("")

    if summary["changes"]:
        lines += [
            "### State Changes This Run",
            "",
            "| ADR | From | To |",
            "|---|---|---|",
        ]
        for c in summary["changes"]:
            lines.append(f"| {c['adr_id']} | {c['from']} | {c['to']} |")
        lines.append("")

    lines += [
        "---",
        "_This issue is auto-generated by the [ADR Review State workflow]"
        "(.github/workflows/adr_review_states.yml). "
        "Close it once all stale and expiring-soon ADRs have been reviewed._",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=Path("/tmp/adr_review_summary.json"),
        help="Path to write JSON summary (default: /tmp/adr_review_summary.json)",
    )
    parser.add_argument(
        "--report-out",
        type=Path,
        default=Path("/tmp/adr_review_report.md"),
        help="Path to write Markdown report (default: /tmp/adr_review_report.md)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not ADR_DIR.is_dir():
        print(f"ERROR: ADR directory not found: {ADR_DIR}", file=sys.stderr)
        sys.exit(1)

    files = collect_adr_files()
    results: list[tuple[str | None, str | None, dict]] = []
    fatal = False

    for filepath in files:
        old_state, new_state, fm = update_file_review_state(filepath)
        if new_state is None and fm == {}:
            # File had no valid ADR frontmatter — skip silently unless it looks
            # like an ADR (starts with "---") to surface genuine parse errors.
            if filepath.read_text(encoding="utf-8").startswith("---"):
                print(f"WARN: Skipped {filepath.name} (no adr_id)", file=sys.stderr)
            continue

        results.append((old_state, new_state, fm))

        if old_state != new_state:
            print(
                f"  Updated {filepath.name}: {old_state} -> {new_state}",
                file=sys.stderr,
            )

    if fatal:
        sys.exit(1)

    summary = build_summary(results)
    report = build_markdown_report(summary)

    args.summary_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    args.report_out.write_text(report, encoding="utf-8")

    stale_n = len(summary["by_state"].get("stale", []))
    expiring_n = len(summary["by_state"].get("expiring-soon", []))
    current_n = len(summary["by_state"].get("current", []))
    unknown_n = len(summary["by_state"].get("unknown", []))

    print(
        f"Processed {summary['total']} ADRs "
        f"({summary['changed']} state(s) updated).",
        file=sys.stderr,
    )
    print(
        f"  stale={stale_n}  expiring-soon={expiring_n}  "
        f"current={current_n}  unknown={unknown_n}",
        file=sys.stderr,
    )
    print(f"Summary: {args.summary_out}", file=sys.stderr)
    print(f"Report:  {args.report_out}", file=sys.stderr)


if __name__ == "__main__":
    main()
