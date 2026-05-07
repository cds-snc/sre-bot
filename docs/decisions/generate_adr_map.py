#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
import re

ADR_RE = re.compile(r"ADR-\d{4}")


def parse_frontmatter(text: str) -> dict[str, object]:
    if not text.startswith("---\n"):
        return {}

    end = text.find("\n---\n", 4)
    if end == -1:
        return {}

    block = text[4:end]
    lines = block.splitlines()
    meta: dict[str, object] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue

        if ":" not in line:
            i += 1
            continue

        key, raw = line.split(":", 1)
        key = key.strip()
        value = raw.strip()

        if not value:
            items: list[str] = []
            j = i + 1
            while j < len(lines):
                li = lines[j]
                if li.startswith("  - ") or li.startswith("- "):
                    item = li.split("-", 1)[1].strip().strip('"')
                    items.append(item)
                    j += 1
                    continue
                if not li.strip():
                    j += 1
                    continue
                break

            meta[key] = items
            i = j
            continue

        if value == "[]":
            meta[key] = []
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                meta[key] = []
            else:
                meta[key] = [
                    v.strip().strip('"') for v in inner.split(",") if v.strip()
                ]
        else:
            meta[key] = value.strip('"')

        i += 1

    return meta


def adr_refs(value: object) -> list[str]:
    if isinstance(value, list):
        refs: list[str] = []
        for item in value:
            refs.extend(ADR_RE.findall(str(item)))
        return refs
    if isinstance(value, str):
        return ADR_RE.findall(value)
    return []


def adr_sort_key(record: dict[str, object]) -> tuple[int, str]:
    adr_id = str(record.get("adr_id", ""))
    m = re.search(r"(\d{4})", adr_id)
    return (int(m.group(1)) if m else 9999, adr_id)


def load_records(files: list[Path], root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        meta = parse_frontmatter(text)
        if not meta:
            continue
        records.append(
            {
                "path": path.relative_to(root).as_posix(),
                "adr_id": str(meta.get("adr_id", "")),
                "title": str(meta.get("title", "-")).strip('"') or "-",
                "status": str(meta.get("status", "")),
                "decision_type": str(meta.get("decision_type", "-")).strip('"') or "-",
                "tier": str(meta.get("tier", "-")),
                "primary_domain": str(meta.get("primary_domain", "-")).strip('"')
                or "-",
                "supersedes": meta.get("supersedes", []),
                "superseded_by": meta.get("superseded_by", []),
                "related_records": meta.get("related_records", []),
            }
        )
    return records


def render_counts(counter: Counter[str], order: list[str]) -> list[str]:
    lines: list[str] = []
    for status in order:
        lines.append(f"- {status}: {counter.get(status, 0)}")
    return lines


def generate_map(base_dir: Path) -> str:
    adr_dir = base_dir / "adr"
    superseded_dir = adr_dir / "superseded"

    active_files = sorted(adr_dir.glob("*.md"))
    superseded_files = sorted(superseded_dir.glob("*.md"))

    active = load_records(active_files, base_dir.parent)
    superseded = load_records(superseded_files, base_dir.parent)
    all_records = active + superseded

    all_status = Counter(r["status"] for r in all_records)
    active_status = Counter(r["status"] for r in active)

    supersedence_index: dict[str, list[str]] = defaultdict(list)
    for rec in superseded:
        old_id = str(rec["adr_id"])
        for new_id in adr_refs(rec["superseded_by"]):
            supersedence_index[new_id].append(old_id)

    id_to_active = {str(r["adr_id"]): r for r in active}
    candidates: list[str] = []
    for rec in sorted(active, key=adr_sort_key):
        if rec["status"] != "Draft":
            continue
        supersedes_raw = rec["supersedes"]
        supersedes_refs = adr_refs(supersedes_raw)
        for target in supersedes_refs:
            tgt = id_to_active.get(target)
            if tgt and tgt.get("status") == "Accepted":
                candidates.append(
                    f"- `{rec['adr_id']}` (Draft) explicitly supersedes `{target}` while `{target}` is still Accepted and active. This creates transitional dual authority in scope."
                )
        if isinstance(supersedes_raw, str) and "partial" in supersedes_raw.lower():
            candidates.append(
                f"- `{rec['adr_id']}` (Draft) declares partial supersession of `{', '.join(supersedes_refs)}`. Until accepted and merged, both documents can be interpreted as authoritative in the same slice."
            )

    if {"ADR-0084", "ADR-0089", "ADR-0090"}.issubset(id_to_active):
        candidates.append(
            "- `ADR-0084`, `ADR-0089`, and `ADR-0090` (all Draft) overlap identity/transport handler boundaries already covered by Accepted `ADR-0061`, `ADR-0060`, and `ADR-0063`."
        )
    if "ADR-0091" in id_to_active:
        candidates.append(
            "- `ADR-0091` (Draft, Data and Persistence) intersects handler reliability and idempotency concerns already constrained by runtime and transport standards (`ADR-0057`, `ADR-0058`, `ADR-0060`, `ADR-0063`)."
        )

    id_counts = Counter(str(r["adr_id"]) for r in all_records)
    duplicate_ids = sorted([k for k, v in id_counts.items() if k and v > 1])
    active_superseded = sorted(
        [r for r in active if r["status"] == "Superseded"], key=adr_sort_key
    )
    missing_domain = sorted(
        [r for r in active if r["primary_domain"] in {"", "-"}], key=adr_sort_key
    )

    lines: list[str] = []
    lines.append("# ADR Map: Current State")
    lines.append("")
    lines.append(f"Date: {date.today().isoformat()}")
    lines.append(
        "Source scope: `docs/decisions/adr/*.md` and `docs/decisions/adr/superseded/*.md`"
    )
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append(
        "This document is a map of ADR metadata and interrelations in the repository."
    )
    lines.append("It is intentionally not a migration plan and not a tracker.")
    lines.append("")
    lines.append("## Corpus Snapshot")
    lines.append("")
    lines.append(f"- Total ADR files: {len(all_records)}")
    lines.append(f"- Active-directory ADR files (`docs/decisions/adr`): {len(active)}")
    lines.append(
        f"- Superseded-directory ADR files (`docs/decisions/adr/superseded`): {len(superseded)}"
    )
    lines.append("")
    lines.append("### Status Distribution (all ADR files)")
    lines.append("")
    lines.extend(
        render_counts(all_status, ["Accepted", "Draft", "Rejected", "Superseded"])
    )
    lines.append("")
    lines.append("### Status Distribution (active directory only)")
    lines.append("")
    lines.extend(
        render_counts(active_status, ["Accepted", "Draft", "Rejected", "Superseded"])
    )
    lines.append("")
    lines.append("## Interrelation Map")
    lines.append("")
    lines.append("### Supersedence Index (from superseded ADR metadata)")
    lines.append("")
    lines.append(
        "This table maps each superseding ADR ID to the ADR IDs it supersedes."
    )
    lines.append(
        "Note: a superseding ADR ID can itself now be superseded historically."
    )
    lines.append("")
    lines.append("| Superseding ADR ID | Title | Superseded ADR IDs |")
    lines.append("|---|---|---|")
    for sup_id in sorted(supersedence_index):
        title_text = "-"
        for rec in active:
            if str(rec["adr_id"]) == sup_id:
                title_text = str(rec["title"])[:60]  # Truncate long titles
                break
        old = "<br>".join(sorted(supersedence_index[sup_id]))
        lines.append(f"| {sup_id} | {title_text} | {old} |")

    lines.append("")
    lines.append("## Potential Scope Tension / Conflict Candidates")
    lines.append("")
    lines.append(
        "These are scope-overlap candidates to review, not confirmed contradictions."
    )
    lines.append("")
    if candidates:
        lines.extend(candidates)
    else:
        lines.append(
            "- No obvious transitional scope conflicts detected by metadata rules."
        )

    lines.append("")
    lines.append("## Metadata Quality Flags")
    lines.append("")
    if duplicate_ids:
        lines.append("- Duplicate ADR IDs exist across directories:")
        for adr_id in duplicate_ids:
            lines.append(
                f"  - `{adr_id}` appears in both active and superseded locations."
            )
    if active_superseded:
        lines.append("- Active ADRs already marked `Superseded`:")
        for rec in active_superseded:
            lines.append(f"  - `{rec['path']}`")
    if missing_domain:
        ids = ", ".join(f"`{r['adr_id']}`" for r in missing_domain)
        lines.append(
            f"- Active ADR files missing `primary_domain` and shown as `-` in the table below: {ids}."
        )

    lines.append("")
    lines.append("## Active ADR Inventory (Complete)")
    lines.append("")
    lines.append("| ADR | Title | Status | Tier | Type | Primary Domain | Supersedes |")
    lines.append("|---|---|---|---|---|---|---|")
    for rec in sorted(active, key=adr_sort_key):
        supersedes_refs = adr_refs(rec["supersedes"])
        supersedes_display = "<br>".join(supersedes_refs) if supersedes_refs else "-"
        title_text = str(rec["title"])[:55]  # Truncate long titles for readability
        lines.append(
            "| {adr} | {title} | {status} | {tier} | {dtype} | {domain} | {supersedes} |".format(
                adr=rec["adr_id"],
                title=title_text,
                status=rec["status"],
                tier=rec["tier"],
                dtype=rec["decision_type"],
                domain=rec["primary_domain"],
                supersedes=supersedes_display,
            )
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    output_path = script_dir / "adr-map-current-state.md"
    content = generate_map(script_dir)
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
