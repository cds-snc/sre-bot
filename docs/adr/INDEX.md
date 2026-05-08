# Decision Record Index

**Generated:** 2026-05-08 · **Total records:** 35

---

## Summary

| Tier | Application | Operations | Cross-domain |
|------|-------------|------------|--------------|
| Tier-0 (Governance) | — | — | 1 |
| Tier-1 (Foundational) | 3 | 0 | 0 |
| Tier-2 (Cross-cutting) | 25 | 2 | 4 |
| Tier-3 (Scoped) | 0 | 0 | 0 |

---

## By Domain

### Tier-0: Governance

- [decision-record-governance.md](decision-record-governance.md) — **Decision Record Governance**
  - `Governance` · `Accepted` · —

### Application

#### Tier-1: Foundational

- [cloud-portability.md](cloud-portability.md) — **Cloud Portability**
  - `Principle` · `Accepted` · `architecture`
- [layered-architecture.md](layered-architecture.md) — **Layered Architecture**
  - `Principle` · `Accepted` · `architecture`
- [type-boundaries.md](type-boundaries.md) — **Type Boundaries**
  - `Principle` · `Accepted` · `architecture`

#### Tier-2: Cross-cutting

- [api-design-error-mapping.md](api-design-error-mapping.md) — **API Design and Error Mapping**
  - `Standard` · `Draft` · `api`, `architecture`
- [api-security.md](api-security.md) — **API Security**
  - `Standard` · `Draft` · `api`, `security`
- [application-lifecycle.md](application-lifecycle.md) — **Application Lifecycle**
  - `Standard` · `Accepted` · `lifecycle`, `architecture`
- [background-execution.md](background-execution.md) — **Background Execution**
  - `Standard` · `Draft` · `lifecycle`, `architecture`
- [client-adapter-responsibilities.md](client-adapter-responsibilities.md) — **Client and Adapter Responsibilities**
  - `Standard` · `Accepted` · `architecture`
- [client-module-placement.md](client-module-placement.md) — **Client Module Placement**
  - `Selection` · `Accepted` · `architecture`
- [code-quality-tooling.md](code-quality-tooling.md) — **Code Quality Tooling**
  - `Selection` · `Draft` · `quality-gates`
- [configuration-ownership.md](configuration-ownership.md) — **Configuration Ownership and Settings**
  - `Standard` · `Accepted` · `configuration`, `architecture`
- [cross-channel-correlation.md](cross-channel-correlation.md) — **Cross-Channel Correlation**
  - `Standard` · `Draft` · `observability`, `architecture`
- [dependency-injection.md](dependency-injection.md) — **Dependency Injection**
  - `Standard` · `Accepted` · `architecture`
- [environment-parity.md](environment-parity.md) — **Environment Parity**
  - `Standard` · `Draft` · `configuration`
- [event-dispatch.md](event-dispatch.md) — **Event Dispatch**
  - `Standard` · `Draft` · `architecture`
- [feature-package-structure.md](feature-package-structure.md) — **Feature Package Structure**
  - `Standard` · `Draft` · `architecture`, `plugins`
- [handler-idempotency.md](handler-idempotency.md) — **Handler Idempotency**
  - `Standard` · `Draft` · `architecture`, `data`
- [identity-resolution.md](identity-resolution.md) — **Identity Resolution**
  - `Standard` · `Draft` · `security`, `api`
- [import-governance.md](import-governance.md) — **Import Governance**
  - `Standard` · `Accepted` · `architecture`
- [infrastructure-service-classification.md](infrastructure-service-classification.md) — **Infrastructure Service Classification**
  - `Standard` · `Draft` · `architecture`
- [logging-observability.md](logging-observability.md) — **Logging and Observability**
  - `Standard` · `Draft` · `observability`, `security`
- [message-queuing.md](message-queuing.md) — **Message Queuing**
  - `Standard` · `Draft` · `architecture`, `data`
- [multi-transport-architecture.md](multi-transport-architecture.md) — **Multi-Transport Architecture**
  - `Standard` · `Draft` · `api`, `architecture`
- [operation-result-pattern.md](operation-result-pattern.md) — **Operation Result Pattern**
  - `Standard` · `Accepted` · `architecture`, `api`
- [package-management.md](package-management.md) — **Package Management**
  - `Selection` · `Accepted` · `quality-gates`, `configuration`
- [platform-interaction-handlers.md](platform-interaction-handlers.md) — **Platform Interaction Handlers**
  - `Standard` · `Draft` · `api`, `architecture`, `plugins`
- [plugin-registration-discovery.md](plugin-registration-discovery.md) — **Plugin Registration and Discovery**
  - `Standard` · `Draft` · `plugins`, `architecture`
- [project-metadata.md](project-metadata.md) — **Project Metadata**
  - `Standard` · `Accepted` · `configuration`
- [technology-blinker.md](technology-blinker.md) — **Technology Selection: Blinker**
  - `Selection` · `Draft` · `architecture`
- [technology-pluggy.md](technology-pluggy.md) — **Technology Selection: Pluggy**
  - `Selection` · `Draft` · `plugins`, `architecture`
- [technology-slowapi.md](technology-slowapi.md) — **Technology Selection: SlowAPI**
  - `Selection` · `Draft` · `security`, `api`
- [testing-standards.md](testing-standards.md) — **Testing Standards**
  - `Standard` · `Draft` · `testing`, `architecture`

### Operations

#### Tier-2: Cross-cutting

- [build-release-run-pipeline.md](build-release-run-pipeline.md) — **Build-Release-Run Pipeline**
  - `Standard` · `Draft` · `cicd`, `compute`
- [cross-channel-correlation.md](cross-channel-correlation.md) — **Cross-Channel Correlation**
  - `Standard` · `Draft` · `observability`, `architecture`
- [environment-parity.md](environment-parity.md) — **Environment Parity**
  - `Standard` · `Draft` · `configuration`
- [logging-observability.md](logging-observability.md) — **Logging and Observability**
  - `Standard` · `Draft` · `observability`, `security`
- [message-queuing.md](message-queuing.md) — **Message Queuing**
  - `Standard` · `Draft` · `architecture`, `data`
- [port-binding-exposure.md](port-binding-exposure.md) — **Port Binding and Exposure**
  - `Standard` · `Draft` · `compute`

---

## By Concern

### `api`

- [api-design-error-mapping.md](api-design-error-mapping.md) — **API Design and Error Mapping**
  - `Standard` · `Draft` · `api`, `architecture`
- [api-security.md](api-security.md) — **API Security**
  - `Standard` · `Draft` · `api`, `security`
- [identity-resolution.md](identity-resolution.md) — **Identity Resolution**
  - `Standard` · `Draft` · `security`, `api`
- [multi-transport-architecture.md](multi-transport-architecture.md) — **Multi-Transport Architecture**
  - `Standard` · `Draft` · `api`, `architecture`
- [operation-result-pattern.md](operation-result-pattern.md) — **Operation Result Pattern**
  - `Standard` · `Accepted` · `architecture`, `api`
- [platform-interaction-handlers.md](platform-interaction-handlers.md) — **Platform Interaction Handlers**
  - `Standard` · `Draft` · `api`, `architecture`, `plugins`
- [technology-slowapi.md](technology-slowapi.md) — **Technology Selection: SlowAPI**
  - `Selection` · `Draft` · `security`, `api`

### `architecture`

- [api-design-error-mapping.md](api-design-error-mapping.md) — **API Design and Error Mapping**
  - `Standard` · `Draft` · `api`, `architecture`
- [application-lifecycle.md](application-lifecycle.md) — **Application Lifecycle**
  - `Standard` · `Accepted` · `lifecycle`, `architecture`
- [background-execution.md](background-execution.md) — **Background Execution**
  - `Standard` · `Draft` · `lifecycle`, `architecture`
- [client-adapter-responsibilities.md](client-adapter-responsibilities.md) — **Client and Adapter Responsibilities**
  - `Standard` · `Accepted` · `architecture`
- [client-module-placement.md](client-module-placement.md) — **Client Module Placement**
  - `Selection` · `Accepted` · `architecture`
- [cloud-portability.md](cloud-portability.md) — **Cloud Portability**
  - `Principle` · `Accepted` · `architecture`
- [configuration-ownership.md](configuration-ownership.md) — **Configuration Ownership and Settings**
  - `Standard` · `Accepted` · `configuration`, `architecture`
- [cross-channel-correlation.md](cross-channel-correlation.md) — **Cross-Channel Correlation**
  - `Standard` · `Draft` · `observability`, `architecture`
- [dependency-injection.md](dependency-injection.md) — **Dependency Injection**
  - `Standard` · `Accepted` · `architecture`
- [event-dispatch.md](event-dispatch.md) — **Event Dispatch**
  - `Standard` · `Draft` · `architecture`
- [feature-package-structure.md](feature-package-structure.md) — **Feature Package Structure**
  - `Standard` · `Draft` · `architecture`, `plugins`
- [handler-idempotency.md](handler-idempotency.md) — **Handler Idempotency**
  - `Standard` · `Draft` · `architecture`, `data`
- [import-governance.md](import-governance.md) — **Import Governance**
  - `Standard` · `Accepted` · `architecture`
- [infrastructure-service-classification.md](infrastructure-service-classification.md) — **Infrastructure Service Classification**
  - `Standard` · `Draft` · `architecture`
- [layered-architecture.md](layered-architecture.md) — **Layered Architecture**
  - `Principle` · `Accepted` · `architecture`
- [message-queuing.md](message-queuing.md) — **Message Queuing**
  - `Standard` · `Draft` · `architecture`, `data`
- [multi-transport-architecture.md](multi-transport-architecture.md) — **Multi-Transport Architecture**
  - `Standard` · `Draft` · `api`, `architecture`
- [operation-result-pattern.md](operation-result-pattern.md) — **Operation Result Pattern**
  - `Standard` · `Accepted` · `architecture`, `api`
- [platform-interaction-handlers.md](platform-interaction-handlers.md) — **Platform Interaction Handlers**
  - `Standard` · `Draft` · `api`, `architecture`, `plugins`
- [plugin-registration-discovery.md](plugin-registration-discovery.md) — **Plugin Registration and Discovery**
  - `Standard` · `Draft` · `plugins`, `architecture`
- [technology-blinker.md](technology-blinker.md) — **Technology Selection: Blinker**
  - `Selection` · `Draft` · `architecture`
- [technology-pluggy.md](technology-pluggy.md) — **Technology Selection: Pluggy**
  - `Selection` · `Draft` · `plugins`, `architecture`
- [testing-standards.md](testing-standards.md) — **Testing Standards**
  - `Standard` · `Draft` · `testing`, `architecture`
- [type-boundaries.md](type-boundaries.md) — **Type Boundaries**
  - `Principle` · `Accepted` · `architecture`

### `cicd`

- [build-release-run-pipeline.md](build-release-run-pipeline.md) — **Build-Release-Run Pipeline**
  - `Standard` · `Draft` · `cicd`, `compute`

### `compute`

- [build-release-run-pipeline.md](build-release-run-pipeline.md) — **Build-Release-Run Pipeline**
  - `Standard` · `Draft` · `cicd`, `compute`
- [port-binding-exposure.md](port-binding-exposure.md) — **Port Binding and Exposure**
  - `Standard` · `Draft` · `compute`

### `configuration`

- [configuration-ownership.md](configuration-ownership.md) — **Configuration Ownership and Settings**
  - `Standard` · `Accepted` · `configuration`, `architecture`
- [environment-parity.md](environment-parity.md) — **Environment Parity**
  - `Standard` · `Draft` · `configuration`
- [package-management.md](package-management.md) — **Package Management**
  - `Selection` · `Accepted` · `quality-gates`, `configuration`
- [project-metadata.md](project-metadata.md) — **Project Metadata**
  - `Standard` · `Accepted` · `configuration`

### `data`

- [handler-idempotency.md](handler-idempotency.md) — **Handler Idempotency**
  - `Standard` · `Draft` · `architecture`, `data`
- [message-queuing.md](message-queuing.md) — **Message Queuing**
  - `Standard` · `Draft` · `architecture`, `data`

### `lifecycle`

- [application-lifecycle.md](application-lifecycle.md) — **Application Lifecycle**
  - `Standard` · `Accepted` · `lifecycle`, `architecture`
- [background-execution.md](background-execution.md) — **Background Execution**
  - `Standard` · `Draft` · `lifecycle`, `architecture`

### `observability`

- [cross-channel-correlation.md](cross-channel-correlation.md) — **Cross-Channel Correlation**
  - `Standard` · `Draft` · `observability`, `architecture`
- [logging-observability.md](logging-observability.md) — **Logging and Observability**
  - `Standard` · `Draft` · `observability`, `security`

### `plugins`

- [feature-package-structure.md](feature-package-structure.md) — **Feature Package Structure**
  - `Standard` · `Draft` · `architecture`, `plugins`
- [platform-interaction-handlers.md](platform-interaction-handlers.md) — **Platform Interaction Handlers**
  - `Standard` · `Draft` · `api`, `architecture`, `plugins`
- [plugin-registration-discovery.md](plugin-registration-discovery.md) — **Plugin Registration and Discovery**
  - `Standard` · `Draft` · `plugins`, `architecture`
- [technology-pluggy.md](technology-pluggy.md) — **Technology Selection: Pluggy**
  - `Selection` · `Draft` · `plugins`, `architecture`

### `quality-gates`

- [code-quality-tooling.md](code-quality-tooling.md) — **Code Quality Tooling**
  - `Selection` · `Draft` · `quality-gates`
- [package-management.md](package-management.md) — **Package Management**
  - `Selection` · `Accepted` · `quality-gates`, `configuration`

### `security`

- [api-security.md](api-security.md) — **API Security**
  - `Standard` · `Draft` · `api`, `security`
- [identity-resolution.md](identity-resolution.md) — **Identity Resolution**
  - `Standard` · `Draft` · `security`, `api`
- [logging-observability.md](logging-observability.md) — **Logging and Observability**
  - `Standard` · `Draft` · `observability`, `security`
- [technology-slowapi.md](technology-slowapi.md) — **Technology Selection: SlowAPI**
  - `Selection` · `Draft` · `security`, `api`

### `testing`

- [testing-standards.md](testing-standards.md) — **Testing Standards**
  - `Standard` · `Draft` · `testing`, `architecture`
