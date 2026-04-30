---
adr_id: ADR-0076
title: "Infrastructure Intra-Layer Import Standard"
status: Accepted
decision_type: Standard
tier: Tier-2
primary_domain: Dependency and Composition
secondary_domains:
 - Package and Plugin Architecture
owners:
 - SRE Team
date_created: 2026-04-29
last_updated: 2026-04-29
last_reviewed: 2026-04-29
next_review_due: 2026-08-29
constrained_by:
 - ADR-0044
 - ADR-0048
 - ADR-0056
impacts:
 - ADR-0059
supersedes: []
superseded_by: []
review_state: current
related_records:
 - ADR-0048
 - ADR-0056
 - ADR-0055
related_packages: []
---

# Infrastructure Intra-Layer Import Standard

## Context

- Problem statement: ADR-0048 Boundary 5 ("Infrastructure Sibling Isolation") states a blanket rule: "Infrastructure packages must not import from other infrastructure service implementations directly." This rule has zero external evidence citations in the ADR-0048 Best-Practice Revalidation section - none of the checked sources (PEP 8/20, FastAPI docs, Twelve-Factor, Clean Architecture, Pluggy) address intra-layer imports. A codebase audit shows that 11 of 18 infrastructure packages violate this rule (61%), and the violations fall into three distinct categories with different coupling risks. The blanket ban conflates shared value types, configuration injection, and service composition - three concerns with different correct solutions. This ADR replaces the under-specified principle with a properly sourced, three-part standard.

- Business/operational drivers:
- Provide an enforceable, evidence-based standard for infrastructure intra-layer imports.
- Distinguish between value-type sharing (harmless), configuration injection (addressed elsewhere), and service composition (the actual coupling risk).
- Align the codebase with established architectural best practices rather than an undocumented local convention.
- Reduce false-positive boundary violations that create friction without preventing real coupling.

- Constraints:
- ADR-0048 Boundary 5 establishes the principle that infrastructure packages are peers (Tier-1).
- ADR-0056 Standard 3 establishes `providers.py` as the composition root (Tier-2).
- ADR-0055 governs how settings are consumed via narrow-slice injection (Tier-2).
- The Dependency Inversion Principle governs inter-layer relationships, not intra-layer ones.

## Decision

ADR-0048 Boundary 5 is refined from a blanket import ban into three targeted rules. The principle-level intent - "infrastructure packages are peers that must not develop hidden coupling" - is preserved. The implementation-level mechanism is corrected to distinguish three categories of intra-layer import.

### Standard 1: Shared Value Types Are Permitted

Infrastructure packages may import shared value types, enumerations, and data containers from sibling infrastructure packages at runtime.

**Qualifying types** (non-exhaustive):

- `OperationResult`, `OperationStatus` from `infrastructure.operations`
- Dataclass or frozen-dataclass value objects that carry no service behavior
- Enumerations and type aliases used across multiple infrastructure packages
- Translation keys and locale identifiers from `infrastructure.i18n.models`

**Rationale:** Shared value types are the infrastructure layer's internal vocabulary. They carry no service behavior, hold no mutable state, and create no instantiation coupling. Prohibiting their import forces either duplication or indirection through the composition root - both of which increase complexity without reducing coupling.

**Constraints:**

- S1.1: The imported type must be a value object, enum, dataclass, or type alias. It must not be a service class, client class, or factory.
- S1.2: If the import graph for shared types becomes cyclic (A imports a type from B, B imports a type from A), the shared types must be extracted to a dedicated `infrastructure.types` or `infrastructure.shared` kernel package.
- S1.3: Shared value types must not hold references to service instances or mutable global state.

### Standard 2: Configuration Must Flow Through Injection

Infrastructure packages must not import configuration classes or settings objects from sibling infrastructure packages. All configuration must be received via constructor injection of the narrowest applicable settings slice.

**Prohibited:**

```python
# WRONG - direct sibling configuration import
from app.infrastructure.configuration.integrations.aws import AwsSettings
```

**Permitted:**

```python
# CORRECT - received via constructor injection
class MyService:
 def __init__(self, aws_settings: AwsSettings) -> None:
 self.aws_settings = aws_settings
```

**Rationale:** Direct configuration imports create hidden coupling between the consuming package and the settings module's internal structure. Constructor injection makes the dependency explicit, overridable for testing, and traceable through the provider graph. This rule is already mandated by ADR-0055 (settings dissolution) and ADR-0056 Standard 1 (narrow-slice injection) - this standard makes the intra-layer application explicit.

**Constraints:**

- S2.1: Configuration must arrive via constructor parameters, not module-level imports.
- S2.2: `TYPE_CHECKING` imports of settings classes for type annotations are permitted, since they create no runtime coupling.
- S2.3: The `infrastructure.configuration` package is the sole exception: it is a shared settings registry, not a peer service.

### Standard 3: Service Composition Must Happen in the Composition Root

Infrastructure packages must not instantiate, construct, or compose other infrastructure services. All cross-service wiring must happen in the composition root (`app/infrastructure/services/providers.py`).

**Prohibited:**

```python
# WRONG - infrastructure package instantiates a sibling service
from app.infrastructure.clients.google_workspace import GoogleWorkspaceClients

class DirectoryFactory:
 def build(self):
 clients = GoogleWorkspaceClients(...) # composition outside the root
```

**Permitted:**

```python
# CORRECT - receive the composed service via constructor injection
class DirectoryFactory:
 def __init__(self, clients: GoogleWorkspaceClients) -> None:
 self.clients = clients

# In providers.py (composition root):
def get_directory_provider():
 clients = get_google_workspace_clients()
 return build_directory_provider(clients=clients)
```

**Rationale:** The Composition Root pattern (Seemann 2011) establishes that object graphs should be assembled in a single location, as close to the application entry point as possible. When individual infrastructure packages compose each other, the wiring becomes distributed, untraceable, and difficult to override for testing. This is the core coupling risk that ADR-0048 B5 was designed to prevent.

**Constraints:**

- S3.1: No infrastructure package may call a sibling package's constructor, factory function, or builder outside of `providers.py`.
- S3.2: Infrastructure packages may accept composed sibling services via constructor injection - the prohibition is on *constructing* them, not *using* them.
- S3.3: `TYPE_CHECKING` imports of service classes for type annotations are permitted.
- S3.4: Protocol-typed constructor parameters are preferred over concrete class parameters when the consuming package needs only a behavioral subset of the sibling service.

For the centralization rationale and the positive framing of where composition MUST happen, see ADR-0056 Standard 3.

## Current Violations

Audit performed 2026-04-29 against `app/infrastructure/`.

### Standard 1 Violations: None

All current shared-type imports (OperationResult, OperationStatus, TranslationKey, Locale) are now explicitly permitted under Standard 1. These were previously counted as B5 violations under the blanket ban.

### Standard 2 Violations (Configuration Imports)

| Package | File | Import | Required Fix |
|---------|------|--------|-------------|
| `directory` | `factory.py` | `infrastructure.configuration.infrastructure.DirectorySettings` | Receive via constructor injection |
| `logging` | `setup.py` | `infrastructure.configuration.Settings` | Receive via constructor injection |
| `resilience` | `retry/factory.py` | `infrastructure.configuration.Settings` | Receive via constructor injection |
| `clients/aws` | `config.py` | `infrastructure.configuration.integrations.aws.AwsSettings` | Receive via constructor injection |

### Standard 3 Violations (Service Composition Outside Root)

| Package | File | Violation | Required Fix |
|---------|------|-----------|-------------|
| `directory` | `factory.py` | Constructs `GoogleWorkspaceClients` directly | Receive via constructor from `providers.py` |
| `storage` | `service.py` | Imports `DynamoDBClient` from `clients.aws.dynamodb` | Receive via constructor from `providers.py` |
| `security` | `current_user.py` | Imports `IdentityService` and identity models directly | Receive via constructor or DI alias |
| `notifications` | `channels/base.py` | Imports `CircuitBreaker` from `resilience.circuit_breaker` | Receive via constructor from `providers.py` |

### Compliant Packages (No Violations Under Refined Rules)

| Package | Notes |
|---------|-------|
| `configuration` | Settings registry - exempt from Standard 2 per S2.3 |
| `events` | No sibling imports |
| `hookspecs` | No sibling imports |
| `identity` | Uses `TYPE_CHECKING` correctly (S2.2, S3.3) |
| `idempotency` | Uses `TYPE_CHECKING` correctly (S2.2, S3.3) |
| `operations` | Shared value-type package - no sibling imports |
| `i18n` | Imports only shared value types from `operations` (S1) |
| `audit` | Imports only shared value types from `operations` (S1) |
| `platforms` | Imports only shared value types from `operations` and `i18n.models` (S1) |
| `commands` | Imports only shared value types from `i18n.models` (S1) |
| `notifications` | Service-level: uses `TYPE_CHECKING` correctly. Channel-level: Standard 3 violation (CircuitBreaker) |

## Alternatives Considered

1. **Retain the blanket ban (status quo - ADR-0048 B5 as-is):**

- Pros: Simplest rule; maximum theoretical isolation.
- Cons: 61% violation rate with no enforcement. Conflates harmless value-type sharing with actual coupling risks. No external evidence supports blanket intra-layer isolation in Python. Creates friction without preventing real problems.
- Why not chosen: An unenforced rule that lacks evidence-based grounding is worse than no rule - it creates false confidence.

1. **Remove B5 entirely (no intra-layer import rules):**

- Pros: Reflects actual Python ecosystem norms (Django contrib packages, Sentry modules cross-import freely).
- Cons: Loses the legitimate service-composition concern. Infrastructure packages could develop distributed wiring that bypasses the composition root.
- Why not chosen: The Composition Root pattern is well-established (Seemann, Cosmic Python). Removing all intra-layer rules would permit the specific coupling pattern that is genuinely harmful.

1. **Move all shared types to a single kernel package:**

- Pros: Eliminates all Standard 1 imports; every infrastructure package imports only from `infrastructure.types`.
- Cons: Premature abstraction. The current shared-type surface is small (OperationResult, OperationStatus, TranslationKey, Locale). Forcing a kernel package at this scale adds indirection without reducing coupling.
- Why not chosen: Standard 1 Constraint S1.2 provides the trigger for this refactoring if/when the shared-type graph becomes cyclic. Pre-emptive extraction is not justified at current scale.

## Consequences

- Positive impacts:
- The blanket ban is replaced by three enforceable, evidence-based rules that target actual coupling risks.
- Approximately 8 current "violations" are reclassified as compliant (shared value-type imports), reducing remediation scope.
- The remaining ~8 violations are properly categorized and mapped to specific remediation patterns.
- The standard is auditable - each rule has a clear test: "Is this a value type?" / "Is this a settings import?" / "Is this constructing a sibling service?"
- Tradeoffs accepted:
- Standard 1 (shared types permitted) accepts that infrastructure packages share vocabulary. If the shared-type surface grows significantly, the S1.2 kernel extraction trigger activates.
- Standard 3 (composition root only) is stricter than general Python norms but weaker than the blanket ban. This is deliberate - the Composition Root pattern is the one intra-layer rule with strong external evidence.
- Risks introduced:
- Developers may misclassify a service class as a "shared type" to avoid Standard 3. Mitigation: S1.1 explicitly defines qualifying types (value objects, enums, dataclasses, type aliases - not service/client/factory classes).
- Shared-type proliferation could create an implicit coupling web. Mitigation: S1.2 triggers kernel extraction when cyclic imports appear.

## Compliance and Boundaries

- ADR-0048 Boundary 5 relationship: This standard provides the implementation-level rules for B5. The principle-level statement in ADR-0048 B5 should be annotated with a reference to this standard for detailed guidance. The B5 text remains authoritative as a governance principle; this standard is authoritative for enforcement.
- ADR-0056 Standard 3 relationship: ADR-0056 Standard 3 (centralized `providers.py`) is the complementary rule - it governs WHERE composition happens. This standard's Standard 3 governs WHO may perform composition (only the composition root, not individual infrastructure packages).
- ADR-0055 relationship: Standard 2 of this ADR reinforces ADR-0055's narrow-slice injection mandate, applied specifically to the intra-infrastructure-layer case.

## Best-Practice Revalidation

- Revalidation date: 2026-04-29
- Sources rechecked:

 1. Mark Seemann - Composition Root (2011): "A Composition Root is a (preferably) unique location in an application where modules are composed together." Directly supports Standard 3.
 2. Mark Seemann - "Layers, Onions, Ports, Adapters: it's all the same" (2013): Introduces "bulkheads" between adapter categories in the same layer, but between functional groups (UI vs. persistence), not between individual infrastructure services. Explicitly states "components can depend on other components within the same layer." Supports Standard 1 (shared types) and contradicts the blanket ban.
 3. Robert C. Martin - Clean Architecture (2012): The Dependency Rule states "source code dependencies can only point inwards." This governs inter-ring relationships. Clean Architecture does not address intra-layer imports - components in the "Frameworks and Drivers" ring or "Interface Adapters" ring are not prohibited from depending on each other. Confirms B5 is not derivable from Clean Architecture.
 4. Cosmic Python - Chapter 13, Dependency Injection and Bootstrapping: All adapter wiring happens in the bootstrap function (composition root). Adapters receive their dependencies via constructor injection. No guidance on prohibiting shared types between adapters. Supports Standard 2 and Standard 3.
 5. Django project structure: Django's own `contrib` packages import from each other freely (`contrib.admin` -> `contrib.auth` -> `contrib.contenttypes`). The largest Python web framework does not enforce intra-layer isolation. Supports Standard 1.
 6. Sentry (getsentry/sentry): 80+ top-level packages cross-import extensively. No blanket sibling isolation. Large-scale Python monorepo does not use this pattern. Supports Standard 1.
 7. Fowler - Constructor Injection: Dependencies should be explicit and received via constructors, not resolved via direct imports of concrete implementations. Supports Standard 2 and Standard 3.
 8. Twelve-Factor App - Factor IV (Backing Services): Each backing service is independently configured. Configuration should not be shared via direct imports between infrastructure modules. Supports Standard 2.

- Alignment summary:
- Standard 1 (shared types permitted) aligns with Seemann, Django, Sentry, and general Python norms.
- Standard 2 (configuration via injection) aligns with Fowler (constructor injection), Twelve-Factor (Factor IV), and ADR-0055/ADR-0056.
- Standard 3 (composition root only) aligns with Seemann (Composition Root 2011), Cosmic Python (Ch. 13), and ADR-0056 Standard 3.
- Intentional deviations from prior internal practice:
- **ADR-0048 B5 blanket ban relaxed.** The blanket "must not import from other infrastructure service implementations directly" is replaced by three targeted rules. This is an intentional correction - B5 had no external evidence, was violated by 61% of infrastructure packages, and conflated three distinct concerns. The refined rules preserve the legitimate coupling-prevention intent while aligning with established practice.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: New Tier-2 standard providing enforceable implementation rules for ADR-0048 Boundary 5 (infrastructure sibling isolation). Replaces an under-specified blanket ban with three evidence-based rules targeting distinct coupling risks.
- Follow-up actions:
- Annotate ADR-0048 Boundary 5 text with a reference to this standard.
- Remediate Standard 2 violations (4 configuration imports) during Action 5 (settings dissolution).
- Remediate Standard 3 violations (4 service composition violations) during Action 6 (provider restructuring).

## Source References

1. Source title: Composition Root

- URL: <https://blog.ploeh.dk/2011/07/28/CompositionRoot/>
- Publisher/maintainer: Mark Seemann
- Accessed date (YYYY-MM-DD): 2026-04-29
- Relevance summary: Defines the Composition Root pattern - "a (preferably) unique location in an application where modules are composed together." Directly supports Standard 3 (service composition must happen in the composition root, not distributed across infrastructure packages).

1. Source title: Layers, Onions, Ports, Adapters: it's all the same

- URL: <https://blog.ploeh.dk/2013/12/03/layers-onions-ports-adapters-its-all-the-same/>
- Publisher/maintainer: Mark Seemann
- Accessed date (YYYY-MM-DD): 2026-04-29
- Relevance summary: Explicitly states "components can depend on other components within the same layer" while introducing bulkheads between adapter categories (not individual services). Supports Standard 1 (shared types) and contradicts blanket sibling isolation.

1. Source title: The Clean Architecture

- URL: <https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html>
- Publisher/maintainer: Robert C. Martin
- Accessed date (YYYY-MM-DD): 2026-04-29
- Relevance summary: The Dependency Rule governs inter-ring dependencies ("source code dependencies can only point inwards"). Does not address intra-layer imports. Confirms blanket sibling isolation is not derivable from Clean Architecture.

1. Source title: Architecture Patterns with Python - Chapter 13: Dependency Injection (and Bootstrapping)

- URL: <https://www.cosmicpython.com/book/chapter_13_dependency_injection.html>
- Publisher/maintainer: Harry Percival, Bob Gregory (O'Reilly)
- Accessed date (YYYY-MM-DD): 2026-04-29
- Relevance summary: Demonstrates the bootstrap/composition-root pattern for Python applications. All adapter wiring happens in a single `bootstrap()` function. Adapters receive dependencies via constructor injection. No guidance on prohibiting shared types between adapters. Supports Standards 2 and 3.

1. Source title: Django Contrib Packages (project structure reference)

- URL: <https://github.com/django/django/tree/main/django/contrib>
- Publisher/maintainer: Django Software Foundation
- Accessed date (YYYY-MM-DD): 2026-04-29
- Relevance summary: Django's own infrastructure packages (`contrib.admin`, `contrib.auth`, `contrib.contenttypes`) import from each other freely. The largest Python web framework does not enforce intra-layer isolation, demonstrating this is not an established Python best practice.

1. Source title: Sentry project structure (large-scale Python monorepo reference)

- URL: <https://github.com/getsentry/sentry/tree/master/src/sentry>
- Publisher/maintainer: Functional Software, Inc. (Sentry)
- Accessed date (YYYY-MM-DD): 2026-04-29
- Relevance summary: 80+ top-level packages with extensive cross-imports. No blanket sibling isolation policy. Demonstrates that large-scale Python applications do not use this pattern.

1. Source title: Fowler - Inversion of Control Containers and the Dependency Injection pattern

- URL: <https://martinfowler.com/articles/injection.html>
- Publisher/maintainer: Martin Fowler
- Accessed date (YYYY-MM-DD): 2026-04-29
- Relevance summary: Constructor injection makes dependencies explicit and overridable. Supports Standard 2 (configuration via injection) and Standard 3 (composition via root, not distributed).

1. Source title: ADR-0048 - Dependency and Import Boundary Constitution (internal)

- URL: docs/decisions/adr/0048-dependency-and-import-boundary-constitution.md
- Publisher/maintainer: SRE Team
- Accessed date (YYYY-MM-DD): 2026-04-29
- Relevance summary: Parent Tier-1 principle record. Boundary 5 establishes the principle-level intent. This standard provides implementation-level enforcement rules.
