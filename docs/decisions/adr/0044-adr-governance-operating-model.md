---
adr_id: ADR-0044
title: "ADR Governance and Operating Model"
status: Accepted
decision_type: Governance Policy
tier: Tier-0
primary_domain: Governance and Operating Model
secondary_domains:
 - Runtime and Lifecycle
 - Configuration and Secrets
 - Dependency and Composition
 - Delivery and Environment Parity
 - Testing and Quality Gates
owners:
 - SRE Team
date_created: 2026-04-28
last_updated: 2026-05-01
last_reviewed: 2026-04-30
next_review_due: 2026-08-28
constrained_by: []
impacts:
 - ADR-0001
 - ADR-0002
 - ADR-0003
 - ADR-0004
 - ADR-0005
 - ADR-0006
 - ADR-0007
 - ADR-0009
 - ADR-0010
 - ADR-0011
 - ADR-0013
 - ADR-0017
 - ADR-0020
 - ADR-0026
 - ADR-0027
supersedes: []
superseded_by: []
review_state: current
related_records:
 - ADR-0001
 - ADR-0002
 - ADR-0003
 - ADR-0005
 - ADR-0006
 - ADR-0007
 - ADR-0009
 - ADR-0010
 - ADR-0011
 - ADR-0013
 - ADR-0017
 - ADR-0020
 - ADR-0026
 - ADR-0027
 - ADR-0080
related_packages: []
---
# ADR Governance and Operating Model

## Context

- Problem statement: The ADR corpus has mixed scope, duplicate authority, and inconsistent review freshness, which makes architecture governance ambiguous during rewrite work.
- Business/operational drivers:
- Establish one authoritative governance baseline for all subsequent ADR rewrites and additions.
- Reduce policy drift by defining tier boundaries, lifecycle rules, and ownership accountability in one place.
- Enable predictable review automation and supersession behavior.
- Constraints:
- Keep ADR directory flat under docs/decisions/adr for tooling compatibility.
- Require explicit supersession metadata and 120-day freshness policy.
- Enforce compatibility with target architecture boundaries across app/infrastructure, app/server, and app/packages.
- Non-goals:
- This record does not perform ADR content rewrites itself.
- This record does not define domain-level implementation standards for individual features.

## Decision

- Chosen approach:
- Establish a Tier-0 governance ADR that constrains all downstream ADR rewrites and new records.
- Keep flat ADR directory structure as the default policy; defer nested-directory decisions to a future Tier-0 ADR.
- Adopt a mandatory metadata contract for governance use: adr_id, title, status, tier, decision_type, primary_domain, secondary_domains, owners, date_created, last_updated, last_reviewed, next_review_due, constrained_by, impacts, supersedes, superseded_by, review_state.
- Set review freshness policy to 120 days with review states current, expiring-soon, stale.
- Require explicit bidirectional supersession links: replacement ADRs must declare supersedes and replaced ADRs must declare superseded_by.
- Require all rewritten or newly authored ADRs to list ADR-0044 in constrained_by.
- Define ownership model as centralized SRE decision authority (single active owner currently), with external contributors advisory-only.
- Why this approach:
- Creates a stable authority layer before rewriting Tier-1 and Tier-2 records.
- Removes ambiguity about directory structure, review cadence, and supersession behavior.
- Minimizes operational overhead while the team remains single-threaded.
- Principles established:
- One ADR, one decision, one authority level.
- Higher-tier ADRs constrain lower-tier ADRs through explicit metadata links.
- Within a tier, later-arriving ADRs may declare `constrained_by` references to earlier same-tier ADRs when they build on established norms. This intra-tier constraint pattern is valid and expected at Tier-1 and Tier-2.
- Domain-tier ADRs (Tier-3) may constrain cross-cutting ADRs (Tier-2) when the cross-cutting standard operates within the domain's scope. The `impacts`/`constrained_by` metadata records this relationship regardless of tier direction.
- The `impacts` and `constrained_by` metadata fields must be maintained bidirectionally: if ADR-A declares `impacts: [ADR-B]`, then ADR-B must declare `constrained_by: [ADR-A]`.
- Time-bound migration and deprecation decisions must use Tier-5 and include retirement criteria.
- Infrastructure library adoption decisions must use Tier-5 and include evaluation criteria (maturity, maintenance status, license compatibility with the project license, type-hint coverage, async compatibility) to govern the long-term dependency commitment. Library licenses must be compatible with the project's own license (currently MIT); incompatible licenses are grounds for rejection regardless of technical merit. This complements ADR-0045 P7 (Managed Service Delegation Hierarchy), which establishes library delegation as Tier 2 in the three-tier hierarchy.
- Foundational ADRs remain implementation-agnostic; implementation details belong in lower tiers.

## Alternatives Considered

1. Keep governance guidance spread across review notes and per-ADR conventions:

- Pros: No additional foundational ADR needed.
- Cons: Continued policy ambiguity and weak enforceability.
- Why not chosen: Does not provide a canonical source of governance truth.

1. Adopt nested ADR directories immediately:

- Pros: Filesystem grouping by tier/domain can improve browsing.
- Cons: Higher migration risk and tooling incompatibility for current automation.
- Why not chosen: Flat structure has better immediate compatibility; nested remains a future governance decision.

## Consequences

- Positive impacts:
- All downstream ADR rewrites and new records have explicit governance constraints and ownership expectations.
- Supersession and review lifecycle become deterministic and automatable.
- Tier boundaries are now enforceable during review.
- Tradeoffs accepted:
- Governance metadata requirements increase ADR authoring overhead.
- Flat structure relies on metadata/index generation rather than directory hierarchy.
- Risks introduced:
- Existing ADRs without full metadata may remain temporarily non-compliant.
- Single-owner governance can become a bottleneck.
- Mitigations:
- Prioritize metadata normalization and review automation before rewrite editing starts.
- Revisit ownership model in this ADR when team size and review capacity increase.

## Compliance and Boundaries

- Package/infrastructure boundary impact:
- Governance only; no direct runtime code boundary changes.
- Type boundary impact (Protocol/dataclass/BaseModel/TypedDict):
- Not applicable; this is a governance decision record.
- Startup/plugin registration impact:
- Governance reinforces startup-driven registration policy through constrained downstream ADRs.
- Settings partitioning impact:
- Governance requires configuration decisions to remain partitioned and documented in canonical settings ADRs.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Governance baseline aligned to 2026-04-28 exhaustive review conclusions and adopted Phase 2 ADR metadata policy.
- Follow-up actions:
- Add/verify automation for due-date notifications, stale marking, and review prompts before rewrite editing starts.
- All rewritten or newly authored ADRs must include constrained_by: [ADR-0044].

## Source References

1. Source title: ADR Exhaustive Review Working Notes

- Publisher/maintainer: SRE Team
- Accessed date (YYYY-MM-DD): 2026-04-28
- Relevance summary: Defines finalized clarifications and Step 1 governance requirements. Key outputs: ADR-0044 metadata contract (18 fields), tier classification system (Tier 0-5), flat directory strategy, and challenge review gate model. Ephemeral working document; findings are fully captured in this ADR and the canonical migration map.

1. Source title: Decisions Documentation

- URL: docs/decisions/README.md
- Publisher/maintainer: Platform Engineering
- Accessed date (YYYY-MM-DD): 2026-04-28
- Relevance summary: Confirms current ADR storage conventions and phase policy references.

1. Source title: Phase 2 Kickoff: ADR Identifier and Metadata Normalization

- URL: docs/decisions/reviews/2026-04-28-phase-2-normalization-kickoff.md
- Publisher/maintainer: Platform Engineering
- Accessed date (YYYY-MM-DD): 2026-04-28
- Relevance summary: Captures adopted canonical ID, metadata, and stale policy decisions used by this governance baseline.

## Implementation Guidance

- Required changes:
- Use this ADR as a mandatory constraining record for all downstream rewrites and new records.
- Ensure each rewritten or new ADR includes explicit constrained_by and impacts links.
- Enforce one-decision-per-record and one-tier-per-record checks during review.
- Validation and quality gates:
- Metadata contract validation for required fields.
- Review state automation validation for current, expiring-soon, stale transitions.
- Index and review calendar generation consistency checks.
- Test strategy and acceptance criteria impact:
- Governance acceptance criteria are satisfied when all downstream ADRs declare this record in constrained_by and review automation is active.

## Change Log

- 2026-04-28: Created Tier-0 governance baseline as canonical authority for ADR lifecycle, ownership, supersession, and downstream rewrite constraints.
- 2026-04-30: Tier-5 library trigger amendment. Added infrastructure library adoption as an explicit Tier-5 ADR trigger. See delegation tracker Item #3.
- 2026-04-30: License compatibility amendment (editorial). Strengthened library evaluation criterion: library licenses must be compatible with the project's own license (currently MIT); incompatible licenses are grounds for rejection regardless of technical merit.
- 2026-04-30: Constraint model clarification (editorial, HV Review findings H-003, H-010, V-016). Acknowledged intra-tier `constrained_by` relationships, upward domain-tier constraint pattern, and bidirectional `impacts`/`constrained_by` metadata invariant.
- 2026-05-01: Tier blast radius amendment (editorial, ADR-0080 follow-up). Updated Tier-1 and Tier-2 blast radius descriptions in metadata reference template to cover both application and infrastructure governance domains per ADR-0080. Added ADR-0080 to `related_records`.
