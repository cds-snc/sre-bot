---
title: "Cloud Portability"
status: Accepted
type: Principle
tier: Tier-1
governance_domain: [application]
concerns: [architecture]
constrained_by: [decision-record-governance.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Cloud Portability

## Context and Problem Statement

The application must be runnable without modification across local development machines, containerized environments, and any cloud provider. When application code depends on where it runs — referencing provider-specific APIs, assuming specific runtime metadata, or embedding environment-coupled startup logic — moving the application to a different execution context requires code changes, not just configuration changes.

The core problem: **application code must not encode assumptions about its execution environment.** How configuration reaches the process, where logs go, what port to bind, and how external services are reached must all be resolvable at runtime without coupling the source code to any specific provider or deployment mechanism.

**Constraints:**

- This principle governs application code only. How a specific hosting platform fulfills these runtime contracts (e.g., how environment variables are injected, how logs are collected, how ports are exposed externally) is an operations concern outside the scope of this record.
- In-app integrations with external services (cloud storage, messaging, directory services) are in scope insofar as they must be structured so the concrete provider can be changed without modifying feature code.

**Non-goals:**

- This record does not prescribe secret management backends, CI/CD pipelines, container orchestration configuration, or cloud-specific deployment tooling.
- This record does not define the build, release, or run phases — those are distinct concerns addressed elsewhere.

## Considered Options

**Option 1: No explicit portability principle — handle ad hoc per feature**

Each feature or infrastructure integration decides independently how tightly it couples to its execution environment. No architectural constraint enforces decoupling.

**Option 2: Portability as a foundational application principle**

Establish an explicit, enforceable principle that prohibits application code from assuming its execution context, and requires that runtime contracts be satisfied through environment variables, Protocol abstractions, and standard I/O — regardless of where the application runs.

## Decision Outcome

**Chosen: Option 2 — Portability as a foundational application principle.**

Application code must satisfy all four portability contracts below. Any application code that violates a contract must be corrected before it can be considered compliant with this principle.

### Contract 1: Configuration via environment variables

All runtime configuration — including service endpoints, credentials references, feature flags, and tuning parameters — must be read from environment variables. Application code must not read configuration from provider-specific APIs (e.g., EC2 instance metadata, cloud-provider secret SDKs) at startup or runtime. The application is responsible for reading and validating its own environment; the hosting environment is responsible for supplying it.

This directly enacts Factor III of the Twelve-Factor App methodology: *"The twelve-factor app stores config in environment variables."*

### Contract 2: Logs to standard output

The application must emit all log output to `stdout` or `stderr`. It must not write to log files, cloud-provider logging APIs, or any other destination. Routing, aggregation, and storage of that output is the responsibility of the execution environment.

This directly enacts Factor XI of the Twelve-Factor App methodology: *"The twelve-factor app never concerns itself with routing or storage of its output stream."*

### Contract 3: Stateless process with external state

The application process must carry no state between requests. Any state that must persist (sessions, job status, locks) must be stored in an external backing service (database, cache, queue). The application must treat each backing service as an attached resource referenced by a URL or credentials supplied through environment variables — not as a co-located or provider-specific dependency.

This directly enacts Factors VI and IV of the Twelve-Factor App methodology: *"Execute the app as one or more stateless processes"* and *"Treat backing services as attached resources."*

### Contract 4: External service integrations via Protocol abstractions

Application code that integrates with external services (directory services, messaging platforms, storage, queuing) must program against a `typing.Protocol` interface. The concrete implementation (e.g., the specific AWS, Google, or Slack client) is injected at composition time. Feature code must not import concrete client classes directly.

This enacts the Ports and Adapters pattern (Hexagonal Architecture): the application defines a port (the Protocol); the concrete adapter (the SDK client) is wired in at the boundary. Replacing one cloud provider's SDK with another's requires only a new adapter, not changes to feature code.

## Consequences

**Positive:**

- The application can run locally with mocked or emulated services, in containers with injected environment, or on any cloud provider with equivalent configuration — without code changes.
- Feature code is decoupled from provider-specific SDKs, making it testable without cloud credentials and swappable as providers change.
- Contracts 1 and 2 enable any log aggregator or secrets manager to be used without application code involvement.

**Tradeoffs accepted:**

- All concrete provider integrations require an explicit Protocol definition and adapter class. This is additional structure up front, but it pays dividends in testability and replaceability.
- Configuration validation must happen at application startup via the `BaseSettings` layer, not lazily — this is a necessary consequence of Contract 1.

**Risks:**

- Protocol abstractions that are too narrow or too wide can create leaky adapters. Protocols must be defined at the level of application need, not shaped around a specific provider's API.

## Confirmation

Compliance is verified by:

- Code review: feature code must not import concrete SDK clients directly; all external integrations must go through a Protocol.
- Code review: no provider-specific environment introspection (e.g., `boto3.Session()` with implicit credential chain, cloud metadata endpoint calls) in application startup or request handling paths.
- Local development: the application must start and serve requests using only environment variables and local/emulated backing services — no cloud credentials required.

## Source References

1. The Twelve-Factor App
   - URL: <https://12factor.net/>
   - Accessed: 2026-05-01
   - Relevance: Factors III (Config), IV (Backing Services), VI (Processes), and XI (Logs) directly define the runtime contracts this principle enforces. The methodology's stated goal is "maximum portability between execution environments."

2. Hexagonal Architecture (Ports and Adapters) — Alistair Cockburn
   - URL: <https://alistair.cockburn.us/hexagonal-architecture/>
   - Accessed: 2026-05-01
   - Relevance: Defines the Ports and Adapters pattern: the application core communicates with external systems through abstract ports; concrete adapters implement those ports for specific technologies. This is the structural basis for Contract 4.

3. The Clean Architecture — Robert C. Martin
   - URL: <https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html>
   - Accessed: 2026-05-01
   - Relevance: "Source code dependencies can only point inwards." Infrastructure (frameworks, cloud SDKs, drivers) lives in the outer ring; application logic lives in the inner rings. Infrastructure details must not leak into application rules — the same constraint this principle enforces for provider coupling.

4. CNCF Cloud Native Definition v1.1
   - URL: <https://github.com/cncf/toc/blob/main/DEFINITION.md>
   - Accessed: 2026-05-01
   - Relevance: Defines cloud native as "loosely coupled systems" with "clear separation of concerns." Loose coupling between application workloads and the infrastructure they run on is foundational to the portability invariant this principle establishes.

5. Government of Canada Cloud Adoption Strategy
   - URL: <https://www.canada.ca/en/government/system/digital-government/digital-government-innovations/cloud-services/government-canada-cloud-adoption-strategy.html>
   - Accessed: 2026-05-01
   - Relevance: Principle 8 — "consider portability and interoperability of services when designing cloud-based solutions." Principle 7 — "develop an appropriate exit strategy before using cloud services." Both require application design to be separable from the hosting platform, which this principle enforces at the code level.

## Change Log

- 2026-05-08: Created as placeholder.
- 2026-05-08: Drafted with four portability contracts grounded in prior ADR research and Twelve-Factor methodology.
