# ADR Metadata Reference

Authoritative field definitions, allowed values, and enforcement rules for all ADRs.
Governed by [ADR-0044](../adr/0044-adr-governance-operating-model.md).

All 18 fields are mandatory in every ADR. List fields with no current entries must use
an empty array `[]`, not be omitted.

---

## Field Definitions

- **`adr_id`**: canonical global ID, zero-padded four-digit sequence (`ADR-0001`, `ADR-0002`, …).
- **`title`**: short, decision-focused phrase in title case (quoted string).
- **`status`**: one of `Draft | Proposed | Accepted | Superseded | Deprecated | Rejected`.
  If `Superseded`, `superseded_by` must contain at least one ADR ID.
- **`decision_type`**: exactly one value from the catalog below (see Tier Compatibility table).
- **`tier`**: exactly one of `Tier-0 | Tier-1 | Tier-2 | Tier-3 | Tier-4 | Tier-5`.
- **`primary_domain`**: exactly one domain from the canonical list below.
- **`secondary_domains`**: zero or more domains from the same canonical list.
- **`owners`**: one or more responsible team names. SRE Team is the current sole authority.
- **`date_created`**: ISO 8601 date the record was first created (`YYYY-MM-DD`).
- **`last_updated`**: ISO 8601 date of the most recent content change.
- **`last_reviewed`**: ISO 8601 date of the most recent formal review.
- **`next_review_due`**: ISO 8601 date; always `last_reviewed` + 120 days.
- **`constrained_by`**: array of ADR IDs that govern this record. Every non-Tier-0 record
  must include `ADR-0044`. Add any higher-tier records that directly constrain this one.
- **`impacts`**: array of ADR IDs this record constrains, or that require updates when
  this record changes.
- **`supersedes`**: array of ADR IDs this record replaces. Must be paired bidirectionally:
  the replaced record must list this record in `superseded_by`.
- **`superseded_by`**: array of ADR IDs that have replaced this record. Populated only on
  superseded records.
- **`review_state`**: one of `current | expiring-soon | stale` (see Freshness Policy).
- **`related_records`**: array of ADR IDs that are informatively related but not constraining.
- **`related_packages`**: array of package paths (e.g., `app/packages/access`) directly
  affected by this decision.

---

## Decision-Type Catalog

Use exactly one value per ADR.

| Value               | Description                                                           |
|---------------------|-----------------------------------------------------------------------|
| `Governance Policy` | How decisions are authored, reviewed, and superseded. Tier-0 only.   |
| `Principle`         | Long-lived architectural rule with high change cost. Tier-1.         |
| `Standard`          | Mandatory implementation convention under a principle. Tier-2.       |
| `Pattern`           | Reusable implementation strategy with applicability conditions. Tier-2. |
| `Domain Contract`   | Stable domain boundary contract and invariants. Tier-3.              |
| `Domain Standard`   | Domain-specific mandatory conventions. Tier-3.                       |
| `Feature Decision`  | Feature-local behavior, mapping, or interface design. Tier-4.        |
| `Integration Decision` | External system interaction contract and failure semantics. Tier-4. |
| `Migration Decision`   | Temporary transition path with explicit checkpoints. Tier-5.      |
| `Deprecation Decision` | Retirement policy for legacy architecture or modules. Tier-5.     |

---

## Tier Definitions

| Tier   | Purpose                              | Blast radius                                |
|--------|--------------------------------------|---------------------------------------------|
| Tier-0 | Governance and Operating Model       | Entire repository                           |
| Tier-1 | Platform Principles                  | `app/infrastructure`, `app/server`, `app/packages` |
| Tier-2 | Platform Standards and Patterns      | Multiple packages and shared platform code  |
| Tier-3 | Domain Architecture                  | One domain and its integration boundaries   |
| Tier-4 | Feature and Integration Decisions    | One feature or one integration path         |
| Tier-5 | Time-Bound Migration Decisions       | Temporary cross-tier bridge                 |

Tier-5 records must include explicit retirement criteria and a target retirement date.

---

## Tier and Decision-Type Compatibility

A record's `tier` and `decision_type` must agree. Mixing is non-compliant.

| Tier   | Allowed `decision_type` values                         |
|--------|--------------------------------------------------------|
| Tier-0 | `Governance Policy`                                    |
| Tier-1 | `Principle`                                            |
| Tier-2 | `Standard`, `Pattern`                                  |
| Tier-3 | `Domain Contract`, `Domain Standard`                   |
| Tier-4 | `Feature Decision`, `Integration Decision`             |
| Tier-5 | `Migration Decision`, `Deprecation Decision`           |

A Tier-1 ADR must not contain Tier-4 implementation specifics. Split into separate records
if needed — one decision, one authority level (ADR-0044 §Classification Rules).

---

## Primary Domain Canonical List

Use exactly one value for `primary_domain`; any subset for `secondary_domains`.

- `Runtime and Lifecycle`
- `Configuration and Secrets`
- `Dependency and Composition`
- `Package and Plugin Architecture`
- `Transport and API`
- `Data and Persistence`
- `Security and Access Control`
- `Observability and Operations`
- `Delivery and Environment Parity`
- `Testing and Quality Gates`
- `Governance and Operating Model`

---

## Freshness Policy

| State           | Condition                                              |
|-----------------|--------------------------------------------------------|
| `current`       | `last_reviewed` within the past 120 days               |
| `expiring-soon` | `next_review_due` within the next 30 days              |
| `stale`         | `last_reviewed` more than 120 days ago                 |

`review_state` is set explicitly by the author/reviewer — it is not computed automatically
during manual authoring. Always recalculate against today's date when updating a record.

---

## Supersession Rules

- Replacement records declare the replaced ID in `supersedes`.
- Replaced records declare the replacement ID in `superseded_by` and set `status: Superseded`.
- Links are bidirectional and mandatory — a one-sided supersession link is non-compliant.
- Time-bound coexistence windows must be captured in a Tier-5 record, not left implicit.
