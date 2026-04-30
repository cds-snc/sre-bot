---
name: adr-review
description: Run horizontal-vertical review across the ADR corpus for gap, conflict, and redundancy detection.
agent: adr-review
model: Claude Sonnet 4.6 (copilot)
---

Run the horizontal-vertical ADR review methodology on the corpus.

ADR index: [adr-index.md](../../docs/decisions/indexes/adr-index.md). Methodology: [adr-horizontal-vertical-review-methodology.md](../../docs/decisions/references/adr-horizontal-vertical-review-methodology.md).

## Output

1. Corpus snapshot: ADR count per tier, domain clusters for Tier-2.
2. Step-by-step results for all 10 review steps.
3. Each finding: ID, step, type, severity, ADRs, check, evidence, resolution.
4. Dashboard: severity × type matrix.
5. Gate assessment: Critical/Major must be 0 unresolved.

## Rules

- Read ADR body text, not just metadata.
- Complete horizontal before vertical per tier.
- Record "no finding" steps explicitly.
- Save review artifacts to `docs/decisions/reviews/`.
