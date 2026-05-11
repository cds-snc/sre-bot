---
title: "Decision Record Governance"
status: Accepted
type: Governance
tier: Tier-0
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Decision Record Governance

## Context and Problem Statement

Architectural knowledge decays when decisions are undocumented, scattered, or ambiguous. Without a governance framework, teams make conflicting choices, duplicate effort, and lose the rationale behind existing design. A single small team needs a lightweight but enforceable system for recording, classifying, and maintaining architectural decisions.

- A single team owns all architectural authority; the process must be low-overhead for one or two contributors while remaining scalable if the team grows.
- Decisions span two distinct governance domains — the software artifact and the operational environment — that evolve at different rates and are owned by the same DevOps team.
- GC policy requires defensible rationale for technology choices, especially around security, accessibility, official languages, and cloud portability.
- The codebase follows a modular monolith pattern where decisions at one layer constrain behavior at lower layers — this hierarchy must be explicit and traceable.

**Constraints:**

- Flat directory structure under `docs/adr/` for tooling compatibility.
- All decisions must cite authoritative sources (official documentation, established methodologies) — not prior implementations.

**Non-goals:**

- This record does not define application architecture, standards, or patterns — those are downstream decisions constrained by this one.
- This record does not prescribe tooling for automation, linting, or CI enforcement of decision records.

## Considered Options

- No formal governance — rely on code review and convention
- Lightweight ADRs without tiers or metadata (plain Nygard/MADR-style)
- Wiki-based documentation instead of in-repo records

## Decision Outcome

Chosen option: **Tiered governance with two domains and orthogonal classification axes**, because it provides explicit conflict resolution through tiers, clear domain ownership boundaries, and lightweight metadata that enables automated indexing — while remaining proportional to a small team's capacity.

---

### 1. One decision, one record, one authority level

Each decision record addresses exactly one problem. If a record needs to prescribe rules at multiple authority levels, it must be split.

### 2. Tiered authority model

Decisions are classified by blast radius. Higher-tier decisions constrain lower-tier decisions through explicit metadata links.

| Tier | Name | Placement Question | Blast Radius |
|------|------|--------------------|--------------|
| Tier-0 | Governance | Is this about how we write and manage decisions? | All decisions in the repository |
| Tier-1 | Foundational | Would reversing this require rearchitecting the domain? | Entire governance domain |
| Tier-2 | Cross-cutting | Does this affect how multiple components/features are built or operated? | Multiple components within a domain |
| Tier-3 | Scoped | Is this limited to one feature, one integration, or one time window? | One component or temporary concern |

**Placement algorithm (sequential, first YES wins):**

1. About decision-making itself? → **Tier-0**
2. Reversal = rewrite the domain? → **Tier-1**
3. Affects multiple components? → **Tier-2**
4. Everything else → **Tier-3**

### 3. Decision types

Five types. Types are independent of tiers — any type may appear at any tier, though natural affinities exist.

| Type | What it captures | Typical tier |
|------|------------------|--------------|
| `Governance` | How decisions are written, reviewed, and superseded | Tier-0 |
| `Principle` | A fundamental constraint derived from methodology or values. "We believe X, therefore Y is always true." | Tier-1 |
| `Standard` | A prescriptive implementation rule. "When you do X, do it this way." | Tier-2 |
| `Selection` | A deliberate choice of tool, platform, or approach over alternatives. "We chose X over Y because Z." | Any |
| `Deprecation` | A retirement plan. "X is being replaced by Y on this timeline." Requires `retirement_date`. | Any |

### 4. Two governance domains

Records at Tier-1 and below must declare one or more governance domains.

| Domain | Governs | Boundary test | Files |
|--------|---------|---------------|-------|
| `application` | The software artifact and all practices to produce it correctly | "If we handed this app to a different ops team, would this decision travel with the code?" | `app/`, `pytest.ini`, `mypy.ini`, `.flake8`, coding standards, security scanning tool choices, devcontainer |
| `operations` | Running the artifact in environments and the delivery pipeline | "Does this decision stay with the infrastructure, not the code?" | `terraform/`, `.github/workflows/`, `Dockerfile`, `docker-compose.yml`, cloud services, deployment strategy |

**Rules:**

- Tier-0 records omit `governance_domain` — they govern the decision process itself.
- Most records declare a single domain: `governance_domain: [application]`
- Cross-cutting records may declare both: `governance_domain: [application, operations]`
- The field is always a list for consistency, even when single-valued.

### 5. Concern tags

Each record declares one or more concern tags for discovery and indexing. Tags are informational — they do not determine authority (that's tiers) or scope (that's domains).

**Application concerns:**

| Tag | Covers |
|-----|--------|
| `architecture` | Layer rules, flow direction, statelessness, boundaries |
| `plugins` | Discovery, registration, hooks, feature isolation |
| `configuration` | Settings, env vars, secrets consumption |
| `api` | Routes, error mapping, transport, HTTP contracts |
| `security` | Auth, identity, rate limiting, scanning |
| `data` | Persistence, caching, state delegation |
| `lifecycle` | Startup, shutdown, background jobs |
| `testing` | Strategy, structure, fixtures, coverage |
| `quality-gates` | Linting, type checking, formatting |

**Operations concerns:**

| Tag | Covers |
|-----|--------|
| `compute` | Containers, ECS, scaling, local dev runtime |
| `networking` | ALB, VPC, DNS, service discovery |
| `cicd` | Pipeline structure, deployment automation |
| `secrets-management` | Secrets provisioning, rotation, injection |
| `monitoring` | CloudWatch, alerting, dashboards |
| `cost` | Resource sizing, reserved capacity |
| `compliance` | WAF, access logs, audit trails |

**Shared (either domain may use):**

`security`, `observability`, `configuration`

### 6. Record naming and identity

Each record is identified by its kebab-case filename (e.g., `decision-record-governance.md`). There is no numeric ID sequence. Cross-references between records use filenames.

### 7. Record structure

Every decision record must contain:

1. **Context and Problem Statement**: What is the problem? What forces or concerns drive this decision? What are the constraints and non-goals?
2. **Considered Options**: At least two alternatives.
3. **Decision Outcome**: Which option was chosen and why. What rules or principles does it establish?
4. **Consequences**: Positive impacts, accepted tradeoffs, risks, mitigations.
5. **Confirmation** *(optional)*: How compliance with this decision will be verified (e.g., code review checklist, automated check, test).
6. **Source References**: Authoritative external sources. Each must include title, URL, and a one-line relevance summary.
7. **Change Log**: Dated entries for all modifications.

### 8. Metadata contract

Every record must declare these fields in its YAML frontmatter:

**Required (every record):**

| Field | Purpose |
|-------|--------|
| `title` | Short, decision-focused phrase |
| `status` | `Draft`, `Proposed`, `Accepted`, `Superseded`, `Deprecated`, `Rejected` |
| `type` | One of: `Governance`, `Principle`, `Standard`, `Selection`, `Deprecation` |
| `tier` | `Tier-0` through `Tier-3` |
| `date` | ISO 8601 date of last update |
| `decision_makers` | People who made or own this decision |

**Conditional (Tier-1 and below):**

| Field | When Required |
|-------|--------|
| `governance_domain` | Tier-1+; list of `application`, `operations`, or both |
| `concerns` | Tier-1+; list of tags from the curated set |
| `constrained_by` | When higher-tier records govern this one; list filenames |
| `supersedes` | When this record replaces another; list filenames |
| `superseded_by` | When this record has been replaced; list filenames |
| `retirement_date` | Deprecation type only; ISO 8601 target date |

**Optional:**

| Field | Purpose |
|-------|--------|
| `consulted` | People whose expertise was sought (two-way communication) |
| `informed` | People kept up-to-date (one-way communication) |

`constrained_by` and `supersedes`/`superseded_by` links must be maintained bidirectionally.

### 9. Supersession rules

- Replacement records list the replaced filename(s) in `supersedes`.
- Replaced records set `status: Superseded` and list the replacement filename(s) in `superseded_by`.
- Links are bidirectional and mandatory.

### 10. Decision readiness

A decision should not be recorded until its readiness criteria are met (adapted from Zimmermann's START framework):

1. **Stakeholders** — Decision makers and affected parties are identified.
2. **Timing** — The most responsible moment has arrived; deferring further would increase risk.
3. **Alternatives** — At least two options are understood with their tradeoffs.
4. **Requirements** — The problem, constraints, and decision drivers are clear.
5. **Template** — The record structure is agreed upon and ready to use.

### 11. Freshness policy

| State | Condition |
|-------|-----------|
| `current` | Reviewed within the past 120 days |
| `expiring-soon` | Next review due within 30 days |
| `stale` | Not reviewed in over 120 days |

Stale records must be reviewed and either reaffirmed, revised, or retired. Deprecation records that pass their `retirement_date` must be retired or explicitly renewed with justification.

### 12. Ownership

The SRE Team holds sole decision authority. External contributors are advisory. Ownership model should be revisited when team capacity changes.

---

## Pros and Cons of the Options

### No formal governance — rely on code review and convention

- Good, because zero overhead.
- Bad, because decisions are implicit, inconsistent, and untraceable.
- Bad, because rationale is lost when contributors change.

### Lightweight ADRs without tiers or metadata (plain Nygard/MADR-style)

- Good, because simple and widely understood format.
- Good, because MADR 4.0 is broadly adopted with minimal overhead.
- Bad, because no authority hierarchy means no way to determine which decision wins when two conflict.
- Bad, because no freshness tracking means records go stale silently.

### Wiki-based documentation instead of in-repo records

- Good, because easier browsing and richer formatting.
- Bad, because disconnected from code review and version control.
- Bad, because easy to edit without traceability.

## Consequences

- Good, because every architectural decision has a single authoritative source with traceable rationale, explicit authority level, and freshness tracking.
- Good, because conflicts between decisions are resolvable by tier.
- Good, because the two-domain model maps cleanly to the DevOps boundary: what we build vs. how we run it.
- Bad, because metadata overhead per record — authors must classify tier and type.
- Bad, because single-owner governance can bottleneck decision throughput.
- Mitigation: keep the process proportional — Tier-3 records are intentionally lightweight. Revisit ownership when team grows.

### Confirmation

Compliance with this governance model will be verified by:

- The index generation script (`generate_adr_indexes.py`) which validates frontmatter fields.
- Code review of all new ADRs against this record's metadata contract.

## Source References

1. Documenting Architecture Decisions (Michael Nygard)
   - URL: <https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions>
   - Accessed: 2026-05-01
   - Relevance: Establishes the ADR format and rationale for recording architectural decisions as lightweight, immutable records alongside code.

2. Architecture Decision Records (Joel Parker Henderson — collection)
   - URL: <https://github.com/joelparkerhenderson/architecture-decision-record>
   - Accessed: 2026-04-29
   - Relevance: Comprehensive survey of ADR templates, tooling, and governance patterns used across industry.

3. Design Decisions and Design Decision Making (Keeling)
   - URL: <https://www.georgefairbanks.com/ieee-software-v27-n2-mar-2010-just-enough/>
   - Accessed: 2026-04-30
   - Relevance: Provides the theoretical basis for decision classification, authority levels, and the relationship between architectural decisions and their constraints.

4. Government of Canada Digital Standards
   - URL: <https://www.canada.ca/en/government/system/digital-government/government-canada-digital-standards.html>
   - Accessed: 2026-05-01
   - Relevance: Establishes GC requirements for defensible technology decisions, security by design, accessibility, and official language support that this governance framework must satisfy.

5. Markdown Any Decision Records (MADR) 4.0 Template
   - URL: <https://github.com/adr/madr/blob/4.0.0/template/adr-template.md>
   - Accessed: 2026-05-02
   - Relevance: Widely adopted lightweight ADR template. Informed the record structure (decision drivers, considered options, decision outcome, confirmation) and the minimal metadata contract.

6. A Definition of Ready for Architectural Decisions (Zimmermann)
   - URL: <https://ozimmer.ch/practices/2023/12/01/ADDefinitionOfReady.html>
   - Accessed: 2026-05-03
   - Relevance: START framework for decision readiness. Establishes that decisions should not be recorded prematurely — stakeholders, timing, alternatives, requirements, and template must be in place.

## Change Log

- 2026-05-08: Created. Fresh governance baseline with two-domain, four-tier, five-type model.
