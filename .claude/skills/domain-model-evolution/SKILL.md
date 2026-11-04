---
name: domain-model-evolution
description: Stress-test domain models for safe evolution and reuse. Use when introducing or reshaping an entity, writing an entity-related decision or task plan, re-planning an epic, or assessing similar records and compatibility during a model pivot.
---

# Domain Model Evolution

Apply this gate before a domain model is fixed in a decision record or approved task plan, and again when a new use case challenges it. A planning pivot can cost only document and task edits; stored records and dependent clients may require migration and a coordinated rollout.

## 1. Stress-test against a scenario catalogue

1. List domain-relevant scenarios the feature must serve, not only the one that prompted it. Include at least one that strains each axis; the incident example below is illustrative, not mandatory for other domains.
2. Build a cardinality matrix: entities per parent, participants and affected assets, plus lifetime, ownership and visibility. Include zero/one/many where plausible and record which the domain permits. Flag every "many" cell where the model assumes "one".
3. Walk each scenario through create, link/unlink, split, reassign, close and roll up. Record edge cases, evidence of mismatches and the resulting decisions; similar fields are a prompt to examine semantics, not proof of duplication.
4. Preserve the matrix, edge-case evidence, chosen/rejected options and rationale in the approved task plan via the backlog CLI. Analysis documents and disposable delivery maps may help, but must not be the only record.
5. At human review, exercise at least two contrasting scenarios: the happy path and the one most likely to break the model. When implemented, turn the approved scenarios and edge cases into deterministic behavior tests, not tests of planning text.

## 2. Reuse semantics, not just shape

- **Reuse requires common lifecycle, ownership and visibility as well as shape.** For example, response and follow-up ActionItems may share one canonical type with a `kind` for purpose when those semantics align. Similar fields across domains do not require a merger; distinct semantics may justify a new entity with explicit rationale.
- **Optional typed references are an option, not a universal pivot strategy.** Prove that existing records remain valid and that cardinality, visibility and ownership are preserved. A link must not silently expose restricted data, change authority or collapse a many-to-many relationship; a separate entity or explicit migration may be needed.
- **Give a shared type a clear canonical owner.** Subdomains may add behavior per kind without creating mirrors; do not centralize genuinely different domain entities merely because their fields match.
- **Index by what jobs read** (kind, due date, root), so adding a kind does not make existing jobs scan more.
- **Check established names.** Before introducing a term, search relevant ADRs, approved plans, contracts and i18n catalogues. Avoid collisions; any rename needs an explicit compatibility and migration plan.

## 3. Make boundary extensibility explicit

- Only explicitly opted-in **display/taxonomy values** are extensible. API/event contracts must document unknown-value handling; this is not permission to open every enum.
- Clients render unknown display/taxonomy values tolerantly with a clearly labelled fallback such as "Unknown value", without silently treating them as a known state or enabling actions.
- **Reject unsupported command/status values; fail closed for authorization and state changes**, including unknown values in events. Display fallbacks must never grant permissions or trigger transitions.
- Additions, including optional fields, links and new kinds, are **not inherently non-breaking**. Test old clients and stored records for parsing, defaults, cardinality, ownership and visibility. Renames/removals require an explicit expand/migrate/contract plan.
- Transport schemas follow [type-model-boundaries](../type-model-boundaries/SKILL.md): Pydantic at the edge, frozen dataclasses inside, explicit conversion between them.

## 4. Review and cascade the pivot

- ADRs state invariants and rationale: which entities exist, who owns them and what must hold. Contractually necessary field names are appropriate; exhaustive schemas belong in task plans and code, not ADRs.
- **Stop at the model-pivot/plan checkpoint for human review before implementation.** Persist the evidence and proposed decisions in the task plan; changed assumptions invalidate prior approval and require re-approval.
- For an approved pivot, review and update the complete cascade (backlog artifacts through the CLI):
  - Affected ADRs, including invariant/rationale changes and a dated change note.
  - Sibling and consumer tasks, their plans and ACs; dependencies and delivery sequence.
  - Delivery maps, briefings and related documentation; keep durable decisions in approved plans, not only maps.
  - Old/new field names and `kind` values, stored-data and client migrations, compatibility/rollback steps and their AC/test coverage.

## Worked example: six incident scenarios

These are candidate cardinalities to validate, not universal constraints. Multi-issue variants are possible in every row, not only VDP.

| Scenario | Issues per incident to exercise | Edge case to preserve |
| --- | --- | --- |
| CVE | One vulnerability; several in an exploit chain | A shared fix spans multiple teams/repositories. |
| Credential compromise | One credential; several principals or credentials | Reassignment must not expose restricted identities. |
| Shared-platform outage | One dependency; several failed components | Teams recover independently; rollup must not close unfinished work. |
| Vendor incident | One advisory; several product/version issues | Vendor and internal ownership boundaries remain distinct. |
| Privacy breach | One exposure; several datasets or disclosure paths | Visibility stays restricted across links and rollups. |
| VDP or pentest report | One finding; many independent vulnerabilities | Findings fan out across teams/repositories with different completion times. |

Across rows, exercise one/many teams per issue, one/many repositories per team, no repository for non-code work, and independent ActionItem completion; record which relationships the domain allows. Where response and follow-up work share lifecycle, ownership and visibility, one ActionItem with a purpose `kind` can survive incident closure instead of being duplicated. An optional incident/finding link still needs the preservation and compatibility checks above.

## Anti-patterns

- Designing from the single scenario that prompted the work.
- Merging on field similarity alone, or duplicating a shared entity solely because its phase changes.
- Assuming an optional link or new kind is automatically safe.
- Treating unknown commands, statuses or authorization values like harmless display labels.
- Exhaustive schemas in ADRs, or durable scenario evidence only in a disposable map.
- Reusing a term that already means something else in the domain.

## Review Checklist

1. Are the scenario/cardinality matrix, edge-case evidence and decisions preserved in the approved plan?
2. Is reuse or a new entity justified by lifecycle, ownership and visibility, not merely shape?
3. Do links/additions preserve old records and the permitted cardinalities and authority boundaries?
4. Is display/taxonomy extensibility opt-in, with labelled unknown rendering and fail-closed command/state handling?
5. Are old-client/stored-record compatibility and deterministic behavior tests planned?
6. Do ADRs capture invariants/rationale at the right detail level, and is the full pivot cascade reviewed?
7. Has human review exercised contrasting scenarios and approved the model/plan before implementation?
