# Decision Record Metadata Reference

Authoritative field definitions and allowed values for all decision records.
Governed by [decision-record-governance.md](../decision-record-governance.md).

---

## Identity

Records are identified by their kebab-case filename (e.g., `stateless-processes.md`).
There is no numeric ID sequence. Cross-references between records use filenames.

---

## Metadata Fields

### Required (every record)

| Field | YAML Type | Allowed Values |
|-------|-----------|----------------|
| `title` | string | Short, decision-focused phrase |
| `status` | enum | `Draft`, `Proposed`, `Accepted`, `Superseded`, `Deprecated`, `Rejected` |
| `type` | enum | `Governance`, `Principle`, `Standard`, `Selection`, `Deprecation` |
| `tier` | enum | `Tier-0`, `Tier-1`, `Tier-2`, `Tier-3` |
| `date` | ISO 8601 | Date of last update (`YYYY-MM-DD`) |
| `decision_makers` | list | One or more team or person names |

### Conditional (Tier-1 and below)

| Field | When Required | YAML Type | Allowed Values |
|-------|---------------|-----------|----------------|
| `governance_domain` | Tier-1+ | list | One or both of: `application`, `operations` |
| `concerns` | Tier-1+ | list | One or more tags from the Concern Tags list |
| `constrained_by` | When governed by higher-tier records | list | Filenames |
| `supersedes` | When replacing another record | list | Filenames |
| `superseded_by` | When replaced by another record | list | Filenames |
| `retirement_date` | Deprecation type only | ISO 8601 | Target retirement date (`YYYY-MM-DD`) |

### Optional

| Field | Purpose |
|-------|--------|
| `consulted` | People whose expertise was sought (two-way communication) |
| `informed` | People kept up-to-date (one-way communication) |

**Bidirectionality:** `constrained_by` and `supersedes`/`superseded_by` must be maintained
bidirectionally. If record A declares `supersedes: [b.md]`, then `b.md` must declare
`superseded_by: [a.md]`.

---

## Governance Domains

Applies to Tier-1 and below only. Tier-0 records omit this field.
The field is always a list, even when single-valued.

| Value | Governs | Boundary test | Files |
|-------|---------|---------------|-------|
| `application` | The software artifact and all practices to produce it correctly | "Would this decision travel with the code if handed to a different ops team?" | `app/`, `pytest.ini`, `mypy.ini`, `.flake8`, coding standards |
| `operations` | Running the artifact in environments and the delivery pipeline | "Does this decision stay with the infrastructure, not the code?" | `terraform/`, `.github/workflows/`, `Dockerfile`, cloud services |

Cross-cutting decisions declare both: `governance_domain: [application, operations]`

---

## Decision Types

Each record uses exactly one type. Types are **independent of tiers** — any type may
appear at any tier, though natural affinities exist.

| Type | What it captures | Typical tier |
|------|------------------|--------------|
| `Governance` | How decisions are written, reviewed, and superseded | Tier-0 |
| `Principle` | Fundamental constraint from methodology or values. "We believe X, therefore Y." | Tier-1 |
| `Standard` | Prescriptive implementation rule. "When you do X, do it this way." | Tier-2 |
| `Selection` | Deliberate choice of tool, platform, or approach over alternatives | Any |
| `Deprecation` | Retirement plan with explicit timeline. Requires `retirement_date`. | Any |

---

## Tier Definitions

| Tier | Name | Placement Question | Blast Radius |
|------|------|--------------------|--------------|
| Tier-0 | Governance | Is this about how we write and manage decisions? | All decisions in the repository |
| Tier-1 | Foundational | Would reversing this require rearchitecting the domain? | Entire governance domain |
| Tier-2 | Cross-cutting | Does this affect multiple components/features? | Multiple components within a domain |
| Tier-3 | Scoped | One feature, one integration, or one time window? | One component or temporary concern |

### Placement Algorithm

Sequential — first YES wins:

1. About decision-making itself? → **Tier-0**
2. Reversal = rewrite the domain? → **Tier-1**
3. Affects multiple components? → **Tier-2**
4. Everything else → **Tier-3**

---

## Concern Tags

Use one or more tags for discovery and indexing. Tags are informational — they do not
determine authority (that's tiers) or scope (that's domains).

### Application concerns

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

### Operations concerns

| Tag | Covers |
|-----|--------|
| `compute` | Containers, ECS, scaling, local dev runtime |
| `networking` | ALB, VPC, DNS, service discovery |
| `cicd` | Pipeline structure, deployment automation |
| `secrets-management` | Secrets provisioning, rotation, injection |
| `monitoring` | CloudWatch, alerting, dashboards |
| `cost` | Resource sizing, reserved capacity |
| `compliance` | WAF, access logs, audit trails |

### Shared (either domain)

| Tag | Covers |
|-----|--------|
| `security` | Spans both — app-level auth AND infra-level WAF/IAM |
| `observability` | Spans both — structured logging AND monitoring infra |
| `configuration` | Spans both — app settings consumption AND secrets injection |

---

## Freshness Policy

| State | Condition |
|-------|-----------|
| `current` | Reviewed within the past 120 days |
| `expiring-soon` | Next review due within the next 30 days |
| `stale` | Not reviewed in over 120 days |

Stale records must be reviewed and either reaffirmed, revised, or retired. Deprecation
records that pass their `retirement_date` must be retired or explicitly renewed with
justification.

---

## Supersession Rules

- Replacement records list the replaced filename(s) in `supersedes`.
- Replaced records set `status: Superseded` and list the replacement filename(s) in `superseded_by`.
- Links are bidirectional and mandatory — a one-sided link is non-compliant.
