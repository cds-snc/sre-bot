---
status: Accepted
date: 2026-07-06
applies: target
scope: Test layers, doubles, substitution, and gates.
---

# Testing

## Context

The suite lives at `app/tests/` (~320 files) with `unit/`, `integration/`, `smoke/` layers plus legacy trees; a second root-level `tests/architecture/` exists outside CI. The old record's core was strong; its unbuilt mechanisms (marker enforcement, provider clearing, coverage gate) made it aspirational.

## Decision

**One tree:** `app/tests/`. The root-level architecture test moves into it (import-linter supersedes most of it anyway — [toolchain.md](toolchain.md)).

**Three layers:**

- **Unit** (<50 ms): pure logic, Protocol fakes, no I/O. The bulk of the pyramid.
- **Integration** (<500 ms): components wired together with in-memory fakes for out-of-process deps ([cloud-portability.md](cloud-portability.md) fakes double here); HTTP via `httpx.AsyncClient` + `ASGITransport` against the real app with `dependency_overrides`. DynamoDB-Local is permitted for store-semantics tests, marked `slow`.
- **Smoke:** on-demand against real backends; never in the PR gate.

**Doubles, in preference order:** Protocol-conformant fake → stub → `MagicMock` (last resort, never for the subject under test). Mock at the Protocol seam, not the SDK.

**Substitution:** routes → `app.dependency_overrides`; direct-call consumers → the provider registry's clear-all autouse fixture + monkeypatch ([dependency-injection.md](dependency-injection.md)). Global env comes from per-test `monkeypatch.setenv`, not a pyproject env block that silently configures everything.

**Determinism:** no real time (freezegun is the blessed tool), no network, no ordering dependence. A flaky test is a bug with a ticket, not a retry.

**Gates:** `--strict-markers` with `unit/integration/smoke/slow/legacy` registered; coverage with `fail_under` at the current measured value, ratcheting up — never down; CI budget ten minutes; no soft-fail.

## Consequences

- The Protocol-fake investment pays twice (portability proof + fast tests).
- The `fail_under` ratchet makes 80% a floor that rises rather than a decorative target.

## Checks

- `pyproject`: `--strict-markers` in addopts; all markers registered; `fail_under` set.
- No root-level `tests/` tree outside `app/tests/`.
- The autouse provider-clearing fixture exists in the root `conftest.py`.

## Migration

Ticket: toolchain convergence (gates land with [toolchain.md](toolchain.md)'s CI work). Tolerated until closed: the root-level `tests/architecture/` tree, unregistered `slow` marker, no `--strict-markers`, no `fail_under`, no provider-clearing fixture (blocked on [dependency-injection.md](dependency-injection.md)'s registry).
