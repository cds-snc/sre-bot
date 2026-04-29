---
adr_id: ADR-0072
title: "IncidentFeatureSettings Migration to packages/incident"
status: Accepted
decision_type: Migration Decision
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
 - app/modules/incident
---

# IncidentFeatureSettings Migration to packages/incident

## Context

`IncidentFeatureSettings` is defined in `app/infrastructure/configuration/features/incident.py` and provides two environment-variable-sourced fields for the incident management feature. Per ADR-0055 Standard 3 (reader-owns rule) and Standard 4 (transitional posture), this settings class must migrate to `app/packages/incident/settings.py` when `app/modules/incident/` migrates to `app/packages/incident/`.

**Key complication:** `INCIDENT_CHANNEL` and `SLACK_SECURITY_USER_GROUP_ID` are also declared in `SlackSettings` (`app/infrastructure/configuration/integrations/slack.py`). This duplication was noted in ADR-0047's challenge review. During migration, the feature-owned copies become canonical and the integration-side duplicates must be removed.

## Decision

**Migrate `IncidentFeatureSettings` to `app/packages/incident/settings.py`** when `app/modules/incident/` migrates to `app/packages/incident/`.

### Source Artifact

| Artifact | Path |
|----------|------|
| Settings class | `app/infrastructure/configuration/features/incident.py` |
| Settings aggregator field | `Settings.feat_incident: IncidentFeatureSettings` |
| Re-export | `app/infrastructure/configuration/features/__init__.py` |

### Target Artifact

| Artifact | Path |
|----------|------|
| Settings class | `app/packages/incident/settings.py` |
| Singleton provider | `app/packages/incident/settings.py :: get_incident_settings()` |

### Environment Variables

| Variable | Purpose | Duplication |
|----------|---------|-------------|
| `INCIDENT_CHANNEL` | Slack channel ID for incident notifications | Also in `SlackSettings` - deduplicate during migration |
| `SLACK_SECURITY_USER_GROUP_ID` | Security team user group ID for mentions | Also in `SlackSettings` - deduplicate during migration |

### Target Pattern

Follow the `AccessSettings` reference implementation (ADR-0055 Standard 1):

```python
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class IncidentSettings(BaseSettings):
 model_config = SettingsConfigDict(extra="ignore", env_file=".env")

 incident_channel: str = Field(default="", alias="INCIDENT_CHANNEL")
 slack_security_user_group_id: str = Field(
 default="", alias="SLACK_SECURITY_USER_GROUP_ID"
 )

@lru_cache(maxsize=1)
def get_incident_settings() -> IncidentSettings:
 return IncidentSettings()
```

### Migration Steps

1. Create `app/packages/incident/settings.py` with `IncidentSettings(BaseSettings)` and `get_incident_settings()`.
2. Update all consumers in `app/packages/incident/` to use `get_incident_settings()` instead of `settings.feat_incident`.
3. **Deduplication safety check:** Before removing `INCIDENT_CHANNEL` and `SLACK_SECURITY_USER_GROUP_ID` from `SlackSettings`, verify no non-incident code reads these values via `settings.slack.INCIDENT_CHANNEL` or `settings.slack.SLACK_SECURITY_USER_GROUP_ID`. Current search (2026-04-29) found only one reference in `slack.py` line 24 (a comment/docstring), confirming safe removal.
4. Remove `INCIDENT_CHANNEL` and `SLACK_SECURITY_USER_GROUP_ID` from `SlackSettings` (deduplication).
5. **Fix import-time side effects:** `app/modules/incident/incident.py` (line 20-21) and `app/modules/incident/core.py` (line 17-18) both assign `INCIDENT_CHANNEL = settings.feat_incident.INCIDENT_CHANNEL` and `SLACK_SECURITY_USER_GROUP_ID = settings.feat_incident.SLACK_SECURITY_USER_GROUP_ID` at module level. This violates ADR-0046 (no side effects at import time). Replace with function calls or lazy accessors during migration.
6. Remove `IncidentFeatureSettings` from `infrastructure/configuration/features/incident.py`.
7. Remove re-export from `infrastructure/configuration/features/__init__.py`.
8. Remove `Settings.feat_incident` field from the aggregator.

### Blocking Prerequisite

Migration of `app/modules/incident/` to `app/packages/incident/`.

### Isolation and Execution Phasing

The incident module operates entirely on the legacy `core.config.settings` singleton chain (7 files access `settings.PREFIX`, `settings.feat_incident`, or `settings.google_resources`). It has zero imports from `infrastructure.configuration` or `infrastructure.services` for settings. No infrastructure code imports from `app/modules/incident/` (zero reverse coupling).

This means ADR-0072 execution does not block the infrastructure settings dissolution program (ADR-0055 Action 5). The `infrastructure.configuration.Settings` aggregator can be fully dissolved - its domain settings classes made into independent singletons, its providers narrowed, its boundary violations fixed - without touching any incident module code. The `core.config.Settings` legacy singleton remains stable as a compatibility shim throughout (see ADR-0055 Standard 4, Dual Settings Chain Coexistence).

ADR-0072 execution is deferred to Phase C of the ADR program - a separate feature rearchitecting project that includes extracting service boundaries, replacing direct Slack SDK and Google API calls with infrastructure clients, introducing repository patterns, and fixing module-level settings loading. Settings migration is a leaf operation within that larger effort (~5% of scope).

### Retirement Criteria

All conditions must be true:

1. `app/infrastructure/configuration/features/incident.py` is deleted.
2. `IncidentFeatureSettings` is removed from `infrastructure/configuration/features/__init__.py`.
3. `Settings.feat_incident` field is removed from the Settings aggregator.
4. No imports of `IncidentFeatureSettings` remain in the codebase.
5. `INCIDENT_CHANNEL` and `SLACK_SECURITY_USER_GROUP_ID` are removed from `SlackSettings`.
6. Quality gates pass: `mypy`, `flake8`, `black --check .`, `pytest app/tests --ignore=app/tests/smoke`.

### Target Date

TBD - blocked on prerequisite module migration from `app/modules/incident/` to `app/packages/incident/`.

## Consequences

- The incident package becomes self-contained for settings, following the access package pattern.
- Deduplication of `INCIDENT_CHANNEL` and `SLACK_SECURITY_USER_GROUP_ID` removes a known violation of ADR-0047 Principle 1 (single source per domain).
- Consumers that currently read these values from `SlackSettings` must be redirected to the incident package's settings provider.

## Change Log

- 2026-04-29: Added "Isolation and Execution Phasing" section documenting legacy chain isolation verdict (7 files, zero infrastructure imports, zero reverse coupling), Phase C deferral, and non-blocking relationship to settings dissolution program. Source: incident and webhooks legacy feature rearchitecting assessment.
- 2026-04-29: Created Tier-5 migration record for IncidentFeatureSettings.
