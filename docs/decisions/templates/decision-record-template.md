# Decision Record Template

Copy this file to `docs/decisions/adr/NNNN-kebab-case-title.md` and fill in every field.
All 19 metadata fields are required — see [adr-metadata-reference.md](adr-metadata-reference.md)
for allowed values, field definitions, and the tier/decision-type compatibility table.

---
adr_id: ADR-0000
title: "Short decision title"
status: Draft
decision_type: Principle
tier: Tier-1
governance_domain: application
primary_domain: "Runtime and Lifecycle"
secondary_domains: []
owners:
  - SRE Team
date_created: YYYY-MM-DD
last_updated: YYYY-MM-DD
last_reviewed: YYYY-MM-DD
next_review_due: YYYY-MM-DD
constrained_by:
  - ADR-0044
impacts: []
supersedes: []
superseded_by: []
review_state: current
related_records: []
related_packages: []
---

## Context

- Problem statement:
- Business/operational drivers:
- Constraints:
- Non-goals:

## Decision

- Chosen approach:
- Why this approach:
- Principles established:

## Alternatives Considered

1. Option name:
   - Pros:
   - Cons:
   - Why not chosen:
2. Option name:
   - Pros:
   - Cons:
   - Why not chosen:

## Consequences

- Positive impacts:
- Tradeoffs accepted:
- Risks introduced:
- Mitigations:

## Compliance and Boundaries

- Package/infrastructure boundary impact:
- Type boundary impact (Protocol/dataclass/BaseModel/TypedDict):
- Startup/plugin registration impact:
- Settings partitioning impact:

## Freshness Review

- Record age at review time (days):
- Is record older than 120 days: Yes | No
- If Yes, status set to stale: Yes | No
- Validation summary:
- Follow-up actions:

## Source References (Required)

List every source used for new or revised guidance.

1. Source title:
   - URL:
   - Publisher/maintainer:
   - Accessed date (YYYY-MM-DD):
   - Relevance summary:
2. Source title:
   - URL:
   - Publisher/maintainer:
   - Accessed date (YYYY-MM-DD):
   - Relevance summary:

## Derivation from Higher-Tier ADRs (Tier-4 only)

> **Include this section only for Tier-4 (Feature Decision / Integration Decision) ADRs.**
> Every Tier-4 ADR must derive its constraints from settled higher-tier ADRs and address
> only decisions specific to the feature's domain. If a decision would apply to any other
> feature in the same situation, it belongs in a higher tier.

### Derivation Test Checklist

Before authoring, confirm all four checks pass:

1. **Tier-bleed check:** For each norm, ask: "Would this apply to a hypothetical different
   feature with similar needs?" If yes → belongs in Tier-2/3, not Tier-4.
2. **Constraint chain check:** `constrained_by` must trace to settled Tier-1/2/3 ADRs.
   If no constraining ADR exists, either (a) author the higher-tier ADR first, or
   (b) the decision is too platform-wide for Tier-4.
3. **Single-concern check:** The ADR addresses exactly one feature-scoped decision.
   If the Context section describes problems at multiple tiers, split the record.
4. **Domain-specificity check:** Standards/Principles reference domain entities, events,
   or workflows that do not exist outside this feature.

### Constraint Derivation Table

| Constraint | Source ADR | How This Feature Applies It |
|------------|-----------|----------------------------|
| [Tier-2 standard rule] | ADR-NNNN Standard X | [Feature-specific application] |
| [Tier-1 principle] | ADR-NNNN Principle Y | [Feature-specific application] |

### Feature-Specific Decisions (Not Governed by Higher Tiers)

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| [Domain-specific choice] | [Why this choice for this feature] | [What else was considered] |

### Scoping Rules (Complex Features)

> For features with multiple sub-functionalities, apply these rules:
>
> - **One ADR per sub-feature concern:** Each sub-feature has its own domain model and lifecycle.
> - **Shared concerns get a separate ADR:** Common config, naming, or event contracts get their own Tier-4 record.
> - **ADR-per-decision, not ADR-per-package:** A sub-feature with no feature-specific decisions beyond higher-tier mandates does not need a Tier-4 ADR.
> - **Cross-sub-feature coordination is a separate decision:** Interaction contracts between sub-features get their own Tier-4 ADR.

## Implementation Guidance

- Required changes:
- Validation and quality gates:
- Test strategy and acceptance criteria impact:

## Change Log

- YYYY-MM-DD: Summary of changes and reason.