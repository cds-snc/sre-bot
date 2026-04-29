---
adr_id: ADR-0051
title: "ADR Taxonomy and Classification Enforcement Standard"
status: Accepted
decision_type: Standard
tier: Tier-2
primary_domain: Governance and Operating Model
secondary_domains:
 - Delivery and Environment Parity
owners:
 - SRE Team
date_created: 2026-04-28
last_updated: 2026-04-28
last_reviewed: 2026-04-28
next_review_due: 2026-08-26
constrained_by:
 - ADR-0044
impacts:
 - ADR-0052
 - ADR-0053
 - ADR-0054
 - ADR-0063
 - ADR-0065
supersedes:
 - ADR-0019
 - ADR-0032
superseded_by: []
review_state: current
related_records:
 - ADR-0044
 - ADR-0045
related_packages: []
---
## Context

- Problem statement: Legacy ADR records mixed authority levels, used inconsistent decision_type values, and allowed Tier-1 records to include implementation-level policy.
- Business/operational drivers: Enforce stable governance boundaries so downstream rewrites can proceed without recurring scope drift.
- Constraints:
 - Keep directory strategy flat under `docs/decisions/adr`.
 - Preserve explicit supersession chains for traceability.
 - Apply the 18-field metadata contract to all newly authored ADRs.
- Non-goals:
 - This record does not rewrite Wave 1 canonical principle content.
 - This record does not define feature-local API behavior.

## Decision

- Chosen approach:
 - Adopt a mandatory taxonomy enforcement standard for all active ADR authoring and rewrites.
 - Define a hard one-to-one mapping between tier and decision_type values (as constrained by ADR-0044 and the metadata reference).
 - Prohibit broad `Feature` as a decision_type; use `Feature Decision` or `Integration Decision` at Tier-4.
 - Require that platform-wide conventions remain in Tier-2 (`Standard` or `Pattern`) and not Tier-4.
 - Require each ADR review to include explicit checks for:
 - one decision per record;
 - one authority level per record;
 - no Tier-1 implementation leakage.
- Why this approach:
 - Converts classification guidance into enforceable review policy.
 - Reduces repeated corrective refactors caused by ambiguous ADR scopes.
- Principles established:
 - Classification is governance, not optional style.
 - Tier boundaries must remain explicit, reviewable, and auditable.

## Alternatives Considered

1. Keep classification as advisory guidance only.
 - Pros: Less short-term rewrite overhead.
 - Cons: Drift recurs and ambiguity remains during future ADR updates.
 - Why not chosen: Does not satisfy Step 5 exit criteria for clean tier boundaries.
2. Encode taxonomy only in filenames/directories.
 - Pros: Fast visual grouping.
 - Cons: Weak semantic validation and poor compatibility with current tooling constraints.
 - Why not chosen: Metadata-driven governance is required by ADR-0044.

## Consequences

- Positive impacts:
 - Tier and decision_type consistency becomes enforceable at review time.
 - New ADRs can be audited automatically for schema and taxonomy compliance.
- Tradeoffs accepted:
 - Additional authoring and review overhead for metadata correctness.
- Risks introduced:
 - Legacy records may remain partially non-compliant until rewritten.
 - In a single-maintainer workflow, review classification checks can be skipped under time pressure, allowing mixed-scope records to reappear without detection.
- Mitigations:
 - Apply supersession updates in each rewrite wave and prioritize foundational records first.
 - Automate tier/decision_type compatibility checks so enforcement does not depend solely on manual review discipline.

## Compliance and Boundaries

- Package/infrastructure boundary impact:
 - Indirect only; this ADR constrains governance classification for records that define those boundaries.
- Type boundary impact (Protocol/dataclass/BaseModel/TypedDict):
 - Indirect only; this ADR defines where type-boundary policy belongs by tier.
- Startup/plugin registration impact:
 - Clarifies startup/plugin policy belongs in Tier-2 standards under Tier-1 principles.
- Settings partitioning impact:
 - Clarifies settings governance split between Tier-1 principle and Tier-2 implementation standards.

## Best-Practice Revalidation

- Revalidation date: 2026-04-28
- Sources rechecked:
 - ADR governance and classification best practice (one decision per ADR, explicit supersession).
 - Twelve-Factor factor ownership guidance for architecture/deployment concerns.
- Alignment summary:
 - Classification model remains aligned to metadata-first ADR governance and current Twelve-Factor delivery concerns.
- Intentional deviations:
 - None.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Classification constraints match ADR-0044 governance baseline and Step 5 taxonomy reset objectives.
- Follow-up actions:
 - Enforce this taxonomy in all Wave 2+ ADR rewrites and during metadata automation checks.

## Source References (Required)

1. Source title: ADR Governance and Operating Model
 - URL: docs/decisions/adr/0044-adr-governance-operating-model.md
 - Publisher/maintainer: SRE Team
 - Accessed date (YYYY-MM-DD): 2026-04-28
 - Relevance summary: Provides governance baseline, classification rules, and supersession requirements.
2. Source title: ADR Metadata Reference
 - URL: docs/decisions/templates/adr-metadata-reference.md
 - Publisher/maintainer: SRE Team
 - Accessed date (YYYY-MM-DD): 2026-04-28
 - Relevance summary: Defines mandatory schema and tier/decision_type compatibility table.
3. Source title: The Twelve-Factor App
 - URL: https://12factor.net/
 - Publisher/maintainer: 12factor contributors
 - Accessed date (YYYY-MM-DD): 2026-04-28
 - Relevance summary: Confirms deployment and operations factors that require clear ADR ownership at appropriate tiers.

## Implementation Guidance

- Required changes:
 - Review and reclassify ADR metadata when the current tier/decision_type pair is non-compliant.
 - Reject new ADRs that use invalid decision_type values for their declared tier.
 - Build and integrate a lint check that statically validates tier/decision_type compatibility before any ADR is merged; this is a required gate, not an advisory check.
 - Make one-decision-per-record and one-authority-level-per-record checks explicit items in every review packet; they must not be implicit.
- Validation and quality gates:
 - Automated metadata schema validation (tier/decision_type compatibility table must be machine-checkable).
 - Supersession bidirectionality checks (if A supersedes B, B's superseded_by must reference A).
 - Review-state freshness checks.
 - Explicit checklist confirmation that no Tier-1 implementation detail has leaked into the record under review.
- Test strategy and acceptance criteria impact:
 - Step 5 is accepted when taxonomy constraints are codified, lint automation is defined, and Twelve-Factor gap ADR ownership records are authored.

## Change Log

- 2026-04-28: Created canonical taxonomy enforcement standard for Phase A execution; superseded ADR-0019 and ADR-0032.
- 2026-04-28: Strengthened risks and implementation guidance following challenge review; named single-maintainer enforcement gap and elevated lint automation from follow-up action to required gate.
