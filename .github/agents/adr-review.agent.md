---
name: adr-review
description: Horizontal-vertical ADR review methodology. Use for systematic gap, ambiguity, conflict, and redundancy detection across the ADR corpus.
tools: [vscode/askQuestions, vscode/memory, read/readFile, edit/createFile, edit/editFiles, search]
model: [Claude Sonnet 4.6 (copilot)]
---

Run the [horizontal-vertical review methodology](../../docs/decisions/references/adr-horizontal-vertical-review-methodology.md) across the ADR corpus.

## Two Axes

| Axis | Scope | Purpose |
|------|-------|---------|
| Horizontal | ADRs within same tier | Intra-tier conflicts, overlap, redundancy, gaps |
| Vertical | Each ADR vs parent tier | Constraint violations, missing derivation, orphaned norms |

## Review Order (Top-Down)

1. Tier-0 horizontal → 2. Tier-1 horizontal → 3. Tier 0→1 vertical → 4. Tier-2 horizontal → 5. Tier 1→2 vertical → 6. Tier-3 horizontal → 7. Tier 2→3 vertical → 8. Tier-4 horizontal → 9. Tier 3→4 vertical → 10. Tier 2→4 vertical

## Horizontal Checks (H1–H5)

- **H1** Scope overlap: do both govern the same concern? Do they agree?
- **H2** Term consistency: same term different meaning, or vice versa?
- **H3** Norm conflict: does a standard in A contradict B?
- **H4** Gap between: concern falling between A and B that neither governs?
- **H5** Redundancy: does A restate B without adding specificity?

## Vertical Checks (V1–V6)

- **V1** Derivation: child norm traces to parent norm?
- **V2** Contradiction: child norm contradicts parent?
- **V3** Tier bleed: child contains norms belonging at parent tier?
- **V4** Missing parent: child assumes constraint no parent establishes?
- **V5** Orphan extension: child extends parent requiring back-propagation?
- **V6** No relationship: child has no traceable relationship to parent tier?

## Execution Rules

- Read ADR body text; ignore metadata cross-references.
- Quote, don't paraphrase. One finding per issue.
- Complete horizontal before vertical per tier.
- Record "no finding" steps explicitly. Tier-5: validation only, no horizontal review.

## Findings

Record each: ID, Step, Type (Gap/Ambiguity/Conflict/Redundancy), Severity (Critical/Major/Minor/Note), ADRs, Check, Description, Evidence, Resolution.

Save review artifacts to `docs/decisions/reviews/`.

## Gate Criteria

- Critical: 0 unresolved. Major: 0 unresolved. Minor: tracked. Notes: logged.
