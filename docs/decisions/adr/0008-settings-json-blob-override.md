---
adr_id: ADR-0008
title: "Settings JSON Blob Override Pattern"
status: Accepted
decision_type: Principle
tier: Tier-1
date_created: 2026-04-27
last_updated: 2026-04-27
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - Platform Engineering
supersedes: []
superseded_by: []
related_records:
  - ADR-0007
related_packages: []
review_state: stale
---
# ADR-08: Settings JSON Blob Override Pattern

**Date**: 2026-04-27
**Status**: Accepted
**Applies to**: All `packages/<name>/settings.py` using `BaseSettings` with `env_nested_delimiter`
**External References**:
- [pydantic-settings v2 — Parsing environment variable values](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [pydantic-settings v2 — Field value priority](https://docs.pydantic.dev/latest/concepts/pydantic_settings/#field-value-priority)

---

## Context

When a `BaseSettings` class is configured with `env_nested_delimiter` and has a nested
`BaseModel` field, pydantic-settings v2 supports two ways to populate that field from the
environment:

1. **Flat vars**: individual env vars whose names are formed by joining the prefix, field
   path, and delimiter.
   ```
   ACCESS_SYNC_ENABLED=true
   ACCESS_SYNC_JOB_TTL_SECONDS=3600
   ```

2. **JSON blob var**: a single env var whose name matches the field name (with prefix),
   containing a JSON-encoded object for the entire nested model.
   ```
   ACCESS_SYNC='{"enabled": true, "job_ttl_seconds": 3600}'
   ```

The JSON blob behavior is a built-in pydantic-settings v2 capability. It is **not** a
custom implementation in this codebase. It activates automatically for any `BaseModel`
sub-field whenever `env_nested_delimiter` is set — no opt-in is required.

This codebase's `AccessSettings` exposes three implicit JSON blob vars:
`ACCESS_SYNC`, `ACCESS_REQUESTS`, and `ACCESS_CATALOG`.

---

## Precedence Behavior (pydantic-settings v2)

Within the `EnvSettingsSource`, pydantic-settings v2 merges values from the JSON blob and
flat vars for the same field. **Flat vars take precedence over JSON blob values** for any
key that appears in both:

```bash
# JSON blob sets enabled=false and job_ttl_seconds=300
ACCESS_SYNC='{"enabled": false, "job_ttl_seconds": 300}'
# Flat var overrides enabled only
ACCESS_SYNC_ENABLED=true

# Result: enabled=true, job_ttl_seconds=300
```

This makes the JSON blob suitable as a "base configuration" and flat vars as targeted
overrides. The behavior is documented in the pydantic-settings field value priority
section.

---

## Options

### Option A — Keep as a documented emergency override (recommended)

- Document the JSON blob capability explicitly; make it visible to operators.
- Declare it an "emergency override" and "local dev / CI bulk-init" tool.
- Add structured startup log when a JSON blob var is detected (e.g., `ACCESS_SYNC` is
  present in `os.environ`).
- Flat vars remain the canonical operational configuration surface.

### Option B — Deprecate and remove

- Add deprecation warning log when JSON blob vars are detected.
- Publish a one-release-window migration guide (use individual flat vars instead).
- Remove detection code after the window.
- **Risk**: breaks CI pipelines and local dev setups that currently rely on JSON blobs.
  No concrete benefit — the pattern is safe and the pydantic-settings behavior is stable.

### Option C — Formalize as primary config

- Treat `ACCESS_SYNC='{...}'` as the primary way to configure the sync slice.
- **Risk**: operators must escape and quote large JSON blobs in ECS task definitions and
  SSM parameters; error-prone. Flat vars are universally simpler in ECS and Terraform.

---

## Decision

**Choose Option A — Keep as a documented emergency override.**

### Rationale

- pydantic-settings v2 JSON blob support is stable, documented upstream, and relied on in
  multiple existing deployments (CI and local dev).
- Flat vars remain the canonical and required pattern for production ECS deployments;
  JSON blobs are not used in any SSM parameter or Terraform task definition today.
- The flat-var-wins precedence is deterministic and safe.
- Deprecating provides no architectural improvement; it only creates a migration burden.

### Rules

1. **Flat vars are canonical for production**. All ECS task definitions and SSM parameters
   use individual flat vars (`ACCESS_SYNC_ENABLED`, etc.).
2. **JSON blob vars are permitted** for:
   - Local development (`.env` files with a single `ACCESS_SYNC='...'` line).
   - CI test matrix overrides (env block in CI YAML).
   - Emergency one-off operational overrides (with change-management approval).
3. **JSON blob vars are NOT permitted** in:
   - SSM parameters written by `entry.sh`.
   - Terraform `environment` blocks in ECS task definitions.
   - Production parameter stores.
4. **Detection logging**: at startup, if a JSON blob var is present in `os.environ`, emit
   a structured `info` log:
   ```python
   import os, structlog
   _logger = structlog.get_logger()
   if "ACCESS_SYNC" in os.environ:
       _logger.info("access_settings_json_blob_detected", var="ACCESS_SYNC",
                    hint="flat vars take precedence; json blob is for dev/ci only")
   ```
   This makes operational use visible in CloudWatch without blocking startup.
5. **Field naming**: the JSON blob var name is the `env_prefix` + field name with no
   delimiter. For `AccessSettings` with `env_prefix="ACCESS_"` and field `sync`, the var
   is `ACCESS_SYNC`. This cannot be changed without a pydantic-settings configuration
   change.

### Which vars are implicitly supported

| JSON blob var     | Nested model field        | Canonical flat var prefix   |
|-------------------|---------------------------|-----------------------------|
| `ACCESS_SYNC`     | `AccessSettings.sync`     | `ACCESS_SYNC_`              |
| `ACCESS_REQUESTS` | `AccessSettings.requests` | `ACCESS_REQUESTS_`          |
| `ACCESS_CATALOG`  | `AccessSettings.catalog`  | `ACCESS_CATALOG_`           |
| `ACCESS_CONFIG`   | `AccessSettings.config`   | `ACCESS_CONFIG_`            |

All four exist as a consequence of `env_nested_delimiter`. Only the first three are
operationally relevant today.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Operator uses JSON blob in ECS and flat var in SSM — precedence confusion | Rule 3 above: JSON blob is prohibited in SSM/Terraform. Detection log surfaces violations. |
| pydantic-settings v2 changes merge semantics | Pinned to pydantic-settings ≥ 2.x in requirements.txt. Check release notes on major upgrades. |
| JSON blob contains a key that does not exist in the model — silently ignored | `extra="ignore"` in `SettingsConfigDict` is intentional (ADR-07). Unknown keys are always dropped. |
| JSON blob cannot be validated before runtime | This is inherent to env-var-as-JSON; acceptable for dev/CI use cases. For production, use flat vars which fail at `BaseSettings` instantiation with a clear Pydantic error. |

---

## Sources

- pydantic-settings v2 — Parsing environment variable values:
  https://docs.pydantic.dev/latest/concepts/pydantic_settings/#parsing-environment-variable-values
- pydantic-settings v2 — Field value priority:
  https://docs.pydantic.dev/latest/concepts/pydantic_settings/#field-value-priority
- ADR-07 (2026-03-20) — env_nested_delimiter + env_nested_max_split pattern
