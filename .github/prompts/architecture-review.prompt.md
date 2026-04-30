---
name: architecture-review
description: Author or revise an ADR following the authoring workflow lifecycle with challenge review and source citations.
agent: architecture
model: Claude Sonnet 4.6 (copilot)
---

Author or revise an architecture decision record following the [ADR authoring workflow](../../docs/decisions/references/adr-authoring-workflow.md).

ADRs in [docs/decisions/adr/](../../docs/decisions/adr/) are the source of truth. Index: [adr-index.md](../../docs/decisions/indexes/adr-index.md).

Follow [copilot-instructions.md](../copilot-instructions.md) for all architectural constraints.

## Output

1. Pre-author gate assessment (ID allocation, dependency check).
2. Applicable ADRs cited by number — confirm alignment or identify conflicts.
3. Freshness audit: web-validate any referenced ADR older than 30 days.
4. Draft or revision with all 18 metadata fields.
5. Challenge review executed and saved to `reviews/`.
6. Source references for every decision statement.
7. ADR create/update list with status changes.
8. Handoff packet for feature architecture (if applicable).

## Rules

- Classify new ADRs per ADR-0051 taxonomy.
- Tier-4: apply derivation test before authoring.
- Challenge reviews require web-validated external standards.
