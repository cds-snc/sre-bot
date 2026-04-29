---
adr_id: ADR-0017
title: "Feature Package Startup Failure Policy"
status: Superseded
decision_type: Principle
tier: Tier-1
date_created: 2026-04-27
last_updated: 2026-04-29
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - SRE Team
supersedes: []
superseded_by:
  - ADR-0049
related_records:
  - ADR-0007
  - ADR-0011
  - ADR-0013
related_packages: []
review_state: stale
---
# Feature Package Startup Failure Policy

**Date**: 2026-04-27
**Status**: Accepted
**Applies to**: All `app/packages/<name>/` plugin packages using `startup_warmup`
**External References**:
- `.github/skills/plugin-registration-lifespan/SKILL.md`
- [pluggy exception handling](https://pluggy.readthedocs.io/en/stable/#exception-handling)
- [ASGI Lifespan Protocol v2.0](https://asgi.readthedocs.io/en/latest/specs/lifespan.html#startup-failed-send-event)

---

## Context

Every `packages/<name>/__init__.py` exposes a `startup_warmup` hookimpl that is called
during FastAPI's `lifespan` startup phase via `register_feature_integrations()`. This
hook is the authoritative place to validate settings, prime caches, and register event
handlers.

All three access subpackages (`access.sync`, `access.requests`, `access.catalog`) and
other feature packages currently wrap their `startup_warmup` body in a broad
`try/except Exception` block that logs the error but does **not** re-raise. This creates
a silent misconfiguration window: the process starts, ECS marks it healthy, and the first
request then fails at runtime with an opaque error.

Three available behaviors exist at startup:

1. **Fail-startup**: re-raise (or do not catch) the exception — pluggy propagates it,
   FastAPI's lifespan context manager does not reach `yield`, the ASGI server sends
   `lifespan.startup.failed`, and the container exits with a non-zero code.
2. **Degrade with readiness gate**: catch the exception, set an `_is_ready = False` flag,
   continue startup, and gate every route/event-handler behind a 503 check on that flag.
3. **Silent-continue**: catch and log only, let the process start in a broken state.
   (**This is the current pattern. It is explicitly rejected by this decision.**)

---

## Pluggy and ASGI Semantics

### pluggy exception propagation

From pluggy docs (*Exception handling* section, pluggy ≥ 1.0):

> If any hookimpl errors with an exception no further callbacks are invoked and the
> exception is delivered to any wrappers before being re-raised at the hook invocation
> point.

This means: if a `startup_warmup` hookimpl raises, the exception surfaces directly at the
`pm.hook.startup_warmup(logger=logger)` call site inside the lifespan function. No special
re-raise logic is needed in the hookimpl itself — simply **not catching** the exception is
sufficient.

### ASGI lifespan startup failure

From the ASGI Lifespan Protocol spec (v2.0):

> **Startup Failed** — Sent by the application when it has failed to complete its startup.
> If a server sees this it should log/print the message provided and then exit.

FastAPI/Starlette translates an unhandled exception in the `lifespan` before-yield block
into this event, causing Uvicorn/ECS to exit with a non-zero status code. The container
scheduler (ECS) detects the failure and does not route traffic to the task.

---

## Options

### Option A — Fail-startup (raise)

- **Behavior**: do not catch (or re-raise) exceptions in `startup_warmup` when
  `settings.enabled = True`. When `settings.enabled = False`, log and return early.
- **Pros**:
  - Immediate, unambiguous signal — the container exits instead of silently degrading.
  - ECS health check catches it; no broken tasks receive traffic.
  - Zero runtime gate code required; no `is_ready` flag or 503 middleware.
  - Consistent with pluggy's natural exception propagation model.
  - Natural fit for Level 3 / Rich Workflow features where misconfiguration has high blast
    radius (access.sync, access.requests, access.catalog all meet this threshold).
- **Cons**:
  - A single bad config env var prevents the entire app from starting — all unrelated routes
    are also unavailable.
  - Rollback path requires an ECS task definition update (same as any broken deploy).

### Option B — Degrade with readiness gate

- **Behavior**: catch exceptions, set `_is_ready = False`, continue startup. Gate every
  route handler and every registered event handler behind a 503 check.
- **Pros**:
  - Non-feature routes remain available during a partial misconfiguration.
  - Allows the operator to fix config without a full redeploy (if env vars can be updated
    at runtime — not true for ECS).
- **Cons**:
  - Requires a shared `_is_ready` flag that every route handler, every event dispatcher
    consumer, and every Slack command handler must check.
  - State is implicit (module-level flag); test surface grows.
  - In ECS, env vars cannot be updated at runtime without a new task definition, so the
    "fix without redeploy" benefit does not apply.
  - Operationally dangerous: the process looks healthy to ECS but serves 503 to all access
    endpoints indefinitely, with no automatic recovery path.

### Option C — Silent-continue (current state)

Explicitly rejected. Allows broken request paths to be exposed without any observable
error in the startup lifecycle. Prohibited by the plugin-registration-lifespan skill.

---

## Decision

**Choose Option A — Fail-startup** for all feature packages where `settings.enabled = True`.

### Rule

| Feature state | `startup_warmup` behavior |
|---------------|---------------------------|
| `settings.enabled = True` + warmup succeeds | Normal startup |
| `settings.enabled = True` + warmup fails (config error, missing file, invalid JSON) | **Re-raise exception** — do not catch |
| `settings.enabled = True` + warmup fails (transient provider error) | Re-raise — transient failures belong to readiness, not to startup |
| `settings.enabled = False` | Log structured warning, return `None` immediately (no exception) |

### Correct `startup_warmup` shape

```python
@hookimpl
def startup_warmup(logger) -> None:
    settings = get_access_sync_settings()
    if not settings.enabled:
        logger.warning("access_sync_disabled", reason="feature_flag_off")
        return

    # Allow exceptions to propagate — pluggy re-raises them at the call site,
    # which aborts FastAPI lifespan and causes the container to exit.
    get_access_runtime_config()
    _register_sync_event_handlers()
    get_access_sync_service()
    logger.info("access_sync_providers_warmed")
```

Do **not** wrap the warmup body in `try/except Exception`. If a specific exception needs
a better log message before propagation, use `except SomeSpecificError as exc: logger.error(...); raise`.

### Degrade mode — future guidance

If a future package is genuinely optional (e.g., a metrics exporter where the main
application is fully functional without it), degrade mode may be chosen. Requirements:

1. Document the choice in the package's `__init__.py` docstring.
2. Expose `_is_ready: bool` at module level, defaulting to `False`.
3. Gate **every** route handler and event subscriber behind a check:
   ```python
   if not _is_ready:
       raise HTTPException(status_code=503, detail="feature_unavailable")
   ```
4. Emit a structured log on every 503 response with `feature`, `reason`, and `config_hint`.
5. Add a test that verifies warmup failure produces 503 on all feature routes.

No current package meets the "genuinely optional" threshold.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Bad env var takes down entire app | ECS deployment safety: test in staging with `entry.sh` vars before prod deploy. Pydantic validates settings at `BaseSettings` instantiation — config errors are caught early with clear messages. |
| Transient error at startup (e.g., SSM fetch timeout) | Retry logic belongs in the config loader, not in `startup_warmup`. Loader retries should be bounded (≤ 3 attempts with backoff). If all retries fail, re-raise. |
| Developer confusion about which exceptions to catch | Convention: only catch `SpecificConfigError` to add logging context, then always `raise`. Never catch `Exception` without re-raising. |

---

## Consequences

- All three access subpackages (`sync`, `requests`, `catalog`) must remove their
  `try/except Exception` blocks from `startup_warmup`.
- Future packages must follow this rule from day one.
- Tests must assert that misconfigured warmup raises (fail-startup test) and that
  disabled feature returns None without raising (disabled-flag test).

---

## Sources

- pluggy 1.6 docs — Exception handling: https://pluggy.readthedocs.io/en/stable/#exception-handling
- ASGI Lifespan Protocol v2.0 — Startup Failed: https://asgi.readthedocs.io/en/latest/specs/lifespan.html#startup-failed-send-event
- FastAPI Lifespan Events: https://fastapi.tiangolo.com/advanced/events/
- `.github/skills/plugin-registration-lifespan/SKILL.md` — Warmup Failure Policy Pattern
- ADR-07 (2026-03-20) — "startup_warmup hookimpl preserves fail-fast guarantee"
