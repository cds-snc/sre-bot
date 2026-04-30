# ADR Program — Document Index

**Purpose:** Entry point for the ADR refactoring program. Four decoupled documents, each single-purpose.

---

## Active Documents

| Document | Purpose | Update Frequency |
|----------|---------|------------------|
| [Authoring Workflow](adr-authoring-workflow.md) | Reference procedure for draft → review → accept lifecycle | Stable (update only when process changes) |
| [Migration Map](adr-migration-map.md) | Registry of legacy → canonical ADR mappings and supersession | Update when ADRs are allocated, accepted, or superseded |
| [Wave Tracker](adr-wave-tracker.md) | Current wave progress and pending actions | Update each work cycle |
| [Change Log](adr-change-log.md) | Append-only audit trail of all program actions | Append after each action |

## Supporting Artifacts

| Location | Contents |
|----------|----------|
| `adr/` | Active ADR files |
| `adr/superseded/` | Legacy ADRs with `status: Superseded` |
| `reviews/` | Challenge review artifacts |
| `templates/` | ADR metadata template |
| `references/` | Reference materials |

## Archived Planning Documents

The following `tmp/` files contain historical analysis and planning context from the program's early phases. They are retained as reference but are **not actively maintained**:

| File | Role | Superseded By |
|------|------|---------------|
| `tmp/adr-exhaustive-review-working-notes-2026-04-28.md` | Original step-by-step planning (Steps 1–11) | Wave Tracker + Change Log |
| `tmp/adr-program-implementation-plan-v2-2026-04-29.md` | Consolidated action tracker with detailed scope notes | Wave Tracker + Change Log |
| `tmp/canonical-adr-migration-map-and-legacy-reconciliation-2026-04-28.md` | Detailed migration map with scope notes and constraint chains | Migration Map (lean) + Change Log (audit) |
| `tmp/backstage-mental-model-reconciliation-2026-04-29.md` | Root cause analysis (ADR-0048 B5 misapplication) | Referenced by ADR-0045, ADR-0048 inline |
| `tmp/infrastructure-configuration-and-services-decentralization-analysis-2026-04-28.md` | Technical inventory for settings dissolution | Referenced by ADR-0055, ADR-0056 inline |
| `tmp/platform-services-assessment-2026-04-29.md` | InteractionProvider Protocol rejection analysis | Referenced by ADR-0059, ADR-0078 inline |
| `tmp/interaction-provider-abstraction-analysis-2026-04-29.md` | Analysis input for platform services decision | Consumed by platform-services-assessment |
| `tmp/legacy-feature-rearchitecting-assessment-2026-04-29.md` | Coupling analysis for Tier-5 ADR sequencing | Referenced by ADR-0072 through ADR-0075 inline |
| `tmp/adr-horizontal-vertical-review-methodology-2026-04-30.md` | Cross-ADR consistency review (337 comparisons, 17 findings). Master methodology with §8 findings, §9 dashboard, §10 cross-reference map | Wave Tracker + Migration Map (gaps tracked there) |
| `tmp/adr-redundancy-restructuring-proposal-2026-04-30.md` | Redundancy analysis and consolidation proposal for 6 accepted-as-is HV findings | All 5 actionable proposals applied to ADR files |
| `tmp/hv-review-tier3-gap-analysis-2026-04-30.md` | Tier-3 domain contract gap analysis (finding V-017) | Wave Tracker (Wave 7 prerequisite) + Migration Map (Cross-Cutting ADR Gaps) |
