---
title: "Decision Record Governance"
status: Draft
decision_type: Governance Policy
tier: Tier-0
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Decision Record Governance

## Context

### Problem

Architectural knowledge decays when decisions are undocumented, scattered, or ambiguous. Without a governance framework, teams make conflicting choices, duplicate effort, and lose the rationale behind existing design. A single small team needs a lightweight but enforceable system for recording, classifying, and maintaining architectural decisions.

### Drivers

- A single team owns all architectural authority; the process must be low-overhead for one or two contributors while remaining scalable if the team grows.
- Decisions span two distinct governance domains (application code and hosting infrastructure) that evolve at different rates.
- GC policy requires defensible rationale for technology choices, especially around security, accessibility, official languages, and cloud portability.
- The codebase follows a modular monolith pattern where decisions at one layer constrain behavior at lower layers — this hierarchy must be explicit and traceable.

### Constraints

- Flat directory structure under `docs/adr/` for tooling compatibility.
- All decisions must cite authoritative sources (official documentation, established methodologies) — not prior implementations.

### Non-goals

- This record does not define application architecture, standards, or patterns — those are downstream decisions constrained by this one.
- This record does not prescribe tooling for automation, linting, or CI enforcement of decision records.

## Decision

### 1. One decision, one record, one authority level

Each decision record addresses exactly one architectural problem. If a record needs to prescribe rules at multiple authority levels, it must be split.

### 2. Tiered authority model

Decisions are classified by blast radius. Higher-tier decisions constrain lower-tier decisions through explicit metadata links.

| Tier | Authority Level | Blast Radius |
|------|----------------|--------------|
| Tier-0 | Governance | Entire repository — how decisions themselves are made |
| Tier-1 | Principle | Foundational architectural truths across one governance domain |
| Tier-2 | Standard / Pattern | Mandatory conventions or reusable strategies across multiple components |
| Tier-3 | Domain Contract | Stable boundary contracts within one domain and its integration points |
| Tier-4 | Feature / Integration | One feature or one external integration path |
| Tier-5 | Time-Bound | Temporary decisions with explicit retirement criteria and target date |

### 3. Decision-type catalog

Each record uses exactly one type, constrained by its tier:

| Tier | Allowed Types |
|------|--------------|
| Tier-0 | Governance Policy |
| Tier-1 | Principle |
| Tier-2 | Standard, Pattern |
| Tier-3 | Domain Contract, Domain Standard |
| Tier-4 | Feature Decision, Integration Decision |
| Tier-5 | Migration Decision, Deprecation Decision, Library Adoption Decision |

### 4. Two governance domains

Records at Tier-1 and below must declare one governance domain:

- **application** — governs the Python FastAPI codebase (`app/`): architecture, runtime behavior, business logic, and internal APIs.
- **infrastructure** — governs hosting, CI/CD, and cloud-native components (`terraform/`, `.github/workflows/`, deployment configs).

Tier-0 governance records are domain-agnostic and omit this field — they govern the decision process itself, not a specific codebase area.

### 5. Record naming and identity

Each record is identified by its kebab-case filename (e.g., `decision-record-governance.md`). There is no numeric ID sequence. Cross-references between records use filenames.

### 6. Record structure

Every decision record must contain:

1. **Context and Problem Statement**: What is the problem? What forces or concerns drive this decision? What are the constraints and non-goals?
2. **Considered Options**: At least two alternatives, each with pros and cons.
3. **Decision Outcome**: Which option was chosen and why. What rules or principles does it establish?
4. **Consequences**: Positive impacts, accepted tradeoffs, risks, mitigations.
5. **Confirmation** *(optional)*: How compliance with this decision will be verified (e.g., code review checklist, automated check, test).
6. **Source References**: Authoritative external sources. Each must include title, URL, and a one-line relevance summary.
7. **Change Log**: Dated entries for all modifications.

### 7. Metadata contract

Every record must declare these fields in its YAML frontmatter:

**Required:**

| Field | Purpose |
|-------|--------|
| `title` | Short, decision-focused phrase |
| `status` | Draft, Proposed, Accepted, Superseded, Deprecated, Rejected |
| `decision_type` | From the type catalog (must match tier) |
| `tier` | Tier-0 through Tier-5 |
| `date` | ISO 8601 date of last update |
| `decision_makers` | People who made or own this decision |

**Conditional:**

| Field | When Required |
|-------|--------|
| `governance_domain` | Tier-1+ only (application or infrastructure); omit for Tier-0 |
| `primary_domain` | Tier-1+ only; exactly one from the domain list |
| `supersedes` | When this record replaces another; list filenames |
| `superseded_by` | When this record has been replaced; list filenames |
| `constrained_by` | When higher-tier records govern this one; list filenames |
| `retirement_date` | Tier-5 only; target date for retirement |

**Optional:**

| Field | Purpose |
|-------|--------|
| `consulted` | People whose expertise was sought (two-way communication) |
| `informed` | People kept up-to-date (one-way communication) |
| `secondary_domains` | Additional domains from the domain list |

`constrained_by` and `supersedes`/`superseded_by` links must be maintained bidirectionally.

### 8. Primary domain list

- Runtime and Lifecycle
- Configuration and Secrets
- Dependency and Composition
- Package and Plugin Architecture
- Transport and API
- Data and Persistence
- Security and Access Control
- Observability and Operations
- Delivery and Environment Parity
- Testing and Quality Gates
- Governance and Operating Model

### 9. Supersession rules

- Replacement records list the replaced filename(s) in `supersedes`.
- Replaced records set `status: Superseded` and list the replacement filename(s) in `superseded_by`.
- Links are bidirectional and mandatory.

### 10. Decision readiness

A decision should not be recorded until its readiness criteria are met (adapted from Ozimmer's START framework):

1. **Stakeholders** — Decision makers and affected parties are identified.
2. **Timing** — The most responsible moment has arrived; deferring further would increase risk.
3. **Alternatives** — At least two options are understood with their tradeoffs.
4. **Requirements** — The problem, constraints, and decision drivers are clear.
5. **Template** — The record structure is agreed upon and ready to use.

### 11. Freshness policy

| State | Condition |
|-------|-----------|
| current | Reviewed within the past 120 days |
| expiring-soon | Next review due within 30 days |
| stale | Not reviewed in over 120 days |

Stale records must be reviewed and either reaffirmed, revised, or retired. Tier-5 records that pass their target retirement date must be retired or explicitly renewed with justification.

### 12. Ownership

The SRE Team holds sole decision authority. External contributors are advisory. Ownership model should be revisited when team capacity changes.

## Alternatives Considered

1. **No formal governance — rely on code review and convention:**
   - Pros: Zero overhead.
   - Cons: Decisions are implicit, inconsistent, and untraceable. Rationale is lost when contributors change.
   - Why not chosen: Unacceptable for GC accountability requirements and a growing codebase.

2. **Lightweight ADRs without tiers or metadata (plain Nygard/MADR-style):**
   - Pros: Simple, widely understood format. MADR 4.0 is broadly adopted with minimal overhead.
   - Cons: No authority hierarchy means no way to determine which decision wins when two conflict. No freshness tracking means records go stale silently.
   - Why not chosen: The modular monolith architecture requires explicit layered authority — principles must visibly constrain standards, which constrain feature decisions. However, MADR's record structure and minimal metadata approach directly influenced this governance model.

3. **Wiki-based documentation instead of in-repo records:**
   - Pros: Easier browsing, richer formatting.
   - Cons: Disconnected from code review, no version control, easy to edit without traceability.
   - Why not chosen: Decisions must travel with the code they govern and go through the same review process.

## Consequences

- **Positive**: Every architectural decision has a single authoritative source with traceable rationale, explicit authority level, and freshness tracking. Conflicts between decisions are resolvable by tier.
- **Tradeoffs**: Metadata overhead per record. Authors must classify tier and type correctly before writing.
- **Risks**: Single-owner governance can bottleneck decision throughput. Over-classification may slow down simple decisions.
- **Mitigations**: Keep the process proportional — Tier-4/5 records are intentionally lightweight. Revisit ownership when team grows.

## Source References

1. Documenting Architecture Decisions (Michael Nygard)
   - URL: <https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions>
   - Publisher: Cognitect
   - Accessed: 2026-05-01
   - Relevance: Establishes the ADR format and rationale for recording architectural decisions as lightweight, immutable records alongside code.

2. Architecture Decision Records (Joel Parker Henderson — collection)
   - URL: <https://github.com/joelparkerhenderson/architecture-decision-record>
   - Publisher: Community
   - Accessed: 2026-04-29
   - Relevance: Comprehensive survey of ADR templates, tooling, and governance patterns used across industry.

3. Design Decisions and Design Decision Making (Keeling)
   - URL: <https://www.georgefairbanks.com/ieee-software-v27-n2-mar-2010-just-enough/>
   - Publisher: IEEE Software
   - Accessed: 2026-04-30
   - Relevance: Provides the theoretical basis for decision classification, authority levels, and the relationship between architectural decisions and their constraints.

4. Government of Canada Digital Standards
   - URL: <https://www.canada.ca/en/government/system/digital-government/government-canada-digital-standards.html>
   - Publisher: Government of Canada
   - Accessed: 2026-05-01
   - Relevance: Establishes GC requirements for defensible technology decisions, security by design, accessibility, and official language support that this governance framework must satisfy.

5. Markdown Any Decision Records (MADR) 4.0 Template
   - URL: <https://github.com/adr/madr/blob/4.0.0/template/adr-template.md>
   - Publisher: adr.github.io community
   - Accessed: 2026-05-02
   - Relevance: Widely adopted lightweight ADR template. Informed the record structure (decision drivers, considered options, decision outcome, confirmation) and the minimal metadata contract.

6. A Definition of Ready for Architectural Decisions (Ozimmer)
   - URL: <https://ozimmer.ch/practices/2023/12/01/ADDefinitionOfReady.html>
   - Publisher: Olaf Zimmermann
   - Accessed: 2026-05-03
   - Relevance: START framework for decision readiness. Establishes that decisions should not be recorded prematurely — stakeholders, timing, alternatives, requirements, and template must be in place.

## Change Log

- 2026-05-08: Created. Fresh governance baseline for the decision record corpus.
