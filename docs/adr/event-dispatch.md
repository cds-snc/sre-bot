---
title: "Event Dispatch"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [architecture]
constrained_by: [layered-architecture.md, plugin-registration-discovery.md, infrastructure-service-classification.md, application-lifecycle.md, logging-observability.md, cross-channel-correlation.md, type-boundaries.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Event Dispatch

## Context and Problem Statement

The application has cross-cutting domain notifications: a feature performs work and several other code paths want to react — write an audit record, enqueue a notification, refresh a derived projection, emit a metric. Coupling each of these to the producing handler (direct calls, registries that the producer maintains) defeats the per-feature isolation that the package structure establishes; coupling them through the message-queue path is too heavy for events that never need to leave the process.

The problem this record addresses: **what is the standard pattern for in-process domain-event dispatch — its registration shape, its delivery semantics, its error-isolation contract, and the boundary between it and the cross-process queue path?** The answer determines:

1. Whether features can react to events from other features without a circular-import or central-registry pattern.
2. Whether the dispatcher's failure mode is "fail one subscriber" or "fail the producer."
3. Whether correlation context (request ID, transport context) flows through a domain event or has to be threaded as a parameter.
4. Whether a future migration to a durable, cross-process bus (queues, streams) requires touching producer code or just the subscriber side of an event.

**Constraints:**

- The application is a single Python process (with `desired_count >= 2`, multiple identical processes; per [cloud-portability.md](cloud-portability.md), no cross-process state-sharing is assumed). Events delivered through this dispatcher are in-process only — they do not cross the task boundary.
- Plugin registration is via Pluggy entry-points and `hookimpl`s ([plugin-registration-discovery.md](plugin-registration-discovery.md)); registration is fail-fast and frozen at lifespan yield. The dispatcher's subscription model must align.
- Module-level side-effects are prohibited at import time ([import-governance.md](import-governance.md)). Handler registration must run during a lifespan phase, not as a decorator side-effect at import.
- Service-layer outcomes are returned as the closed five-status envelope ([operation-result-pattern.md](operation-result-pattern.md)). Domain events are *notifications about completed work*, not requests for work; the dispatcher does not return an envelope.
- Log records carry correlation context bound to a `ContextVar` ([logging-observability.md](logging-observability.md), [cross-channel-correlation.md](cross-channel-correlation.md)). Subscriber log records must carry the producer's correlation context.
- Type contracts at module boundaries are vendor-neutral ([type-boundaries.md](type-boundaries.md)); subscriber signatures and event payload types are application-owned, not library-shaped.

**Non-goals:**

- This record does not pick the library; the library choice is a Selection record ([technology-blinker.md](technology-blinker.md)). The contract here is what the library must provide; substitution is permitted as long as the contract holds.
- This record does not define the cross-process bus (durable queues, dead-letter handling, message retention). That posture is owned by [message-queuing.md](message-queuing.md).
- This record does not catalogue the application's actual event types. Events are added through normal review when a domain interaction justifies them; the catalogue is observable from the registry, not from this document.
- This record does not specify the platform-transport event-handling chain (Slack Bolt's `.command()` / `.action()` decorators, an HTTP-route's request → handler chain). Those are transport concerns governed by their respective records.

## Considered Options

**Option 1 — In-process pub/sub through an infrastructure-owned dispatcher facade, with subscriber registration via Pluggy hookspec at lifespan phase 4.** Producers call `dispatcher.publish(event)`; subscribers register through `register_event_subscribers(dispatcher)` during phase 4. The dispatcher iterates subscribers in a deterministic order, invokes each inside its own error boundary, and returns nothing to the producer. The library backing the dispatcher is hidden behind the facade; features do not import the library directly.

**Option 2 — Direct calls between features.** A feature that wants to notify others imports their entry points and calls them. No dispatcher; no registration mechanism; no facade. Features know their subscribers by name.

**Option 3 — Decorator-time subscription.** Subscribers register at import via `@on_event("domain.entity.action")`. The library performs the registration as an import side-effect.

**Option 4 — Use the cross-process queue for everything.** Every event is published to SQS (or equivalent); subscribers are queue consumers. No in-process path.

## Decision Outcome

**Chosen: Option 1 — in-process pub/sub through an infrastructure-owned dispatcher facade, with subscriber registration via Pluggy hookspec at lifespan phase 4.**

This is the only option that combines (a) subscriber-side decoupling (a producer publishes without naming subscribers; a subscriber subscribes without modifying producer code), (b) deterministic, fail-fast registration (subscribers known at lifespan yield, not added on a running process), (c) bounded blast radius (one subscriber raising does not affect other subscribers or the producer), and (d) library-substitution latitude (the library is hidden behind a Protocol the facade implements). Direct calls (Option 2) reverse the coupling polarity but keep features tangled. Decorator-time subscription (Option 3) breaks the no-import-side-effects rule and pre-dates the lifespan discovery contract. Queue-for-everything (Option 4) imposes durability cost and operational surface on events that never need either; the queue is the right tool for cross-process delivery, not for in-process notification.

### Where the dispatcher lives

The dispatcher is a **shared infrastructure capability** ([infrastructure-service-classification.md](infrastructure-service-classification.md): Path A, Shared). One implementation in `app/infrastructure/events/`, one Protocol exported to consumers, one DI-injected handle.

```text
app/infrastructure/events/
    __init__.py          # public surface: EventDispatcher Protocol, Event base type
    dispatcher.py        # concrete facade implementation
    settings.py          # any settings the facade consumes (currently none)
```

Features depend on the Protocol, not the implementation; they do not import the backing library. The library choice is replaceable at the implementation seam without touching subscriber or producer code.

### Event shape

An event is a **typed value object** owned by the producing feature. Its module path is part of the producer's package; its name is a dotted namespace string of the form `<domain>.<entity>.<action>` — for example, `incident.ticket.opened`, `access.request.approved`, `aws.identity.provisioned`.

```python
@dataclass(frozen=True, slots=True)
class IncidentOpened:
    incident_id: str
    opened_by: str
    opened_at: datetime
    # …feature-owned fields…

    name: ClassVar[str] = "incident.ticket.opened"
```

Rules:

- Event types are immutable, pickling-friendly value objects (`frozen=True`). Subscribers must not mutate them.
- Event types do not carry transport-shaped fields (HTTP request objects, Slack Bolt context, raw payloads). They carry the *domain meaning* of what happened. Transport-shaped context, when needed by a subscriber, is reconstituted from correlation context, not threaded through the event.
- Event class names use the noun-perfect-tense form (`IncidentOpened`, `RequestApproved`); the dotted `name` is the address used by subscribers and observability.
- Events are *facts*, not commands. They name something that has already happened. A handler that wants to *cause* something asks the service layer; it does not publish a request-shaped event.

### Producer side

A producer publishes after the domain transition has been committed:

```python
dispatcher.publish(IncidentOpened(incident_id=..., opened_by=..., opened_at=...))
```

Rules:

- `publish` returns nothing. There is no envelope, no count of subscribers reached, no synchronous failure surface for the producer to react to.
- A producer does not know which subscribers exist. Adding a subscriber for an event does not require any change in the producer's code.
- Publication happens *after* the domain entity's persistence has been confirmed. An event published before the write succeeds creates a state in which subscribers can observe a fact that does not exist; this is prohibited.
- A handler that publishes an event is still subject to its handler-shape rules ([feature-handler-standard.md](feature-handler-standard.md)); publication is one of its observable side-effects, not a control-flow exit.

### Subscriber side

Subscribers register through a Pluggy hookspec invoked once at lifespan **phase 4 (feature activation)**:

```python
@hookimpl
def register_event_subscribers(dispatcher: EventDispatcher) -> None:
    dispatcher.subscribe(IncidentOpened, _on_incident_opened)
    dispatcher.subscribe(RequestApproved, _on_request_approved)
```

Rules:

- Subscriber registration is a metadata operation. It does not start work, open connections, or warm caches.
- The subscriber callable is a regular function or coroutine function with a fixed signature: `(event: SomeEventType) -> None` (sync) or `async def …(event: SomeEventType) -> None`. It returns nothing.
- The subscriber callable does not raise into the dispatcher (see "Error isolation" below); but its body is otherwise unconstrained — it may call services, publish further events (subject to depth limits, see "Avoiding cycles"), enqueue messages, etc.
- A subscriber that needs to do durable, cross-process work does the work via the message-queue path ([message-queuing.md](message-queuing.md)) — it consumes the in-process event, then enqueues to the durable queue. The dispatcher does not become a queue.
- The registry is frozen at lifespan yield. No `subscribe` or `unsubscribe` calls run on a serving process.

### Delivery semantics

- **Synchronous by default.** `publish` invokes each subscriber inline, in registration order, on the producer's call stack. The producer's request returns when all subscribers have run (modulo per-subscriber error boundary, see below).
- **Async-aware.** A subscriber declared as `async def` is awaited by the dispatcher. A sync subscriber is called directly. Producers do not branch on subscriber shape; the facade does.
- **Best-effort.** Delivery is in-process and process-local. A crash of the producing task between publish and subscriber execution loses the event. Events that *must* survive process death travel through the durable queue, not this dispatcher.
- **No persistence.** The dispatcher does not buffer, replay, or store events. There is no event log; observability of events is via the structured log records subscribers emit.
- **Single delivery per process.** Each subscriber runs once per `publish`. With `desired_count >= 2`, a single domain event published in one task is delivered only to that task's subscribers. If an effect needs to be cross-task, the durable queue is the path; a subscriber that "fans out" to N tasks is a misuse.

### Error isolation

The facade's dispatch loop wraps each subscriber invocation in its own error boundary:

- A subscriber that raises produces a `event_subscriber_failed` structured log record carrying `event_name`, `subscriber_name`, `error_type`, `error_message`, plus the standard correlation context. The redaction processor ([data-redaction-policy.md](data-redaction-policy.md)) is in effect.
- The exception is **not** re-raised into the producer's call stack. The producer's transition has already been committed; a downstream notification failure is an operational concern, not a domain failure.
- Subsequent subscribers on the same event are still invoked. One subscriber's failure does not cascade.
- The library backing the facade is *not relied on* for this property. Many in-process pub/sub libraries propagate the first subscriber's exception and skip the rest; the facade does not delegate to the library's bulk-send method, it iterates subscribers and applies the boundary itself.

### Correlation context

Subscriber log records inherit the producer's correlation context automatically. The mechanism:

- The application binds correlation IDs (request ID, trace context) to a `ContextVar` at request entry ([cross-channel-correlation.md](cross-channel-correlation.md), [logging-observability.md](logging-observability.md)).
- `ContextVar` values are inherited by code executing in the same task.
- A synchronous subscriber inherits trivially. An `async` subscriber inherits because the dispatcher awaits it on the producer's task; it does not spawn a detached task.
- Subscribers do not receive correlation IDs as parameters. They appear in `structlog`'s context-vars processor in subscriber log records the same way they appear in any other log record.

### Avoiding cycles

The dispatcher does not detect cycles in event publication. Operationally, cycles are prevented by:

- The "events are facts, not commands" rule. A subscriber to `incident.ticket.opened` whose body publishes `incident.ticket.opened` is a logic bug; it falls out of code review.
- A configurable depth limit (default 4) on nested `publish` calls within a single producer-rooted call stack. The facade tracks publish depth in a `ContextVar`; a publish at depth > limit raises a `EventDispatchDepthExceeded` *into the producer*, on the assumption that further reentry is a defect rather than an isolated subscriber failure. The exception's message names the chain.

### What this record does not change

- The plugin registration mechanism (entry-points, frozen registries, fail-fast) remains authoritative; this record adds one hookspec to the contract.
- The handler shape (`feature-handler-standard.md`) remains authoritative; publishing an event is one of a handler's permitted side-effects, governed by the rule that publication follows commit.
- The cross-process bus (`message-queuing.md`) is unchanged. Subscribers that need to propagate effects across tasks enqueue from inside their body; they do not extend this dispatcher.
- The observability vocabulary remains the structured log model defined by `logging-observability.md`. Events do not introduce a parallel telemetry channel.

## Consequences

**Positive:**

- A new subscriber on an existing event is one hookimpl line in the subscribing feature; no edits to the producer. Cross-feature reactions are zero-coupling on the producer side.
- Subscriber failures are localized: one failed subscriber on `IncidentOpened` does not skip the audit subscriber or break the request that produced the event.
- Library substitution is bounded to the facade implementation. A future replacement (different library, different transport) is a single-file change.
- Correlation context flows automatically; subscribers do not need to thread request IDs through their parameters.
- The boundary between in-process and cross-process is explicit: subscribers that need durability, retry, or cross-task delivery enqueue from their body. The dispatcher is not asked to be a queue.

**Tradeoffs accepted:**

- Synchronous, in-process delivery means a slow subscriber lengthens the producer's response time. Acceptable: subscribers are short, and the subscriber that needs to do heavy work enqueues a queue message and returns.
- A process crash between publish and subscriber execution loses the event. Acceptable: events that cannot tolerate this are queue messages, not in-process events. The boundary is explicit.
- The depth-limit rule occasionally fires on legitimately nested chains. Acceptable: the limit is high enough that legitimate chains do not hit it, and the failure surfaces a defect rather than hiding it.

**Risks and mitigations:**

- **A subscriber publishes a downstream event in a long-running chain.** The producer's response time accumulates the chain's cost. *Mitigation:* code review flags chains that exceed two levels; the depth-limit setting is calibrated to surface accidental deep chains.
- **A subscriber blocks on I/O without a timeout.** The producer stalls. *Mitigation:* subscribers calling external services use the same timeout discipline as handlers; review enforces.
- **A library upgrade changes delivery ordering.** Subscribers that depend on order break. *Mitigation:* the facade defines order as registration order and tests the property; library substitution is governed by the Selection record, not silent dependency-bumping.
- **An async subscriber escapes its task via `asyncio.create_task` and outlives the producer.** Correlation context may be lost, lifespan shutdown may not see it. *Mitigation:* subscribers do not detach. If a subscriber needs fire-and-forget execution, it enqueues to the message queue.

## Confirmation

Compliance is verified by:

- **Code review.** No `import blinker` (or any backing library) outside `app/infrastructure/events/`. No `@dispatcher.subscribe` decorator at module level. No `EventDispatcher` instantiation outside the composition root. Subscribers' bodies match the documented shape (no return value; no raise into producer).
- **Static analysis.** A check forbids the backing library's import path outside the facade module. A check forbids module-level invocation of `dispatcher.subscribe(...)`.
- **Tests.** A unit test asserts that registering two subscribers, one of which raises, results in both being invoked and the producer not seeing the exception. A test asserts that subscriber log records carry the producer's correlation IDs. A test asserts the depth limit fires on a deliberate cycle.
- **Boot test.** After phase 4, the registry contains exactly the expected subscriber set; a feature whose entry-point is missing causes the test to flag the gap.

## Source References

1. Blinker — Documentation
   - URL: <https://blinker.readthedocs.io/en/stable/>
   - Accessed: 2026-05-08
   - Relevance: Documents `Signal`, `connect`, `send`, `send_async`, weak-reference receiver storage, and per-receiver invocation. Grounds the implementation seam used by the facade and the rule that the facade iterates receivers explicitly rather than delegating dispatch wholesale.

2. Pluggy — Hook Specifications and Implementations
   - URL: <https://pluggy.readthedocs.io/en/stable/>
   - Accessed: 2026-05-08
   - Relevance: Documents the hookspec/hookimpl contract used to register subscribers at lifespan phase 4. Establishes that hooks are called by the host once per phase, with all registered implementations invoked in a deterministic order.

3. Python — `contextvars` (PEP 567)
   - URL: <https://docs.python.org/3/library/contextvars.html>
   - Accessed: 2026-05-08
   - Relevance: Documents the `ContextVar` semantics: a value bound in a task is visible to inline code and to coroutines awaited on the same task, but isolated across `asyncio.create_task` boundaries. Grounds the rule that subscribers inherit correlation context automatically when invoked inline by the facade.

4. Martin Fowler — Domain Event
   - URL: <https://martinfowler.com/eaaDev/DomainEvent.html>
   - Accessed: 2026-05-08
   - Relevance: Defines a domain event as "an event that captures things that happen which are of interest to a domain expert." Grounds the "events are facts, not commands" rule and the perfect-tense naming convention (`IncidentOpened`, not `OpenIncident`).

5. Microsoft Learn — Domain Events vs. Integration Events
   - URL: <https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/domain-events-design-implementation>
   - Accessed: 2026-05-08
   - Relevance: Distinguishes in-process domain events (transactional with the work that produced them) from cross-process integration events (durable, retryable, eventually consistent). Grounds the boundary between this dispatcher's scope and the message-queue path: domain events stay in-process; cross-task effects are queue messages.

6. AWS Builders' Library — Avoiding Insurmountable Queue Backlogs
   - URL: <https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/>
   - Accessed: 2026-05-08
   - Relevance: Argues that durable queueing has operational cost (backlog management, dead-letter handling, retry policy) that should not be paid for events that are inherently in-process. Grounds the explicit non-goal of using the queue path for events that have no cross-process consumer.

7. The Twelve-Factor App — Concurrency (Factor VIII)
   - URL: <https://12factor.net/concurrency>
   - Accessed: 2026-04-29
   - Relevance: Establishes that the application runs as N stateless processes and that cross-process state-sharing is not assumed. Grounds the rule that in-process events are delivered only within the publishing task's process; cross-process delivery is the queue's job.

## Change Log

- 2026-05-08: Created. Establishes an in-process domain-event dispatcher as a shared infrastructure capability behind a facade Protocol; subscribers registered via the `register_event_subscribers` hookspec at lifespan phase 4; events as immutable noun-perfect-tense value objects with dotted-namespace addresses; synchronous, in-process, best-effort delivery with per-subscriber error isolation; correlation context inherited via `ContextVar`; explicit boundary between in-process events (this record) and cross-process delivery (message-queuing.md). Defers the library choice to technology-blinker.md and the durable-queue mechanics to message-queuing.md.
