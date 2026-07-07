---
status: Accepted
date: 2026-07-06
applies: target
scope: In-process domain events between features.
---

# Domain Events

## Context

Features announce facts ("access request approved") that other features react to without direct coupling. This is in-process, best-effort notification — distinct from the durable queue ([reliability.md](reliability.md)), which is for work that must survive a crash. The old design selected blinker, then forbade every blinker dispatch feature and hand-rolled the rest around it; the implementation then disabled the weak references the selection was justified by and added a thread pool the record never mentioned. We stop pretending.

## Decision

**An owned, minimal dispatcher** in `app/infrastructure/events/` — a registry mapping event types to subscriber lists. No blinker (dependency removed with the rewrite). Rules:

- **Events are frozen dataclasses**, named as past-tense facts (`AccessRequestApproved`), carrying value types only. Publishing is keyed by the event *class*, not strings.
- **Facts, not commands.** A producer must not care whether zero or ten subscribers exist. If the producer needs the work to happen, that's the queue, not an event.
- **Synchronous, inline delivery** on the publisher's task, in registration order — so `contextvars` (correlation, locale) flow into subscribers for free. Async subscribers are awaited; a slow subscriber is a review problem, not a threading problem.
- **Per-subscriber error isolation:** one subscriber's exception is logged (with correlation) and does not stop the others or the producer.
- **Publish after commit:** events describing persisted state changes fire after the write succeeds.
- Subscription happens via a hookspec at startup ([plugins.md](plugins.md)); the subscriber table is frozen at yield.

## Consequences

- ~50 lines of owned code replace a dependency we were using as a dict; the behavior contract (ordering, isolation, context inheritance) is now tested in our suite instead of assumed of a library.
- Inline delivery means a blocking subscriber blocks the producer — accepted at current scale, revisit if event volume grows.
- Divergences to fix: current dispatcher is string-keyed, blinker-backed, and uses a `ThreadPoolExecutor` (which breaks context inheritance).

## Checks

- Dispatcher tests: ordering, isolation, contextvar inheritance into subscribers, async subscriber support.
- grep: no `blinker` imports after migration; no string event names at publish sites.

## Migration

Ticket: dispatcher rewrite. Tolerated until closed: blinker-backed string-keyed dispatcher.
