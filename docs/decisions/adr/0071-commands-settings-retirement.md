---
adr_id: ADR-0071
title: "CommandsSettings Retirement"
status: Accepted
decision_type: Deprecation
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
  - ADR-0055
impacts: []
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0047
  - ADR-0056
  - ADR-0059
related_packages: []
---

# CommandsSettings Retirement

## Context

The commands feature (`app/infrastructure/commands/`) was an early attempt at standardizing interaction providers across platforms (Slack, Teams, etc.) but was ill-scoped. The correct architectural approach — a unified InteractionProvider Protocol with capability registration, platform abstraction, and HTTP-first bridge patterns — is defined by ADR-0059 (Interaction Provider and Feature Integration Standard, Wave 4).

There is no `app/packages/commands/` target and none will be created. `CommandsSettings` has no corresponding module in `app/modules/` and no successor package.

ADR-0055 Standard 4 requires a Tier-5 record for each feature settings class in `infrastructure/configuration/features/`. Because the commands concept is being retired rather than migrated, this ADR records a deprecation, not a migration.

## Decision

**Retire `CommandsSettings` and its source file** when the commands infrastructure is fully removed and replaced by the interaction provider architecture (ADR-0059).

### Source Artifact

| Artifact | Path |
|----------|------|
| Settings class | `app/infrastructure/configuration/features/commands.py` |
| Settings aggregator field | `Settings.commands: CommandsSettings` |
| Re-export | `app/infrastructure/configuration/features/__init__.py` |

### Environment Variables Retired

| Variable | Purpose |
|----------|---------|
| `COMMAND_PROVIDERS` | Per-provider configuration for command adapters (JSON dict) |

### Consumers (to be removed with infrastructure)

| File | Access Pattern |
|------|---------------|
| `app/infrastructure/commands/providers/__init__.py` | `settings.commands.providers` |
| `app/infrastructure/commands/providers/slack.py` | `settings.commands.providers['slack']` |

### Blocking Prerequisite

Completion of ADR-0059 (Interaction Provider and Feature Integration Standard) and its implementation. The interaction provider architecture must fully replace the commands infrastructure's provider registration and dispatch capabilities.

### Retirement Criteria

All conditions must be true:

1. `app/infrastructure/commands/` directory is deleted or refactored into the interaction provider architecture.
2. `app/infrastructure/configuration/features/commands.py` is deleted.
3. `CommandsSettings` is removed from `infrastructure/configuration/features/__init__.py`.
4. `Settings.commands` field is removed from the Settings aggregator (or the aggregator itself has been dissolved per ADR-0055 Standard 7).
5. No imports of `CommandsSettings` remain in the codebase.
6. `COMMAND_PROVIDERS` environment variable is removed from deployment configurations.
7. Quality gates pass: `mypy`, `flake8`, `black --check .`, `pytest app/tests --ignore=app/tests/smoke`.

### Target Date

2026-09-30 (contingent on ADR-0059 authoring and interaction provider implementation).

## Consequences

- Platform-specific command registration will be governed by the InteractionProvider Protocol (ADR-0059) instead of the `COMMAND_PROVIDERS` JSON configuration pattern.
- Any per-platform enable/disable configuration currently in `COMMAND_PROVIDERS` will be handled by the interaction provider's capability negotiation model, not a settings class.
- Tests in `app/tests/integration/infrastructure/commands/` must be migrated or removed as part of the commands infrastructure retirement.
