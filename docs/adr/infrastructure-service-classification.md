---
title: "Infrastructure Service Classification"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [architecture]
constrained_by: [layered-architecture.md, type-boundaries.md, dependency-injection.md, client-adapter-responsibilities.md, client-module-placement.md, configuration-ownership.md, feature-package-structure.md, import-governance.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Infrastructure Service Classification

## Context and Problem Statement

The application talks to many external systems — cloud-storage backends, queues, identity stores, chat platforms, mail providers, identity providers, and others. Some of those external systems are interchangeable from the application's point of view (the application needs *storage*, and any cloud's blob store would do); others are not (the application talks to Slack *because it is Slack*, and a different chat platform would not satisfy the same purpose). Some integrations are consumed by many features (Slack, storage); others are consumed by exactly one feature (a feature-specific access-provisioning sync against a specific cloud's identity store).

The corpus has been using a Path A vs Path B distinction informally since `layered-architecture.md` introduced it. Several already-accepted records (`client-adapter-responsibilities.md`, `client-module-placement.md`, `configuration-ownership.md`, `feature-package-structure.md`, `import-governance.md`, `transport-slack.md`) lean on the distinction without a single record formalizing the criteria, the layout consequences, and the rules for changing classification over time.

The problem this record addresses: **what is the canonical taxonomy for classifying an outbound integration in this codebase, and what does each classification imply for Protocol design, file placement, composition scope, and migration when the classification changes?** The answer determines:

1. Whether a contributor adding a new integration can decide its placement (`app/infrastructure/<service>/` vs `app/packages/<feature>/adapters/<provider>.py`) by reading one rule, or must consult prior art ad hoc.
2. Whether the Protocol exposed for the integration is shaped by the application's *capability* needs (vendor-portable) or by the *external system's* native operations (vendor-bound).
3. When (and how) a feature-local adapter should be promoted to a shared infrastructure service so that a second consumer doesn't have to copy.
4. How the classification interacts with the existing rules for vendor SDK access (`app/integrations/<vendor>/`), settings ownership (configuration-ownership.md), and import contracts (import-governance.md).

**Constraints:**

- The application has three top-level position layers (`app/integrations/`, `app/infrastructure/`, `app/packages/`) per `layered-architecture.md`. This record classifies infrastructure-side integrations; it does not redefine the layer model.
- Vendor-client purity is enforced by `client-module-placement.md`: `app/integrations/<vendor>/` contains only authenticated raw SDK access, never an application service. The classification this record establishes operates at the *service* level (the composed Protocol surface that consumers see), not at the raw-client level.
- Vendor credentials live in the infrastructure layer per `configuration-ownership.md`; the classification does not change that rule.
- Feature-package layout (`feature-package-structure.md`) already names `app/packages/<feature>/adapters/<provider>.py` as the home for feature-local outbound adapters; this record formalizes when that location is the correct one.
- Import contracts (`import-governance.md`) already enforce vendor-import boundaries; this record provides the criteria those contracts presuppose.

**Non-goals:**

- This record does not enumerate the application's full inventory of services and their classifications. Each integration's classification is decided when the integration is added, applying the criteria here.
- This record does not redefine adapter responsibilities (exception-to-`OperationResult` translation; no business logic in adapters). Those are owned by `client-adapter-responsibilities.md`.
- This record does not pick the migration mechanics for promoting a feature-local adapter to a shared infrastructure service — only the trigger and the target shape. The migration itself is a code task that follows the trigger.
- This record does not classify cross-cutting infrastructure that is not "service-shaped" — application-wide concerns like the logging stack, the redaction pipeline, the lifespan, the plugin manager, or the configuration providers. Those are framework concerns, not outbound integrations.

## Considered Options

**Option 1 — No formal taxonomy.** Each integration's placement is decided ad hoc when it is added, with reviewers checking against general layered-architecture principles. Consistent with the corpus's existing informal use; vulnerable to drift as the codebase grows.

**Option 2 — Single-axis classification (Path A vs Path B only).** Formalize the existing Path A vs Path B distinction; treat sharing/feature-local as a secondary placement question resolved per-case. Cleaner than ad hoc but leaves the most common follow-up question (where does it live physically?) tied to a separate rule in another record.

**Option 3 — Two-axis classification: Path × Sharing scope.** Two orthogonal axes, both binary in steady state. Path is about *purpose* (cloud-portable capability vs platform-bound integration). Sharing scope is about *consumer breadth* (multiple-feature consumers vs single-feature consumer). The combination determines physical placement, Protocol shape, and promotion rules.

**Option 4 — Three-category taxonomy (A/B/C).** A category for Protocol-required shared services, a category for concrete shared utilities (raw clients), a category for feature-local. Encodes more than the two-axis matrix but adds vocabulary that overlaps with `app/integrations/` (already covered by `client-module-placement.md`).

## Decision Outcome

**Chosen: Option 3 — two-axis classification.**

Each outbound integration is classified along two orthogonal axes. The combination determines its placement, its Protocol shape, and the rules for changing its classification over time. The two axes are simple, binary in steady state, and replace ad-hoc decision-making without introducing vocabulary that overlaps the existing layer model.

### Axis 1 — Path: cloud-portable capability vs platform-bound integration

**Path A — Cloud-portable capability.** The application's interest is in the *capability*; the vendor that provides the capability is replaceable. The Protocol abstracts the capability in domain terms; consumer code depends on the Protocol, never on the vendor. A vendor swap is a configuration and provider-wiring change, not a consumer-code change.

Examples (not exhaustive): a `StorageService` Protocol that may be implemented by an S3-backed adapter today and a GCS-backed adapter tomorrow without consumer-code changes; an `EventDispatcher` Protocol whose implementation could be swapped between an in-process dispatcher and an SNS-backed one; a `SecretsService` Protocol over AWS Secrets Manager that could move to GCP Secret Manager.

The litmus test: **does the consumer ask the question in vendor-neutral language?** "Store this object" — Path A. "Send this Slack Block Kit message to this channel" — not Path A.

**Path B — Platform-bound integration.** The application's interest is in *this specific external system*; the system is not interchangeable. The Protocol exposes the platform's native operations because that is what the consumer needs to express. A vendor swap is not a swap; it is a different integration.

Examples: `SlackService` exposing `post_message`, `open_view`, `lookup_user_by_email` — the consumer is interested in Slack; "post a chat message somewhere" is not the question. `TeamsService` exposing `send_card`, `update_card`, `task_module_invoke`. A feature's `aws_identity_store` adapter exposing operations that mirror the AWS Identity Store API because the feature's purpose is to manage AWS Identity Store memberships specifically.

The litmus test: **the Protocol's method names are platform-shaped or domain-bound to a specific external system's vocabulary.**

**The classification is decided by *purpose*, not by consumer count.** A capability used by exactly one feature today is still Path A if its Protocol is vendor-portable in shape (the application could swap vendors without a code change); a capability used by every feature is still Path B if its Protocol is shaped by a specific external system. Single-consumer Path A and many-consumer Path B both exist.

### Axis 2 — Sharing scope: shared infrastructure vs feature-local adapter

**Shared.** The integration is consumed by **two or more features**, or by another infrastructure service that fans out to many features (for example, a shared `EventDispatcher` consumed by every feature that emits domain events). The integration is a first-class member of the infrastructure layer.

**Feature-local.** The integration is consumed by **exactly one feature**, and the integration's Protocol is shaped by that feature's domain. The integration lives inside the feature package; no other feature imports it.

The classification is observational: count the consumers. If a second feature legitimately needs the integration, the sharing scope changes from feature-local to shared (see "Promotion" below).

### The matrix: classification → physical placement

The four combinations of the two axes map to placement and Protocol shape as follows:

| Path | Sharing scope | Physical placement | Protocol shape |
| --- | --- | --- | --- |
| Path A | Shared | `app/infrastructure/<service>/` | Capability-shaped (`StorageService.put_object(...)`); vendor-neutral |
| Path A | Feature-local | `app/packages/<feature>/adapters/<provider>.py` | Capability-shaped but consumed by one feature only |
| Path B | Shared | `app/infrastructure/<platform>/` | Platform-shaped (`SlackService.post_message(...)`, `TeamsService.send_card(...)`) |
| Path B | Feature-local | `app/packages/<feature>/adapters/<provider>.py` | Domain-bound (`AwsIdentityStoreReconciler.reconcile_group(...)`) shaped by the feature's purpose against this specific external system |

A few observations about the matrix:

- **Path A + Feature-local is uncommon but valid.** Most Path A integrations are introduced because the cloud-portable capability is needed by many features at once; the steady state is Path A + Shared. A single-feature Path A integration is acceptable when the Protocol is genuinely capability-shaped (e.g., a feature-only `RateLimiterStore` that is intentionally a portable abstraction even though only one feature consumes it today). It does not need to be promoted; promotion's trigger is a second consumer, not a guess at portability.
- **Path B + Shared and Path B + Feature-local differ in placement only.** The Protocol shape is platform-bound in both — the difference is whether one feature owns it (`app/packages/<feature>/adapters/<vendor>.py`) or whether it is shared infrastructure (`app/infrastructure/<platform>/`). Slack and Teams are Path B + Shared because every chat-using feature consumes them.
- **The four combinations cover service-shaped infrastructure**, not raw vendor SDK access (`app/integrations/<vendor>/`), not cross-cutting framework concerns (logging stack, lifespan, plugin manager, configuration providers).

### Protocol design implications

- **Path A Protocols** are named in capability terms: `StorageService`, `EventDispatcher`, `SecretsService`, `KeyValueStore`. The methods describe what the consumer wants to *do*, not how the vendor *does it*. Vendor-specific terminology (S3 keys, SQS receipt handles, Slack channel IDs) does not appear on the Protocol surface.
- **Path B Protocols** are named after the platform: `SlackService`, `TeamsService`, `<Specific>IdentityStoreReconciler`. The methods reflect the platform's native operations because that is what the consumer is asking for. Vendor terminology is appropriate on the Protocol surface (Slack `views.open`, Teams Adaptive Card actions).
- **Both Path A and Path B Protocols** are `typing.Protocol`s per `type-boundaries.md`. Both are exposed from the per-service `__init__.py` per `dependency-injection.md`. Consumers receive the Protocol via dependency injection; concrete implementations are hidden behind providers.
- **The vendor's typed exceptions are translated to `OperationResult` at the adapter layer** per `client-adapter-responsibilities.md`. The classification does not change that rule; both Path A and Path B return `OperationResult` to consumers.

### Sharing-scope promotion rules

A feature-local adapter is promoted to shared infrastructure when **a second feature legitimately needs the same integration**. The promotion's trigger is the second consumer, not a count, a pattern, or a guess at future need (per `feature-package-structure.md`). The promotion mechanics:

1. The Protocol and concrete implementation move from `app/packages/<feature_a>/adapters/<provider>.py` to `app/infrastructure/<service>/`.
2. Feature A's import of the Protocol changes from the feature-local path to `app/infrastructure/<service>/__init__.py`. Feature A's adapter file is deleted.
3. Feature B imports the Protocol from `app/infrastructure/<service>/__init__.py` from the start.
4. The shared service's settings, providers, and tests follow the per-service vertical-slice pattern from `dependency-injection.md` and `configuration-ownership.md`.

The promotion is a single PR. The Protocol shape may evolve during promotion if Feature B's needs surface gaps in Feature A's original definition; the evolution is local to the same PR.

**Demotion is not supported.** Once an integration is shared, it does not move back to a feature package even if one of the two consumers later removes its dependency. Removing a service from the shared infrastructure layer requires the second consumer to also disappear; at that point, the service is deleted, not demoted to one feature.

### Path-axis reclassification (rare)

Reclassification along Axis 1 (Path A ↔ Path B) is governance-grade and rare. It happens when the *purpose* of the integration changes — when a vendor-bound integration becomes cloud-portable because the application's needs shift, or vice versa. Examples:

- A feature's `aws_identity_store` adapter (Path B + Feature-local) does not become an `IdentityProviderService` Protocol (Path A + Shared) just because a second feature reads from it. It becomes Path B + Shared (`app/infrastructure/aws_identity_store/`) — the consumers are still asking for AWS Identity Store specifically.
- An `S3StorageAdapter` (Path A + Shared) does not become Path B even if the application has only one cloud target today. The Protocol shape determines the Path; the deployment landscape does not.

Reclassification is not a routine operation. It is a redesign documented through normal review.

### What this classification does not cover

- **Raw vendor SDK access** at `app/integrations/<vendor>/`. Authenticated client construction with scalar credential injection is governed by `client-module-placement.md` and `configuration-ownership.md`; the classification in this record sits one layer above (services consume clients to build the Protocol surface).
- **Cross-cutting framework concerns** — the logging stack, the lifespan, the plugin manager, the redaction pipeline, the configuration providers, the request-correlation middleware. Those are owned by their respective records and are not "outbound integrations."
- **Feature settings and feature business logic.** Both live inside the feature; this record does not change their boundaries.

## Consequences

**Positive:**

- A contributor adding a new integration applies two binary tests (Path A vs B; shared vs feature-local) to land on a placement and a Protocol shape. The decision is mechanical; no consultation of prior art is required for routine cases.
- Protocol shape follows from purpose. Capability-shaped Protocols are recognized at review by their vendor-neutral method names; platform-shaped Protocols by their alignment with the external system's native operations.
- The promotion rule has one trigger (a second consumer) and one target shape (shared infrastructure). Promotion is mechanical when the trigger fires; it is not deferred or accumulated.
- The vocabulary (Path A, Path B, shared, feature-local) is explicit and reusable across the corpus. Records that previously referenced "Path A" informally now have a named, stable taxonomy to point at.
- The classification is decoupled from the count of vendors the application currently uses. Adding a second cloud target to a Path A integration is a provider edit; adding an integration that *looks like* an existing Path B service does not become Path A by accident.

**Tradeoffs accepted:**

- The two axes are an explicit framework. Some integrations are not perfectly placed by it (a feature-local Path A is uncommon but legitimate). The classification provides defaults; reviewers may justify exceptions in the rare cases that warrant them.
- The corpus has used "Path A" / "Path B" informally in several records. Those records continue to use the same terms; no rename is needed. This record formalizes them.
- The promotion rule is one-way: once promoted, an integration does not demote. A feature that briefly co-uses a service and then drops it does not pull the service back into a private corner. Acceptable because demotion would create churn for the remaining consumer; the cost of one extra `app/infrastructure/` entry is small.

**Risks:**

- A contributor classifies an integration ad hoc, missing the criteria. Mitigation: code review against this record's litmus tests; the rule is short and the test (vendor-neutral language vs platform-shaped operations) is fast.
- A feature-local adapter accumulates without anyone noticing it would be cleanly shared. Mitigation: PR review of new adapters checks for lookalike adapters in other features; the second-consumer trigger is enforced when a second feature would re-implement the same logic.
- The Path classification is mistaken at introduction (something modeled as Path A turns out to be inherently platform-bound, or vice versa). Mitigation: reclassification is a documented redesign through normal review; the cost is bounded by the size of the integration's surface area.

## Confirmation

Compliance is verified by:

- **Code review.** A PR introducing a new integration explicitly states the classification (Path A or B; shared or feature-local) and points to the matching matrix row. Reviewers verify the Protocol shape matches the path (capability-shaped for Path A; platform-shaped for Path B). PRs that add a second consumer of a feature-local adapter are paired with the promotion to `app/infrastructure/<service>/`.
- **Repository structure.** Path A and Path B + Shared services live under `app/infrastructure/<service>/` with the per-service vertical-slice pattern. Feature-local adapters live at `app/packages/<feature>/adapters/<provider>.py`. The vendor-import contract (already enforced via `import-linter`) catches feature code reaching into `app/integrations/` outside the adapter path.
- **Naming.** Path A Protocol names use capability terms; Path B Protocol names use platform names. PRs that name a Path A Protocol after a vendor (e.g., `S3StorageService` instead of `StorageService`) are revised; PRs that name a Path B Protocol generically (e.g., `ChatService` instead of `SlackService`) are revised.
- **Tests.** Path A integrations have at least one Protocol-level test that exercises the capability through the Protocol, with the concrete adapter substitutable. Path B integrations have tests that exercise the platform-shaped operations.

## Source References

1. Hexagonal Architecture (Ports and Adapters) — Alistair Cockburn
   - URL: <https://alistair.cockburn.us/hexagonal-architecture/>
   - Accessed: 2026-05-08
   - Relevance: Establishes that an application has driven ports (outbound abstractions) where the application's core defines the contract and adapters supply the implementation. Path A integrations realize this pattern: the Protocol is the port; the vendor adapter is the implementation; the application is portable across implementations. Grounds the criteria for Path A.

2. Domain-Driven Design — Anti-Corruption Layer (Eric Evans, summarized at Microsoft Learn)
   - URL: <https://learn.microsoft.com/en-us/azure/architecture/patterns/anti-corruption-layer>
   - Accessed: 2026-05-08
   - Relevance: Describes the Anti-Corruption Layer pattern — a translation layer between the application's domain model and an external system whose model is not the application's. Path B integrations are anti-corruption layers around specific external systems; the Protocol shape is bound to the external system because that is what the application's domain wants to talk to. Grounds the Path B criteria.

3. Composition Root — Mark Seemann
   - URL: <https://blog.ploeh.dk/2011/07/28/CompositionRoot/>
   - Accessed: 2026-05-08
   - Relevance: Establishes that wiring happens at one composition point and dependencies (including configured implementations of Protocols) are injected downward. Grounds the rule that both Path A and Path B integrations are wired by providers and consumed via dependency injection — the classification does not affect the wiring mechanics, only the Protocol's shape and the integration's location.

4. Vertical Slice Architecture — Jimmy Bogard
   - URL: <https://jimmybogard.com/vertical-slice-architecture/>
   - Accessed: 2026-05-08
   - Relevance: Establishes that features are vertical slices owning their integrations end-to-end, with cross-feature coupling minimized. Grounds the feature-local placement rule (`app/packages/<feature>/adapters/<provider>.py`) and the rule that promotion to shared infrastructure is triggered by a second consumer, not by speculative reuse.

5. Strangler Fig — Martin Fowler
   - URL: <https://martinfowler.com/bliki/StranglerFigApplication.html>
   - Accessed: 2026-05-08
   - Relevance: Establishes the migration pattern in which a new structure is built alongside the old, with consumers gradually transitioning until the old is removed. Grounds the promotion mechanics: the shared service is established at `app/infrastructure/<service>/`, the original feature's adapter is replaced in the same PR, and the adapter file is deleted.

6. Modular Monolith Primer — Kamil Grzybek
   - URL: <https://www.kamilgrzybek.com/blog/posts/modular-monolith-primer>
   - Accessed: 2026-05-08
   - Relevance: Establishes that modules in a modular monolith are organized around business domains, with shared infrastructure consumed through interfaces and feature-local concerns kept inside the module. Grounds the two-axis matrix's separation between shared and feature-local.

## Change Log

- 2026-05-08: Created. Establishes a two-axis classification for outbound integrations: Path (Path A — cloud-portable capability with capability-shaped Protocol; Path B — platform-bound integration with platform-shaped Protocol) × Sharing scope (Shared infrastructure consumed by multiple features; Feature-local adapter consumed by exactly one feature). Pins the four-cell placement matrix: Path A + Shared and Path B + Shared at `app/infrastructure/<service>/`; Path A + Feature-local and Path B + Feature-local at `app/packages/<feature>/adapters/<provider>.py`. The classification is decided by **purpose** (Path) and **consumer count** (Sharing scope), not by guesses or counts of vendors. Promotion from feature-local to shared is triggered by the **second consumer**, and is one-way (no demotion). Reclassification along the Path axis is rare and governance-grade. The classification does not cover raw vendor SDK access (`app/integrations/<vendor>/`, governed by `client-module-placement.md`) or cross-cutting framework concerns (lifespan, plugin manager, logging stack, etc.). Formalizes the "Path A / Path B" vocabulary that several already-accepted records have been using informally; no rename of those records is required.
- 2026-05-12: Updated all `app/integrations/` path references that were incorrectly written as `app/clients/`.
