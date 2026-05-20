# Decision Record Index

**Generated:** 2026-05-13 · **Total records:** 44

---

## Summary

| Tier | Application | Operations | Cross-domain |
|------|-------------|------------|--------------|
| Tier-0 (Governance) | — | — | 1 |
| Tier-1 (Foundational) | 3 | 0 | 0 |
| Tier-2 (Cross-cutting) | 29 | 2 | 5 |
| Tier-3 (Scoped) | 4 | 0 | 0 |

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
  - `Standard` · `Accepted` · `api`, `architecture`
- [api-security.md](api-security.md) — **API Security**
  - `Standard` · `Accepted` · `api`, `security`
- [application-lifecycle.md](application-lifecycle.md) — **Application Lifecycle**
  - `Standard` · `Accepted` · `lifecycle`, `architecture`
- [background-execution.md](background-execution.md) — **Background Execution**
  - `Standard` · `Accepted` · `lifecycle`, `architecture`
- [client-adapter-responsibilities.md](client-adapter-responsibilities.md) — **Client and Adapter Responsibilities**
  - `Standard` · `Accepted` · `architecture`
- [client-module-placement.md](client-module-placement.md) — **Client Module Placement**
  - `Selection` · `Accepted` · `architecture`
- [client-sdk-shield-pattern.md](client-sdk-shield-pattern.md) — **Client SDK Shield Pattern**
  - `Standard` · `Draft` · `architecture`
- [code-quality-tooling.md](code-quality-tooling.md) — **Code Quality Tooling**
  - `Selection` · `Accepted` · `quality-gates`
- [configuration-ownership.md](configuration-ownership.md) — **Configuration Ownership and Settings**
  - `Standard` · `Accepted` · `configuration`, `architecture`
- [cross-channel-correlation.md](cross-channel-correlation.md) — **Cross-Channel Correlation**
  - `Standard` · `Accepted` · `observability`, `architecture`
- [data-redaction-policy.md](data-redaction-policy.md) — **Data Redaction Policy**
  - `Standard` · `Accepted` · `security`, `observability`
- [dependency-injection.md](dependency-injection.md) — **Dependency Injection**
  - `Standard` · `Accepted` · `architecture`
- [environment-parity.md](environment-parity.md) — **Environment Parity**
  - `Standard` · `Accepted` · `configuration`
- [event-dispatch.md](event-dispatch.md) — **Event Dispatch**
  - `Standard` · `Accepted` · `architecture`
- [feature-handler-standard.md](feature-handler-standard.md) — **Feature Handler Standard**
  - `Standard` · `Accepted` · `api`, `architecture`, `plugins`
- [feature-package-structure.md](feature-package-structure.md) — **Feature Package Structure**
  - `Standard` · `Accepted` · `architecture`, `plugins`
- [handler-idempotency.md](handler-idempotency.md) — **Handler Idempotency**
  - `Standard` · `Accepted` · `architecture`, `data`
- [identity-resolution.md](identity-resolution.md) — **Identity Resolution**
  - `Standard` · `Accepted` · `security`, `api`
- [import-governance.md](import-governance.md) — **Import Governance**
  - `Standard` · `Accepted` · `architecture`
- [infrastructure-i18n.md](infrastructure-i18n.md) — **Infrastructure I18n**
  - `Selection` · `Draft` · `architecture`, `configuration`
- [infrastructure-service-classification.md](infrastructure-service-classification.md) — **Infrastructure Service Classification**
  - `Standard` · `Accepted` · `architecture`
- [logging-observability.md](logging-observability.md) — **Logging and Observability**
  - `Standard` · `Accepted` · `observability`
- [message-queuing.md](message-queuing.md) — **Message Queuing**
  - `Standard` · `Accepted` · `architecture`, `data`
- [multi-transport-architecture.md](multi-transport-architecture.md) — **Multi-Transport Architecture**
  - `Standard` · `Accepted` · `api`, `architecture`
- [operation-result-pattern.md](operation-result-pattern.md) — **Operation Result Pattern**
  - `Standard` · `Accepted` · `architecture`, `api`
- [outbound-retry-policy.md](outbound-retry-policy.md) — **Outbound Retry Policy**
  - `Standard` · `Accepted` · `architecture`
- [package-management.md](package-management.md) — **Package Management**
  - `Selection` · `Accepted` · `quality-gates`, `configuration`
- [plugin-registration-discovery.md](plugin-registration-discovery.md) — **Plugin Registration and Discovery**
  - `Standard` · `Accepted` · `plugins`, `architecture`
- [project-metadata.md](project-metadata.md) — **Project Metadata**
  - `Standard` · `Accepted` · `configuration`
- [technology-blinker.md](technology-blinker.md) — **Technology Selection: Blinker**
  - `Selection` · `Accepted` · `architecture`
- [technology-pluggy.md](technology-pluggy.md) — **Technology Selection: Pluggy**
  - `Selection` · `Accepted` · `plugins`, `architecture`
- [technology-slowapi.md](technology-slowapi.md) — **Technology Selection: SlowAPI**
  - `Selection` · `Accepted` · `security`, `api`
- [testing-standards.md](testing-standards.md) — **Testing Standards**
  - `Standard` · `Accepted` · `testing`, `architecture`
- [transport-teams.md](transport-teams.md) — **Teams Transport**
  - `Standard` · `Draft` · `api`, `architecture`, `plugins`

#### Tier-3: Scoped

- [slack-command-parser.md](slack-command-parser.md) — **Slack Command Parser**
  - `Standard` · `Draft` · `architecture`, `api`
- [slack-help-text.md](slack-help-text.md) — **Slack Help Text**
  - `Standard` · `Draft` · `architecture`, `api`
- [transport-slack-delivery-mode.md](transport-slack-delivery-mode.md) — **Slack Transport — Delivery Mode**
  - `Standard` · `Draft` · `architecture`, `api`
- [transport-slack-shield.md](transport-slack-shield.md) — **Slack Transport — Shield Implementation**
  - `Standard` · `Draft` · `architecture`, `api`

### Operations

#### Tier-2: Cross-cutting

- [build-release-run-pipeline.md](build-release-run-pipeline.md) — **Build-Release-Run Pipeline**
  - `Standard` · `Accepted` · `cicd`, `compute`
- [cross-channel-correlation.md](cross-channel-correlation.md) — **Cross-Channel Correlation**
  - `Standard` · `Accepted` · `observability`, `architecture`
- [data-redaction-policy.md](data-redaction-policy.md) — **Data Redaction Policy**
  - `Standard` · `Accepted` · `security`, `observability`
- [environment-parity.md](environment-parity.md) — **Environment Parity**
  - `Standard` · `Accepted` · `configuration`
- [logging-observability.md](logging-observability.md) — **Logging and Observability**
  - `Standard` · `Accepted` · `observability`
- [message-queuing.md](message-queuing.md) — **Message Queuing**
  - `Standard` · `Accepted` · `architecture`, `data`
- [port-binding-exposure.md](port-binding-exposure.md) — **Port Binding and Exposure**
  - `Standard` · `Accepted` · `compute`

---

## By Concern

### `api`

- [api-design-error-mapping.md](api-design-error-mapping.md) — **API Design and Error Mapping**
  - `Standard` · `Accepted` · `api`, `architecture`
- [api-security.md](api-security.md) — **API Security**
  - `Standard` · `Accepted` · `api`, `security`
- [feature-handler-standard.md](feature-handler-standard.md) — **Feature Handler Standard**
  - `Standard` · `Accepted` · `api`, `architecture`, `plugins`
- [identity-resolution.md](identity-resolution.md) — **Identity Resolution**
  - `Standard` · `Accepted` · `security`, `api`
- [multi-transport-architecture.md](multi-transport-architecture.md) — **Multi-Transport Architecture**
  - `Standard` · `Accepted` · `api`, `architecture`
- [operation-result-pattern.md](operation-result-pattern.md) — **Operation Result Pattern**
  - `Standard` · `Accepted` · `architecture`, `api`
- [slack-command-parser.md](slack-command-parser.md) — **Slack Command Parser**
  - `Standard` · `Draft` · `architecture`, `api`
- [slack-help-text.md](slack-help-text.md) — **Slack Help Text**
  - `Standard` · `Draft` · `architecture`, `api`
- [technology-slowapi.md](technology-slowapi.md) — **Technology Selection: SlowAPI**
  - `Selection` · `Accepted` · `security`, `api`
- [transport-slack-delivery-mode.md](transport-slack-delivery-mode.md) — **Slack Transport — Delivery Mode**
  - `Standard` · `Draft` · `architecture`, `api`
- [transport-slack-shield.md](transport-slack-shield.md) — **Slack Transport — Shield Implementation**
  - `Standard` · `Draft` · `architecture`, `api`
- [transport-teams.md](transport-teams.md) — **Teams Transport**
  - `Standard` · `Draft` · `api`, `architecture`, `plugins`

### `architecture`

- [api-design-error-mapping.md](api-design-error-mapping.md) — **API Design and Error Mapping**
  - `Standard` · `Accepted` · `api`, `architecture`
- [application-lifecycle.md](application-lifecycle.md) — **Application Lifecycle**
  - `Standard` · `Accepted` · `lifecycle`, `architecture`
- [background-execution.md](background-execution.md) — **Background Execution**
  - `Standard` · `Accepted` · `lifecycle`, `architecture`
- [client-adapter-responsibilities.md](client-adapter-responsibilities.md) — **Client and Adapter Responsibilities**
  - `Standard` · `Accepted` · `architecture`
- [client-module-placement.md](client-module-placement.md) — **Client Module Placement**
  - `Selection` · `Accepted` · `architecture`
- [client-sdk-shield-pattern.md](client-sdk-shield-pattern.md) — **Client SDK Shield Pattern**
  - `Standard` · `Draft` · `architecture`
- [cloud-portability.md](cloud-portability.md) — **Cloud Portability**
  - `Principle` · `Accepted` · `architecture`
- [configuration-ownership.md](configuration-ownership.md) — **Configuration Ownership and Settings**
  - `Standard` · `Accepted` · `configuration`, `architecture`
- [cross-channel-correlation.md](cross-channel-correlation.md) — **Cross-Channel Correlation**
  - `Standard` · `Accepted` · `observability`, `architecture`
- [dependency-injection.md](dependency-injection.md) — **Dependency Injection**
  - `Standard` · `Accepted` · `architecture`
- [event-dispatch.md](event-dispatch.md) — **Event Dispatch**
  - `Standard` · `Accepted` · `architecture`
- [feature-handler-standard.md](feature-handler-standard.md) — **Feature Handler Standard**
  - `Standard` · `Accepted` · `api`, `architecture`, `plugins`
- [feature-package-structure.md](feature-package-structure.md) — **Feature Package Structure**
  - `Standard` · `Accepted` · `architecture`, `plugins`
- [handler-idempotency.md](handler-idempotency.md) — **Handler Idempotency**
  - `Standard` · `Accepted` · `architecture`, `data`
- [import-governance.md](import-governance.md) — **Import Governance**
  - `Standard` · `Accepted` · `architecture`
- [infrastructure-i18n.md](infrastructure-i18n.md) — **Infrastructure I18n**
  - `Selection` · `Draft` · `architecture`, `configuration`
- [infrastructure-service-classification.md](infrastructure-service-classification.md) — **Infrastructure Service Classification**
  - `Standard` · `Accepted` · `architecture`
- [layered-architecture.md](layered-architecture.md) — **Layered Architecture**
  - `Principle` · `Accepted` · `architecture`
- [message-queuing.md](message-queuing.md) — **Message Queuing**
  - `Standard` · `Accepted` · `architecture`, `data`
- [multi-transport-architecture.md](multi-transport-architecture.md) — **Multi-Transport Architecture**
  - `Standard` · `Accepted` · `api`, `architecture`
- [operation-result-pattern.md](operation-result-pattern.md) — **Operation Result Pattern**
  - `Standard` · `Accepted` · `architecture`, `api`
- [outbound-retry-policy.md](outbound-retry-policy.md) — **Outbound Retry Policy**
  - `Standard` · `Accepted` · `architecture`
- [plugin-registration-discovery.md](plugin-registration-discovery.md) — **Plugin Registration and Discovery**
  - `Standard` · `Accepted` · `plugins`, `architecture`
- [slack-command-parser.md](slack-command-parser.md) — **Slack Command Parser**
  - `Standard` · `Draft` · `architecture`, `api`
- [slack-help-text.md](slack-help-text.md) — **Slack Help Text**
  - `Standard` · `Draft` · `architecture`, `api`
- [technology-blinker.md](technology-blinker.md) — **Technology Selection: Blinker**
  - `Selection` · `Accepted` · `architecture`
- [technology-pluggy.md](technology-pluggy.md) — **Technology Selection: Pluggy**
  - `Selection` · `Accepted` · `plugins`, `architecture`
- [testing-standards.md](testing-standards.md) — **Testing Standards**
  - `Standard` · `Accepted` · `testing`, `architecture`
- [transport-slack-delivery-mode.md](transport-slack-delivery-mode.md) — **Slack Transport — Delivery Mode**
  - `Standard` · `Draft` · `architecture`, `api`
- [transport-slack-shield.md](transport-slack-shield.md) — **Slack Transport — Shield Implementation**
  - `Standard` · `Draft` · `architecture`, `api`
- [transport-teams.md](transport-teams.md) — **Teams Transport**
  - `Standard` · `Draft` · `api`, `architecture`, `plugins`
- [type-boundaries.md](type-boundaries.md) — **Type Boundaries**
  - `Principle` · `Accepted` · `architecture`

### `cicd`

- [build-release-run-pipeline.md](build-release-run-pipeline.md) — **Build-Release-Run Pipeline**
  - `Standard` · `Accepted` · `cicd`, `compute`

### `compute`

- [build-release-run-pipeline.md](build-release-run-pipeline.md) — **Build-Release-Run Pipeline**
  - `Standard` · `Accepted` · `cicd`, `compute`
- [port-binding-exposure.md](port-binding-exposure.md) — **Port Binding and Exposure**
  - `Standard` · `Accepted` · `compute`

### `configuration`

- [configuration-ownership.md](configuration-ownership.md) — **Configuration Ownership and Settings**
  - `Standard` · `Accepted` · `configuration`, `architecture`
- [environment-parity.md](environment-parity.md) — **Environment Parity**
  - `Standard` · `Accepted` · `configuration`
- [infrastructure-i18n.md](infrastructure-i18n.md) — **Infrastructure I18n**
  - `Selection` · `Draft` · `architecture`, `configuration`
- [package-management.md](package-management.md) — **Package Management**
  - `Selection` · `Accepted` · `quality-gates`, `configuration`
- [project-metadata.md](project-metadata.md) — **Project Metadata**
  - `Standard` · `Accepted` · `configuration`

### `data`

- [handler-idempotency.md](handler-idempotency.md) — **Handler Idempotency**
  - `Standard` · `Accepted` · `architecture`, `data`
- [message-queuing.md](message-queuing.md) — **Message Queuing**
  - `Standard` · `Accepted` · `architecture`, `data`

### `lifecycle`

- [application-lifecycle.md](application-lifecycle.md) — **Application Lifecycle**
  - `Standard` · `Accepted` · `lifecycle`, `architecture`
- [background-execution.md](background-execution.md) — **Background Execution**
  - `Standard` · `Accepted` · `lifecycle`, `architecture`

### `observability`

- [cross-channel-correlation.md](cross-channel-correlation.md) — **Cross-Channel Correlation**
  - `Standard` · `Accepted` · `observability`, `architecture`
- [data-redaction-policy.md](data-redaction-policy.md) — **Data Redaction Policy**
  - `Standard` · `Accepted` · `security`, `observability`
- [logging-observability.md](logging-observability.md) — **Logging and Observability**
  - `Standard` · `Accepted` · `observability`

### `plugins`

- [feature-handler-standard.md](feature-handler-standard.md) — **Feature Handler Standard**
  - `Standard` · `Accepted` · `api`, `architecture`, `plugins`
- [feature-package-structure.md](feature-package-structure.md) — **Feature Package Structure**
  - `Standard` · `Accepted` · `architecture`, `plugins`
- [plugin-registration-discovery.md](plugin-registration-discovery.md) — **Plugin Registration and Discovery**
  - `Standard` · `Accepted` · `plugins`, `architecture`
- [technology-pluggy.md](technology-pluggy.md) — **Technology Selection: Pluggy**
  - `Selection` · `Accepted` · `plugins`, `architecture`
- [transport-teams.md](transport-teams.md) — **Teams Transport**
  - `Standard` · `Draft` · `api`, `architecture`, `plugins`

### `quality-gates`

- [code-quality-tooling.md](code-quality-tooling.md) — **Code Quality Tooling**
  - `Selection` · `Accepted` · `quality-gates`
- [package-management.md](package-management.md) — **Package Management**
  - `Selection` · `Accepted` · `quality-gates`, `configuration`

### `security`

- [api-security.md](api-security.md) — **API Security**
  - `Standard` · `Accepted` · `api`, `security`
- [data-redaction-policy.md](data-redaction-policy.md) — **Data Redaction Policy**
  - `Standard` · `Accepted` · `security`, `observability`
- [identity-resolution.md](identity-resolution.md) — **Identity Resolution**
  - `Standard` · `Accepted` · `security`, `api`
- [technology-slowapi.md](technology-slowapi.md) — **Technology Selection: SlowAPI**
  - `Selection` · `Accepted` · `security`, `api`

### `testing`

- [testing-standards.md](testing-standards.md) — **Testing Standards**
  - `Standard` · `Accepted` · `testing`, `architecture`
