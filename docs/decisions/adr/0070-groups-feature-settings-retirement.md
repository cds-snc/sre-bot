---
adr_id: ADR-0070
title: "GroupsFeatureSettings Retirement"
status: Accepted
decision_type: Deprecation Decision
tier: Tier-5
primary_domain: Configuration and Secrets
secondary_domains:
  - Package and Plugin Architecture
owners:
  - SRE Team
date_created: 2026-04-29
last_updated: 2026-04-29
last_reviewed: 2026-04-29
next_review_due: 2026-08-27
constrained_by:
  - ADR-0044
  - ADR-0055
impacts: []
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0047
  - ADR-0056
related_packages:
  - app/packages/access
---

# GroupsFeatureSettings Retirement

## Context

The groups feature (`app/modules/groups/`) is fully deprecated. Its functionality — group lifecycle management, provider registry, reconciliation, and circuit breaker protection — has been superseded by the access feature (`app/packages/access/`). There is no `app/packages/groups/` target and none will be created.

ADR-0055 Standard 4 requires a Tier-5 record for each feature settings class in `infrastructure/configuration/features/`. Because the groups feature is being retired rather than migrated, this ADR records a deprecation, not a migration.

## Decision

**Retire `GroupsFeatureSettings` and its source file** when `app/modules/groups/` is fully removed.

### Source Artifact

| Artifact | Path |
|----------|------|
| Settings class | `app/infrastructure/configuration/features/groups.py` |
| Settings aggregator field | `Settings.groups: GroupsFeatureSettings` |
| Re-export | `app/infrastructure/configuration/features/__init__.py` |

### Environment Variables Retired

| Variable | Purpose |
|----------|---------|
| `GROUP_PROVIDERS` | Per-provider configuration (JSON dict) |
| `RECONCILIATION_ENABLED` | Enable reconciliation for failed propagations |
| `RECONCILIATION_BACKEND` | Backend type (memory, dynamodb, sqs) |
| `RECONCILIATION_MAX_ATTEMPTS` | Maximum retry attempts |
| `RECONCILIATION_BASE_DELAY_SECONDS` | Base exponential backoff delay |
| `RECONCILIATION_MAX_DELAY_SECONDS` | Maximum backoff delay |
| `CIRCUIT_BREAKER_ENABLED` | Enable circuit breaker protection |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | Failures before opening circuit |
| `CIRCUIT_BREAKER_TIMEOUT_SECONDS` | Recovery attempt timeout |
| `CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS` | Max calls in half-open state |
| `REQUIRE_JUSTIFICATION` | Require justification for operations |
| `MIN_JUSTIFICATION_LENGTH` | Minimum justification text length |
| `GROUP_DOMAIN` | Domain suffix for group emails |

### Consumers (to be removed with module)

| File | Access Pattern |
|------|---------------|
| `app/modules/groups/providers/google_workspace.py` | `settings.groups.group_domain` |
| `app/modules/groups/providers/registry_utils.py` | `settings.groups.providers` |
| `app/modules/groups/providers/__init__.py` | `settings.groups.providers` |

### Blocking Prerequisite

Full removal of `app/modules/groups/`. The access package (`app/packages/access/`) must have achieved feature parity for all group management operations currently served by the groups module.

### Retirement Criteria

All conditions must be true:

1. `app/modules/groups/` directory is deleted.
2. `app/infrastructure/configuration/features/groups.py` is deleted.
3. `GroupsFeatureSettings` is removed from `infrastructure/configuration/features/__init__.py`.
4. `Settings.groups` field is removed from the Settings aggregator (or the aggregator itself has been dissolved per ADR-0055 Standard 7).
5. No imports of `GroupsFeatureSettings` remain in the codebase.
6. All 13 environment variables are removed from deployment configurations (ECS task definitions, `.env` templates, SSM parameters).
7. Quality gates pass: `mypy`, `flake8`, `black --check .`, `pytest app/tests --ignore=app/tests/smoke`.

### Target Date

2026-09-30 (contingent on access feature parity and groups module removal).

## Consequences

- The access package's `AccessSettings` (in `app/packages/access/common/settings.py`) is the successor for any group-related configuration. Access uses its own settings pattern with `ACCESS_` prefix and does not inherit from `GroupsFeatureSettings`.
- Any group management capability not yet covered by the access feature must be migrated there before this retirement can execute.
- Circuit breaker and reconciliation patterns used by the groups module may be generalized into infrastructure utilities; that decision is independent of this settings retirement.
