---
title: "Technology Selection: Blinker"
status: Accepted
type: Selection
tier: Tier-2
governance_domain: [application]
concerns: [architecture]
constrained_by: [event-dispatch.md, layered-architecture.md, infrastructure-service-classification.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Technology Selection: Blinker

## Context and Problem Statement

The event-dispatch standard ([event-dispatch.md](event-dispatch.md)) defines an in-process domain-event dispatcher exposed to features as a Protocol with three documented operations (`publish`, `subscribe`, registry freeze at lifespan yield) and a contract with explicit guarantees (per-subscriber error isolation, deterministic delivery order, correlation-context inheritance via `ContextVar`, weak references to subscribers, no persistence). The standard does not pick the library that backs the dispatcher; it leaves the seam at the facade.

The problem this record addresses: **which Python library does the dispatcher facade wrap, and on what grounds?** A purpose-built library is preferred over a hand-rolled signal registry: the maintenance cost of a registry, weak-reference table, and async/sync invocation logic falls outside the application's domain. The selection criteria are:

1. **Fit with the standard's Protocol** — the library must expose primitives the facade can compose into the documented operations without re-implementing them.
2. **Async-aware delivery** — `publish` must invoke `async def` subscribers correctly (await, not schedule-and-forget). The library either supports async natively or composes cleanly with `asyncio`.
3. **Per-subscriber invocation surface** — the facade applies the per-subscriber error boundary itself ([event-dispatch.md](event-dispatch.md)). The library must allow iterating subscribers (or its equivalent), not only a bulk-send method that swallows the iteration.
4. **Weak-reference subscriber storage** — the standard expects subscribers to be garbage-collectable when their owning module is unloaded; explicit unsubscribe is not required.
5. **Stewardship and maturity** — the library is maintained, packaged on PyPI, documented, and used at scale by other open-source projects whose lifecycle resembles ours.
6. **Tier-2 economics** — per [package-management.md](package-management.md) and the application's general posture, a small, focused library beats a hand-rolled component.

**Constraints:**

- The library is imported only inside `app/infrastructure/events/`. Features depend on the dispatcher Protocol, not the library. Substitution is bounded to the facade module.
- The library's API surface must compose with the application's `ContextVar` propagation. Subscribers are awaited or called inline on the producer's task; libraries that schedule subscribers on detached tasks (and so break context inheritance) are disqualified.
- Wheel availability for the application's Python version (3.13) on the deployment target. Source-only distributions that compile native extensions on install are tolerated but not preferred.

**Non-goals:**

- This record does not redefine any rule from the event-dispatch standard. Where the library and the standard appear to disagree, the standard wins; the facade reconciles.
- This record does not pick the cross-process bus or any durable-queue technology — that is owned by [message-queuing.md](message-queuing.md).
- This record does not pin a specific minor version. The rule is "current stable on PyPI"; minor-version pinning is a `pyproject.toml` concern.

## Considered Options

**Option 1 — Blinker.** The signaling library used by the Pallets ecosystem (Flask, Quart). Exposes `Signal` objects with `connect` (subscribe), `send` (synchronous bulk-send), `send_async` (async-aware bulk-send), weak-reference storage by default, and per-`Signal` deduplication of receivers. Native async support since 1.5.

**Option 2 — PyPubSub.** A long-running pub/sub library with a topic-name-based subscription model and configurable error handling. Synchronous-only (no native `async` support); async receivers would require a wrapper executor.

**Option 3 — Pyee.** A Node.js-flavored event-emitter library with `on` / `emit` semantics. Async-aware; smaller maintenance footprint and less Python-idiomatic API than Blinker.

**Option 4 — Hand-rolled signal registry.** The application maintains its own dictionary of `event_class -> list[subscriber]`, weak-reference table, and async-detection logic. No external dependency.

## Decision Outcome

**Chosen: Option 1 — Blinker.**

Blinker satisfies every selection criterion. It exposes `Signal` objects whose iteration surface (`signal.receivers_for(sender)`) lets the facade apply per-subscriber error boundaries directly, rather than delegating to `signal.send()` whose first-exception-stops semantics would defeat the standard's error-isolation contract. Native `async` support since 1.5 means async subscribers are awaited correctly when invoked through the facade's loop. Weak-reference receiver storage is the default. The library is small (single file, no native code), maintained under the Pallets project umbrella, and used at scale by Flask and Quart. PyPubSub lacks native async; Pyee is workable but is Node-idiomatic and smaller in stewardship; hand-rolling violates the application's posture against re-implementing capabilities that an existing library provides for free.

### What the facade uses, and what it does not

The facade is the **only** module that imports `blinker`. Inside, it uses:

- **`blinker.Signal`** — one instance per registered event type (keyed in a private dict on the facade). Subscribers are registered with `signal.connect(subscriber)`; the facade does not expose `Signal` objects to features.
- **`signal.receivers_for(...)`** — the iteration surface used by the facade's dispatch loop. Each receiver is invoked inside the facade's per-subscriber `try/except`; exceptions are converted to `event_subscriber_failed` log records and not re-raised.
- **Weak-reference storage** — the default. The facade does not pin subscribers; module unloading (in tests) garbage-collects subscriber callables and they are dropped from the signal automatically.

The facade does **not** use:

- **`signal.send()`** — its first-receiver-raises-stops-the-rest semantics conflict with the standard's per-subscriber error-isolation rule.
- **`signal.send_async()`** — same reason. The facade implements its own async dispatch loop, awaiting each `async def` subscriber inside its own boundary.
- **Sender-keyed subscriptions** (Blinker's `connect(receiver, sender=...)` filtering). The standard binds subscribers to event *types*, not to sender objects. The facade keys signals by event class; sender-filtering is not exposed.

This pattern — wrap, iterate, isolate — is the standard mechanism by which the facade reconciles a useful library against a stricter application contract.

### Library version pinning

`pyproject.toml` requires `blinker >= 1.9` (the stable release that consolidated async support). Minor-version upgrades are managed through the dependency-bump workflow ([package-management.md](package-management.md)); breaking-change releases are reviewed.

### Substitution path

If a future need requires a different backing library (a higher-throughput signal mechanism, a native asyncio event-emitter), the substitution is bounded to:

1. Replace the Blinker import inside `app/infrastructure/events/dispatcher.py` with the new library's primitives.
2. Update the implementation of `publish` and `subscribe` to wrap the new library's iteration surface.
3. Re-run the facade's contract tests (per-subscriber error isolation, async support, ordering, weak refs, depth limit).

No feature code, no producer code, no subscriber code changes. The Protocol is the seam.

### Pros and cons of the options

**Blinker.** Good: native async; fits the facade's iterate-and-isolate pattern; weak refs by default; Pallets stewardship; small footprint. Bad: one-feature-per-`Signal`-instance pattern means the facade maintains a private signal map (acceptable indirection).

**PyPubSub.** Good: long history; topic-tree filtering. Bad: synchronous-only; async support is an external wrapper; no first-class iteration surface that supports per-subscriber error boundaries; the topic-tree model is more than the standard requires.

**Pyee.** Good: async-aware; small. Bad: Node-flavored API (`on`, `emit`, `once`) doesn't read as Python-idiomatic; smaller maintainer base; less precedent in mature Python web frameworks.

**Hand-rolled.** Good: no dependency. Bad: re-implements weak-reference storage, async detection, and iteration surface; ongoing maintenance cost falls on the application; correctness regressions in pub/sub plumbing are easy to introduce and hard to detect; violates the posture of preferring small, focused libraries over hand-rolled components.

## Consequences

**Positive:**

- The facade is small. Most of its lines are the per-subscriber error boundary and the async/sync dispatch dispatch — not the registry or the weak-ref logic.
- Blinker's stewardship under Pallets is durable; security and bug-fix updates flow through the same channel as Flask/Quart updates.
- Async migration of subscribers is a per-subscriber change, not a library change. The facade already awaits `async def` subscribers correctly.

**Tradeoffs accepted:**

- One additional runtime dependency. Acceptable: the alternative is hand-rolled code with the same surface area, paid in maintenance instead of in the dependency line.
- The facade does not delegate to `signal.send()`, so the application pays a small Python-level loop cost per publish. Acceptable: subscriber count per event is small (typically 1–4), and the explicit iteration is required by the error-isolation contract anyway.

**Risks and mitigations:**

- **A future Blinker release changes weak-reference semantics or signal-deduplication behavior.** The facade's contract tests cover both. A breaking-change release is reviewed before bump.
- **Subscriber count grows large enough that per-publish iteration cost matters.** Mitigation: subscriber-density thresholds are observable through telemetry (subscriber count per event); a pattern of "many subscribers per event" is a re-design signal, not a library-substitution signal.

## Confirmation

Compliance is verified by:

- **Code review.** `import blinker` appears only in `app/infrastructure/events/dispatcher.py`. No `from blinker import Signal` (or equivalent) inside feature code.
- **Static analysis.** An import-rule check forbids `blinker` outside the facade module path.
- **Contract tests.** The facade's tests assert: per-subscriber error isolation, deterministic order, correct sync/async dispatch, weak-ref drop on subscriber GC, depth-limit enforcement.
- **Dependency declaration.** `pyproject.toml` declares `blinker >= 1.9` under the application's runtime dependencies; the version is reviewable in the manifest.

## Source References

1. Blinker — Project README (PyPI)
   - URL: <https://pypi.org/project/blinker/>
   - Accessed: 2026-05-08
   - Relevance: Establishes Blinker's stewardship (Pallets ecosystem), packaging maturity, and Python version compatibility (current: 3.8+). Grounds the maturity-and-stewardship selection criterion.

2. Blinker — Documentation
   - URL: <https://blinker.readthedocs.io/en/stable/>
   - Accessed: 2026-05-08
   - Relevance: Documents `Signal`, `connect`, `disconnect`, `send`, `send_async`, weak-reference receiver storage, and the `receivers_for(sender)` iteration surface. Grounds the rule that the facade iterates receivers explicitly to apply its per-subscriber error boundary.

3. Pallets — Project Overview
   - URL: <https://palletsprojects.com/>
   - Accessed: 2026-05-08
   - Relevance: Confirms Blinker's stewardship under the Pallets project umbrella, alongside Flask, Werkzeug, Jinja, and Click. Grounds the long-term-maintenance selection criterion.

4. PyPubSub — Documentation
   - URL: <https://pypubsub.readthedocs.io/en/stable/>
   - Accessed: 2026-05-08
   - Relevance: Documents the topic-name subscription model and the absence of native async support. Grounds the rejection of PyPubSub on async-awareness criterion.

5. Pyee — Project README
   - URL: <https://github.com/jfhbrook/pyee>
   - Accessed: 2026-05-08
   - Relevance: Documents Pyee's Node-style event-emitter API (`on`, `emit`, `once`) and async-aware extensions. Grounds the comparison and the "less Python-idiomatic" assessment relative to Blinker.

6. Python — `contextvars` (PEP 567)
   - URL: <https://docs.python.org/3/library/contextvars.html>
   - Accessed: 2026-05-08
   - Relevance: Documents `ContextVar` inheritance semantics: values bound in a task are visible to inline and `await`-chained code on the same task. Grounds the rule that the facade awaits subscribers on the producer's task (rather than detaching them via `create_task`) so correlation context propagates automatically.

## Change Log

- 2026-05-08: Created. Selects Blinker (`>= 1.9`) as the backing library for the in-process event-dispatch facade. Establishes that the facade is the only module that imports the library; iterates receivers via `signal.receivers_for(...)` rather than delegating to `signal.send()`; awaits async subscribers on the producer's task to preserve `ContextVar` inheritance; relies on Blinker's default weak-reference storage. Documents the substitution path: a future library swap is bounded to the facade module without touching producer or subscriber code.
