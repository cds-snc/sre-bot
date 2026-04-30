# Legacy Module Coupling Assessment

**Date:** 2026-04-29  
**Related ADRs:** ADR-0055, ADR-0070–0075  
**Purpose:** Coupling inventory and execution sequencing for legacy module migration

---

## Key Insight

The Tier-5 settings ADRs (ADR-0070–0075) govern *where configuration lives*. They do not govern how features are structured or consume third-party services. Several legacy modules have deep coupling that makes settings migration a leaf operation — the smallest part of a larger rearchitecting problem.

---

## 1. Access Package Supersession

The access package (`app/packages/access/`) actively supersedes capabilities from multiple legacy modules:

| Capability | Access Package | Legacy Module(s) | Status |
|------------|---------------|-------------------|--------|
| AWS Identity Center group sync | `sync/adapters/aws_identity_center.py` | `modules/aws/groups.py`, `modules/provisioning/groups.py` | Superseded |
| Google Workspace group reads | `sync/` (IDP source of truth) | `modules/provisioning/groups.py`, `modules/groups/providers/` | Superseded |
| User provisioning | `request/` (approval → IDP write → sync) | `modules/provisioning/users.py` | Superseded |
| Scheduled reconciliation | `sync/job_runner.py` | `modules/groups/` | Superseded |
| Multi-provider group management | `sync/adapters/` (adapter pattern) | `modules/groups/providers/` (registry pattern) | Superseded |
| Access request lifecycle | `request/` | None | New capability |
| Entitlement catalog | `catalog/` | None | New capability |

---

## 2. Module Coupling Profiles

### Critical Coupling (requires full rearchitecting)

#### `app/modules/incident/` — 16 files

- **Slack SDK:** 9 files with direct `slack_sdk.WebClient` imports
- **Google APIs:** 7 files with direct Drive/Docs/Sheets calls
- **DynamoDB:** 2 files with direct `boto3` calls
- **Settings:** All use `core.config.settings` (legacy singleton), none use `infrastructure.services`
- **Infrastructure abstractions used:** Zero
- **Reverse coupling:** Zero `app/infrastructure/` files import from incident

**Isolation verdict:** Fully decoupled from infrastructure settings chain. Settings dissolution (ADR-0055) can execute without touching incident. The `core.config.Settings` legacy singleton remains stable as a compatibility shim.

**Rearchitecting scope (deferred to Phase 3):** Extract service boundaries, replace direct SDK calls with infrastructure abstractions, migrate to proper settings providers, fix module-level settings loading, introduce repository pattern.

#### `app/modules/aws/` — 10 files

- **Slack SDK:** 5 files
- **AWS boto3:** Direct import in `identity_center.py`
- **Cross-module:** Imports `modules.provisioning` (circular dependency chain: aws → provisioning → google workspace)
- **Supersession:** Group sync and user creation fully superseded by access package. Remaining scope TBD.

**ADR-0073 gap:** Assumes migration to `packages/aws_ops`, but group sync and identity components are superseded. `AWSFeatureSettings` fields may have no consumer post-access-package.

#### `app/modules/webhooks/` — 19 files across 3 directories

Multi-domain mashup spanning `modules/webhooks/`, `modules/slack/webhooks*.py`, `modules/sre/webhook_helper.py`, and `api/v1/routes/webhooks.py`. Slack is hardcoded as the sole output channel. No dedicated settings class exists — borrows `PREFIX`, `is_production`, `NOTIFY_OPS_CHANNEL_ID` from parent settings.

**No Tier-5 settings ADR required.** Settings migration handled as part of parent domain dissolution.

### Moderate Coupling

#### `app/modules/groups/` — 39 files

Well-architected relative to other legacy modules (uses `OperationResult`, circuit breakers, infrastructure abstractions). Fully deprecated — replaced by access package. ADR-0070 correctly records as retirement.

### Light Coupling

| Module | Files | Assessment |
|--------|-------|-----------|
| `app/modules/atip/` | 1 | ADR-0074 correctly scoped. Minimal rearchitecting. |
| `app/modules/sre/` | 3 | ADR-0075 correctly scoped. Already uses infrastructure abstractions. Closest to production-ready among legacy modules. |
| `app/modules/ops/` | 1 | Trivial to fix. One import-time side effect. |

---

## 3. Cross-Cutting: Provisioning Module

`app/modules/provisioning/` is a critical dependency blocking multiple retirements. The access package's sync and request subsystems fully replace it. Must be retired before or simultaneously with AWS and groups modules.

---

## 4. Settings Chain Decoupling

Two parallel settings chains coexist without interference:

| Chain | Entry Point | Consumers |
|-------|------------|-----------|
| **Legacy** | `from core.config import settings` | incident, webhooks, ops, slack modules |
| **Infrastructure** | `from infrastructure.services import get_settings` | groups, sre, packages/access, infrastructure |

The infrastructure chain can be fully restructured (settings dissolution) without impacting the legacy chain.

---

## 5. Phased Execution

| Phase | Scope | Settings ADRs | Constraint |
|-------|-------|--------------|------------|
| **A** | Settings dissolution + independent migrations | ADR-0074 (ATIP), ADR-0075 (SRE ops) | `core.config.Settings` remains stable |
| **B** | Retirements contingent on access maturity | ADR-0070 (Groups), ADR-0071 (Commands) | Access package at parity |
| **C** | Feature-level rearchitecting | ADR-0072 (Incident), ADR-0073 (AWS ops) | Full module rewrites |
| **D** | Legacy chain retirement | Remove `core.config.Settings` | Zero remaining consumers |

**Key constraint:** `core.config.Settings` must remain stable throughout Phases A–C. Never modify it; only migrate consumers away one at a time.

---

## 6. Tier-5 ADR Impact Summary

| ADR | Scope | Gap |
|-----|-------|-----|
| ADR-0070 (Groups) | Retirement | Correctly scoped |
| ADR-0071 (Commands) | Retirement | Correctly scoped |
| ADR-0072 (Incident) | Migration | Correctly scoped but deferred — leaf operation of full rewrite |
| ADR-0073 (AWS ops) | Migration | Needs reassessment — target may not exist post-access-package |
| ADR-0074 (ATIP) | Migration | Correctly scoped |
| ADR-0075 (SRE ops) | Migration | Correctly scoped |
