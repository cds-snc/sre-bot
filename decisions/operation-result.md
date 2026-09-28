---
status: Accepted
date: 2026-07-06
applies: target
scope: The uniform return envelope at integration and service boundaries.
---

# Operation Result

## Context

Consumers of external calls need to branch on expected outcomes (success, not-found, retriable, permanent, auth) without knowing vendor exception hierarchies. Result envelopes are the right tool **at boundaries only** — pervasive Result typing is not idiomatic Python, where exceptions remain the norm for internal flow. The old record claimed static exhaustiveness guarantees its shape could not deliver.

## Decision

`OperationResult` is a shared type of the public plugin API in `app/contracts/` ([plugin-architecture.md](plugin-architecture.md)), importable from every layer, `integrations/` included. It is a **frozen dataclass** carrying:

- `status: OperationStatus` — closed enum: `SUCCESS`, `NOT_FOUND`, `TRANSIENT_ERROR`, `PERMANENT_ERROR`, `UNAUTHORIZED`.
- `data` — the typed payload; present only on `SUCCESS`.
- `error_code: str` — machine-readable, mandatory on non-success, drawn from the project registry (`SCREAMING_SNAKE`; the registry is the enum-like module next to the dataclass — adding a code is a reviewed one-line change). `UNAUTHORIZED` distinguishes `UNAUTHENTICATED` vs `FORBIDDEN` via `error_code`, mapping to 401/403 at the HTTP edge.
- `message: str | None` — for logs/operators, never for end users; capability-level, no SDK internals. Optional on `SUCCESS`.
- `retry_after: float | None` — only when the upstream provided a hint; consumers apply their own backoff when absent.
- `cause: BaseException | None` — internal-only diagnostic; never rendered or serialized; preserves the traceback that string-flattening destroys.

**Where it appears:** adapter → feature service, and feature service → handler. Nowhere else — not in domain types, not on the wire (edges translate it: [errors-and-http.md](errors-and-http.md), platform renderers), not raised, not as internal control flow. Clients raise SDK exceptions below it ([outbound-clients.md](outbound-clients.md)); programmer errors and invariant violations raise through it.

**Branching:** consumers use `match result.status:` with `typing.assert_never` on the fall-through. That — not the enum being "closed" — is what makes missing branches a type error. `if result.is_success:` convenience checks are fine for two-outcome sites.

**No monad ops.** `map`/`bind` on a status-field dataclass cannot be soundly typed and are removed. Sequenced calls use plain branching; if railway composition is ever truly needed, adopt the `returns` library deliberately rather than half-building it.

## Consequences

- One page of contract answers "what do I get back and what do I do with it" for every boundary in the app.
- The five statuses are deliberately coarse; fidelity lives in `error_code`. Adding a status amends this record; adding a code is routine.

## Checks

- `OperationResult` is `frozen=True`; unit tests assert immutability.
- mypy passes with `assert_never` exhaustiveness in at least the shared renderers.
- grep: no `OperationResult` in `app/models/` or route response models; no `.map(`/`.bind(` call sites.

## Migration

No open divergences: `OperationResult`, `OperationStatus` and the `ErrorCode` registry live in `app/contracts/operations/` ([plugin-architecture.md](plugin-architecture.md)).

**Changes:**
- 2026-09-24: `OperationResult` moves to `app/contracts/` as a shared type of the plugin API.
- 2026-09-28: TASK-105 froze the dataclass, removed `map`/`bind`/`unwrap`/`unwrap_or`, made `message` optional on success, added `cause`, widened `retry_after` to `float` and fixed the stale docstring pointer; `provider`/`operation` deferred to TASK-105.1.
- 2026-09-28: TASK-105.1 dropped the `provider`/`operation` fields; adapters log that context as structured fields instead.
- 2026-09-28: TASK-105.2 added the `ErrorCode` registry; TASK-106 moved it with `OperationResult` and `OperationStatus` to `app/contracts/operations/` and deleted `app/infrastructure/operations/` with no re-export.
