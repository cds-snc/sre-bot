# Infrastructure Decentralization Inventory

**Date:** 2026-04-28  
**Related ADRs:** ADR-0055, ADR-0056, ADR-0076, ADR-0077  
**Purpose:** Current-state audit of settings aggregator and provider layer for dissolution planning

---

## 1. Problem Summary

Two antipatterns in the infrastructure layer:

- **Settings aggregator:** Single `Settings(BaseSettings)` root nests 22 sub-settings classes, each inheriting `BaseSettings`. Violates pydantic-settings v2 best practice, inflates test surface, creates single point of failure.
- **Provider over-centralization:** 19 `@lru_cache` singleton providers in one 850+ line file. 5 providers pass full `Settings` object; 6 service classes store it on `self._settings`.

---

## 2. Settings Classes Inventory

| Category | Count | Classes | Target Location |
|----------|-------|---------|-----------------|
| Integration | 9 | SlackSettings, AwsSettings, GoogleWorkspaceSettings, GoogleResourcesConfig, MaxMindSettings, NotifySettings, OpsGenieSettings, SentinelSettings, TrelloSettings | `infrastructure/configuration/integrations/` — independent singletons |
| Feature (legacy) | 6 | GroupsFeatureSettings, CommandsSettings, IncidentFeatureSettings, AWSFeatureSettings, AtipSettings, SreOpsSettings | Owning packages on module migration |
| Infrastructure | 6 | ServerSettings, DevSettings, IdempotencySettings, RetrySettings, PlatformsSettings, DirectorySettings | `infrastructure/configuration/infrastructure/` — independent singletons |
| App-level | 3 | PREFIX, LOG_LEVEL, GIT_SHA | Minimal `AppSettings(BaseSettings)` |

---

## 3. Provider Injection Audit

### Correct — extracts settings slice (8 providers)

`get_aws_clients()` → `settings.aws`, `get_google_workspace_clients()` → `settings.google_workspace`, `get_maxmind_client()` → `settings.maxmind`, `get_jwks_manager()` → `settings.server.ISSUER_CONFIG`, `get_slack_client()` → `settings.slack.SLACK_TOKEN`, `get_teams_client()` → `settings.platforms.teams`, `get_directory_provider()` → `settings.directory`, `get_identity_service()` → passes full but discards after init

### Correct — composes other providers (3)

`get_storage_service()` → `get_aws_clients().dynamodb`, `get_audit_trail_service()` → `get_storage_service()`, `get_event_dispatcher()` → no deps

### Antipattern — passes full Settings (5 providers)

| Provider | Service Class | Actual Need |
|----------|--------------|-------------|
| `get_idempotency_service()` | stores full Settings + internal factory | `IdempotencySettings` only |
| `get_resilience_service()` | stores full Settings + internal factory | `RetrySettings` only |
| `get_notification_service()` | stores full Settings in constructor | Only used to build channels |
| `get_command_service()` | stores full Settings | Never accesses after init |
| `get_platform_service()` | stores full Settings | Used in `load_providers()` — could extract slice |

---

## 4. Services Storing Full Settings (6 classes)

| Class | File | Actual Need |
|-------|------|-------------|
| NotificationService | `notifications/service.py` | Only uses in constructor |
| CommandService | `commands/service.py` | Never accesses after init |
| PlatformService | `platforms/service.py` | `load_providers()` — extractable |
| SlackPlatformProvider | `platforms/providers/slack.py` | Passes to internal constructors |
| TeamsPlatformProvider | `platforms/providers/teams.py` | Passes to internal constructors |
| DynamoDBCache | `idempotency/dynamodb.py` | `settings.aws` only |

---

## 5. Boundary Violations (8 files)

Files importing `Settings` directly instead of via provider:

1. `infrastructure/notifications/channels/email.py`
2. `infrastructure/notifications/channels/sms.py`
3. `infrastructure/notifications/service.py`
4. `infrastructure/idempotency/factory.py`
5. `infrastructure/idempotency/dynamodb.py`
6. `infrastructure/idempotency/service.py`
7. `infrastructure/resilience/retry/factory.py`
8. `infrastructure/resilience/service.py`

---

## 6. Reference Implementation

`app/packages/access/` demonstrates the target pattern:

- `common/settings.py`: `AccessSettings(BaseSettings)` — owns its env vars, nested `BaseModel` sections (not `BaseSettings`)
- `common/providers.py`: Package-local `@lru_cache` providers for settings and runtime config
- `common/config/loaders.py`: Protocol-based config loading for runtime config documents
- Sub-package `__init__.py`: `@hookimpl startup_warmup` validates settings at startup

---

## 7. ADR Gaps Identified

| Gap | Severity | Fix Vehicle |
|-----|----------|-------------|
| ADR-0047 P5: No distinction between env-var bootstrap settings and loader-based runtime config | Medium | ADR-0055 |
| ADR-0048 B2: Package-internal providers not explicitly permitted | Low | ADR-0056 |
| ADR-0047 meta: Missing `related_packages: [app/packages/access]` | Low | Metadata patch |
