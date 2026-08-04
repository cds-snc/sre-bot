---
status: Accepted
date: 2026-07-06
applies: target
scope: In-process domain events between features.
---

# Domain Events

## Context

Features announce facts ("access request approved") that other features react to without direct coupling. This is in-process, best-effort notification — distinct from the durable queue ([reliability.md](reliability.md)), which is for work that must survive a crash. A cross-package hand-off that advances another feature's durable state is neither a notification nor free-standing work — it is a **workflow step** ([approvals.md](approvals.md)) delivered over the queue, not an event. The old design selected blinker, then forbade every blinker dispatch feature and hand-rolled the rest around it; the implementation then disabled the weak references the selection was justified by and added a thread pool the record never mentioned. We stop pretending.

## Decision

**The design is an owned, minimal dispatcher** in `app/infrastructure/events/` — a registry mapping event types to subscriber lists, no blinker. But it is **built on demand, not speculatively.** Today the app has *no* genuine best-effort cross-feature reactor: the one cross-package hand-off (`access/sync → access/request`) is durable workflow work that moves to the queue ([approvals.md](approvals.md)), and operator alerts call the notifications capability directly. So we **retire the current misused dispatcher now** and land the owned typed dispatcher **with its first real consumer** — the same discipline the durable queue follows ([reliability.md](reliability.md)). When built, it obeys:

- **Events are frozen dataclasses**, named as past-tense facts (`AccessRequestApproved`), carrying value types only. Publishing is keyed by the event *class*, not strings.
- **Facts, not commands.** A producer must not care whether zero or ten subscribers exist. If the producer needs the work to happen, that's the queue, not an event.
- **Synchronous, inline delivery** on the publisher's task, in registration order — so `contextvars` (correlation, locale) flow into subscribers for free. Async subscribers are awaited; a slow subscriber is a review problem, not a threading problem.
- **Per-subscriber error isolation:** one subscriber's exception is logged (with correlation) and does not stop the others or the producer.
- **Publish after commit:** events describing persisted state changes fire after the write succeeds.
- Subscription happens via a hookspec at startup ([plugins.md](plugins.md)); the subscriber table is frozen at yield.

## Consequences

- Deferring the build avoids a speculative pub/sub with zero subscribers; when a genuine reactor appears, ~50 lines of owned code (ordering, isolation, context inheritance tested in our suite) replace what was a dependency used as a dict — no blinker. The alternative, building the ~50-line dispatcher now, is cheap but contradicts the anti-speculation posture we apply everywhere else.
- Inline delivery means a blocking subscriber blocks the producer — accepted at current scale, revisit if event volume grows.
- The dispatcher has **no external backing by design** — it is in-process transport with no durable state and no vendor to substitute, so [cloud-portability.md](cloud-portability.md) scopes it out of the fake contract; durability is the queue's job, never a "backed dispatcher."
- Divergences to fix: current dispatcher is string-keyed, blinker-backed, and uses a `ThreadPoolExecutor` (which breaks context inheritance). Separately, `access/sync` pushes `SYNC_COMPLETED` / `SYNC_FAILED` through `dispatch_background` to advance an access request's durable state — a command-styled-as-event that moves off the bus onto the approval workflow's queue-borne step ([approvals.md](approvals.md), [reliability.md](reliability.md)).

## Checks

- Dispatcher tests: ordering, isolation, contextvar inheritance into subscribers, async subscriber support.
- grep: no `blinker` imports after migration; no string event names at publish sites.

## Migration

Ticket: retire the blinker-backed string-keyed dispatcher and its `ThreadPoolExecutor` path now; move `SYNC_COMPLETED` / `SYNC_FAILED` onto the approval workflow's queue step and operator alerts onto the notifications capability. The owned typed dispatcher is deferred until the first genuine best-effort cross-feature reactor exists (build-on-demand). Tolerated until closed: the current blinker-backed dispatcher.
