---
adr_id: ADR-0066
title: "Access Config Env-Source Naming"
status: Accepted
decision_type: Feature Decision
tier: Tier-4
primary_domain: Configuration and Secrets
secondary_domains: []
date_created: 2026-04-30
last_updated: 2026-04-30
last_reviewed: 2026-04-30
next_review_due: 2026-08-28
owners:
  - SRE Team
constrained_by:
  - ADR-0044
  - ADR-0047
  - ADR-0055
impacts: []
supersedes:
  - ADR-0042
superseded_by: []
related_records:
  - ADR-0043
related_packages:
  - app/packages/access
---

# Access Config Env-Source Naming

## Context

- Problem statement: The access package env-source configuration used `ACCESS_SYNC_*` prefixed environment variables, inherited from early designs when the env-source loader was only used by the sync subfeature. Now all three access subfeatures (sync, request, catalog) consume the same runtime config. The `ACCESS_SYNC_*` prefix is semantically incorrect and misleading. ADR-0042 (Accepted, implemented) corrected this, but was authored as a pre-program legacy record without canonical metadata or constraint references. This record supersedes ADR-0042 with a properly structured Tier-4 decision.
- Business/operational drivers:
  - Operators deploying the access feature with `ACCESS_CONFIG_SOURCE=env` need a discoverable, coherent set of environment variable names.
  - The runtime config (`AccessRuntimeConfig`) drives all three access subfeatures — naming must reflect this shared scope, not imply sync-only ownership.
- Constraints:
  - ADR-0047 (Configuration and Settings Governance) Principle 1 requires semantic namespace coherence for env vars.
  - ADR-0055 (Settings Implementation and Dissolution) governs feature-owned settings patterns, including env-source models.
- Non-goals:
  - This record does not govern lock lifecycle or operator intervention scope. Lock lifecycle boundaries are governed by ADR-0058 Standard 4 and Standard 9. ADR-0043 was independently rejected per those standards.
  - This record does not redesign Access Sync reconciliation behavior.

## Decision

Rename access env-source configuration variables from the `ACCESS_SYNC_*` prefix to the `ACCESS_CONFIG_ENV_*` prefix. This rename is semantically correct because:

- The env-source runtime config (`AccessRuntimeConfig`) drives all three access subfeatures: sync, request, and catalog.
- `ACCESS_CONFIG_ENV_*` is a natural sub-namespace of `ACCESS_CONFIG_` (the settings prefix for `AccessConfigSettings` which controls config source selection).
- `ACCESS_CONFIG_SOURCE=env` → populate `ACCESS_CONFIG_ENV_*` vars is a discoverable operator pattern.

**Canonical name mapping:**

| Old name (removed) | Canonical name |
|--------------------|----------------|
| `ACCESS_SYNC_DIR_PREFIX` | `ACCESS_CONFIG_ENV_DIR_PREFIX` |
| `ACCESS_SYNC_DIR_SEPARATOR` | `ACCESS_CONFIG_ENV_DIR_SEPARATOR` |
| `ACCESS_SYNC_PLATFORMS_JSON` | `ACCESS_CONFIG_ENV_PLATFORMS_JSON` |

**Implementation status:** Complete. The rename was applied in [loaders.py](../../app/packages/access/common/config/loaders.py) (`EnvConfigLoader._EnvModel`). No deprecation aliases needed — greenfield vars with zero production deployments at rename time.

**Naming rule for future vars:** Any new env var read only when `ACCESS_CONFIG_SOURCE=env` must use the `ACCESS_CONFIG_ENV_*` prefix.

## Alternatives Considered

1. Keep `ACCESS_SYNC_*` prefix:
   - Pros: No rename effort.
   - Cons: Semantically wrong — vars drive all three subfeatures, not just sync. Violates ADR-0047 Principle 1 (namespace coherence). Misleads operators into thinking the vars are sync-specific.
   - Why not chosen: Semantic correctness and discoverability outweigh rename cost (zero, given no production deployments).

2. Use `ACCESS_RUNTIME_*` prefix:
   - Pros: Reflects the `AccessRuntimeConfig` domain entity name.
   - Cons: Orphan namespace — no parent `ACCESS_RUNTIME_` settings group exists. `ACCESS_CONFIG_ENV_*` naturally nests under `ACCESS_CONFIG_` (which controls config source selection), making the operator pattern `ACCESS_CONFIG_SOURCE=env` → `ACCESS_CONFIG_ENV_*` self-documenting.
   - Why not chosen: `ACCESS_CONFIG_ENV_*` provides better namespace nesting and operator discoverability.

3. Use `ACCESS_ENV_*` prefix:
   - Pros: Shorter.
   - Cons: Ambiguous — could imply "access environment" rather than "access config loaded from env source." Missing the `CONFIG` segment breaks the parent-child namespace relationship with `ACCESS_CONFIG_SOURCE`.
   - Why not chosen: Clarity over brevity.

## Consequences

- Positive impacts:
  - Env-source naming is semantically clear and consistent with the `ACCESS_CONFIG_*` namespace.
  - Operator discoverability: `ACCESS_CONFIG_SOURCE=env` naturally leads operators to look for `ACCESS_CONFIG_ENV_*` vars.
  - All three subfeatures are correctly represented in the naming.
- Tradeoffs accepted:
  - Longer variable names (`ACCESS_CONFIG_ENV_DIR_PREFIX` vs `ACCESS_SYNC_DIR_PREFIX`). Accepted because clarity and namespace coherence outweigh brevity.
- Risks introduced:
  - None. The rename is already implemented with zero production deployments of the old names.
- Mitigations:
  - N/A — no risks require mitigation.

## Compliance and Boundaries

- Package/infrastructure boundary impact: No infrastructure boundary changes. The `_EnvModel` is internal to the access feature's config loader. No infrastructure service involved.
- Type boundary impact (Protocol/dataclass/BaseModel/TypedDict): No new type boundary decisions. `AccessRuntimeConfig` remains a frozen dataclass (domain entity). `_EnvModel` remains a private Pydantic `BaseSettings` subclass for env parsing only.
- Startup/plugin registration impact: None. Config loading occurs during access feature initialization, unchanged.
- Settings partitioning impact: `ACCESS_CONFIG_ENV_*` vars are access-feature-owned settings (read only when `ACCESS_CONFIG_SOURCE=env`). The settings slice is `AccessConfigSettings` with prefix `ACCESS_CONFIG_`.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- Validation summary: Supersedes ADR-0042 with canonical metadata and constraint references. Decision is already implemented. All naming aligns with ADR-0047 Principle 1.
- Follow-up actions:
  - Update `app/packages/access/sync/README.md` to use canonical `ACCESS_CONFIG_ENV_*` names (documentation gap from ADR-0042 implementation).

## Source References

1. Source title: ADR-0042 (Access Runtime Env-Source Variable Naming)
   - URL: docs/decisions/adr/0042-access-runtime-env-source-naming.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-30
   - Relevance summary: Provides the naming decision being superseded. Accepted 2026-04-27. Fully implemented in codebase. This record incorporates all of ADR-0042's content with proper canonical structure.
2. Source title: ADR-0047 Principle 1 (Namespace Coherence for Settings)
   - URL: docs/decisions/adr/0047-configuration-and-settings-governance-canonical-model.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-30
   - Relevance summary: Governs semantic namespace coherence for environment variables. Validates `ACCESS_CONFIG_ENV_*` as correct namespace for env-source config.
3. Source title: ADR-0055 (Settings Implementation and Dissolution Standard)
   - URL: docs/decisions/adr/0055-settings-implementation-and-dissolution-standard.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-30
   - Relevance summary: Governs feature-owned settings patterns including Pydantic BaseSettings subclasses for env parsing.

## Change Log

- 2026-04-30: Created. Supersedes ADR-0042 (naming decision, incorporated with canonical structure). Narrowed from original draft that also included ADR-0043 rejection rationale — lock lifecycle scope is governed by ADR-0058 Standard 9, not this feature-scoped record.
