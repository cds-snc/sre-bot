# ADR Program — Document Index

**Purpose:** Entry point for the ADR refactoring program. Four decoupled documents, each single-purpose.

---

## Active Documents

| Document | Purpose | Update Frequency |
|----------|---------|------------------|
| [Authoring Workflow](references/adr-authoring-workflow.md) | Reference procedure for draft → review → accept lifecycle | Stable (update only when process changes) |
| [Migration Map](adr-migration-map.md) | Registry of legacy → canonical ADR mappings and supersession | Update when ADRs are allocated, accepted, or superseded |
| [Wave Tracker](adr-wave-tracker.md) | Current wave progress and pending actions | Update each work cycle |
| [Change Log](adr-change-log.md) | Append-only audit trail of all program actions | Append after each action |

## Supporting Artifacts

| Location | Contents |
|----------|----------|
| `adr/` | Active ADR files |
| `adr/superseded/` | Legacy ADRs with `status: Superseded` |
| `reviews/` | Challenge review artifacts |
| `analysis/` | Supporting decision assessments and architectural analyses |
| `templates/` | ADR metadata template and challenge review template |
| `references/` | Reference materials, reusable methodologies, and architectural frameworks |

### Reference Documents

| Document | Purpose |
|----------|---------|
| [Authoring Workflow](references/adr-authoring-workflow.md) | ADR authoring, review, and acceptance procedure |
| [HV Review Methodology](references/adr-horizontal-vertical-review-methodology.md) | Cross-ADR consistency review process |
| [Delegation Framework](references/managed-services-delegation-framework.md) | Three-tier managed service delegation hierarchy (ADR-0045 P7) |
| [Tier-3 Gap Analysis](references/tier3-domain-gap-analysis.md) | Domain contract coverage gaps — Wave 7 prerequisite |
| [Mental Model Reconciliation](references/architecture-mental-model-reconciliation.md) | Backstage vs Python/FastAPI architecture root cause (ADR-0076) |
| [Product Purpose](references/product-purpose.md) | Product context and mission |
| [Runtime and Tech Stack](references/runtime-and-tech-stack.md) | Technology stack reference |

### Analysis Documents

| Document | Purpose |
|----------|---------|
| [Platform Services Assessment](analysis/platform-services-assessment.md) | InteractionProvider Protocol rejection rationale (ADR-0078) |
| [Interaction Provider Analysis](analysis/interaction-provider-abstraction-analysis.md) | Unified abstraction risk assessment (ADR-0059) |
| [Legacy Module Coupling](analysis/legacy-module-coupling-assessment.md) | Module coupling profiles and migration sequencing |
| [Infrastructure Decentralization](analysis/infrastructure-decentralization-inventory.md) | Settings/provider current-state audit (ADR-0055, ADR-0056) |
| [Delegation Assessment](analysis/managed-services-delegation-assessment.md) | Build-vs-delegate codebase audit and migration roadmap |

## Historical Context

The ADR program produced several supporting analyses during authoring. Key conclusions from these analyses have been incorporated into the relevant ADR files, the change log, and the tracking documents listed above. The analyses covered:

| Topic | Incorporated Into |
|-------|-------------------|
| Program planning and step-by-step execution | Wave Tracker + Change Log |
| Legacy ADR migration mapping and constraint chains | Migration Map + Change Log |
| Infrastructure composition governance (ADR-0048 B5 scoping) | ADR-0045, ADR-0048 |
| Settings dissolution technical inventory | ADR-0055, ADR-0056 |
| Platform services architecture (InteractionProvider Protocol rejection) | ADR-0059, ADR-0078 |
| Legacy feature coupling analysis for Tier-5 sequencing | ADR-0072 through ADR-0075 |
| Cross-ADR consistency review (HV review: 337 comparisons, 17 findings) | Wave Tracker + Migration Map |
| Tier-3 domain contract gap analysis | Wave Tracker (Wave 7 prerequisite) + Migration Map (Cross-Cutting ADR Gaps) |
| Redundancy consolidation across ADR files | Applied directly to 7 ADR files |
