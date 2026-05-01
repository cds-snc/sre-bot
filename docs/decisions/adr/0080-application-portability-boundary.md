---
adr_id: ADR-0080
title: "Application Portability Boundary"
status: Accepted
decision_type: Principle
tier: Tier-1
primary_domain: Governance and Operating Model
secondary_domains:
  - Delivery and Environment Parity
  - Dependency and Composition
owners:
  - SRE Team
date_created: 2026-05-01
last_updated: 2026-05-01
last_reviewed: 2026-05-01
next_review_due: 2026-08-29
constrained_by:
  - ADR-0044
impacts:
  - ADR-0045
  - ADR-0052
  - ADR-0054
  - ADR-0067
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0044
  - ADR-0045
  - ADR-0046
  - ADR-0047
  - ADR-0052
  - ADR-0054
  - ADR-0067
  - ADR-0068
  - ADR-0069
related_packages: []
---

# Application Portability Boundary

## Context

- Problem statement: The ADR corpus (ADR-0044 through ADR-0079) implicitly governs the Python FastAPI application but never defines the boundary between **application architecture** and **hosting infrastructure**. This creates three recurring problems:
  1. **Scope ambiguity:** ADRs written for the in-process application (e.g., ADR-0067 "any feature or subsystem") are ambiguously applicable to independently deployed infrastructure components (Lambda functions, EventBridge rules, CI/CD workflows) that never run inside the FastAPI process.
  2. **Portability leakage:** Application ADRs contain infrastructure-specific implementation guidance (e.g., ADR-0052 prescribes "Move release-phase configuration binding to the ECS task definition level") alongside portable app-side contracts ("configuration must be resolved and injected before the container starts"). If the app moves from ECS to Kubernetes, the first statement survives; the second does not. Without a boundary, reviewers cannot distinguish portable norms from platform-specific fulfillment.
  3. **Governance gaps:** Purely infrastructure concerns (CI/CD pipeline validation, cloud-native alerting, container orchestration tuning) fall outside any ADR's explicit scope, leaving them ungoverned despite having significant operational impact.

- Business/operational drivers:
  - The application is undergoing an active portability refactoring (org-agnostic, cloud-agnostic, runnable on any container runtime or locally) with no governing authority backing this posture.
  - Infrastructure components (Lambda alerting, GitHub Actions workflows, ECS task definitions, Terraform resources) need their own governance records without conflicting with application ADRs.
  - Future platform migrations (ECS → Kubernetes, AWS → Azure, GitHub Actions → another CI) must not require re-reviewing application ADRs to determine which parts are portable.

- Constraints:
  - Must not duplicate or contradict ADR-0044 (Tier-0 governance model).
  - Must not alter any existing application ADR's normative content — this record establishes a boundary, not new application rules.
  - Both domains share the same repository and the same ADR governance process (ADR-0044).

- Non-goals:
  - This record does not create infrastructure-specific ADRs. It establishes the boundary principle that enables future infrastructure ADRs to be authored without scope conflicts.
  - This record does not prescribe specific infrastructure technologies (ECS, Lambda, Kubernetes, Terraform). Those are infrastructure-domain decisions.
  - This record does not change the application's internal architecture (layers, DI, Protocols, settings). Those remain governed by ADR-0045 and its downstream ADRs.

## Decision

- Chosen approach: Establish the Application Portability Boundary as a foundational Tier-1 principle that explicitly defines two governance domains within the same repository, with a contract-based interface between them.

- Why this approach: The Twelve-Factor App methodology requires "a clean contract with the underlying operating system, offering maximum portability between execution environments." Hexagonal Architecture (Cockburn) and Clean Architecture (Martin) both mandate that application core logic be decoupled from infrastructure adapters. The CNCF Cloud Native Definition emphasizes "loosely coupled systems" with "clear separation of concerns." This boundary principle codifies these established patterns into the ADR governance model, preventing infrastructure-specific decisions from contaminating portable application ADRs and vice versa.

### Principle 1: Two Governance Domains

The repository contains two distinct governance domains:

1. **Application architecture** — the Python FastAPI codebase (`app/`). Governed by application ADRs (ADR-0044 through ADR-0079 and their successors). Must be cloud-agnostic, organization-agnostic, and deployable on any container runtime or locally. In-app service integrations (Slack provider, DynamoDB client, etc.) are mediated through Protocol contracts (ADR-0045 Principle 6) and are application concerns.

2. **Hosting infrastructure** — CI/CD pipelines, container orchestration (ECS, Kubernetes), cloud-native automation (Lambda, SNS, EventBridge), load balancing, DNS, WAF, Terraform, and any component that is deployed and operated independently of the FastAPI process. Governed by infrastructure-specific ADRs (to be created as needed under the same ADR-0044 governance process). These components are cloud-specific by nature and replaceable without application code changes.

### Principle 2: Contract-Based Interface

Application ADRs must state **app-side contracts** — requirements the application imposes on its runtime environment — without prescribing how a specific hosting platform fulfills them. Infrastructure ADRs define how a specific platform satisfies those contracts.

| Concern | Application ADR states | Infrastructure ADR defines |
|---------|----------------------|---------------------------|
| Configuration | "All config must arrive as environment variables before process start" (ADR-0047 P5) | How ECS task definitions, Kubernetes ConfigMaps, or `.env` files inject those variables |
| Secrets | "Credentials must originate from environment variables or secrets management" (ADR-0045 P5) | Whether AWS Secrets Manager, Vault, or SOPS provides the secrets |
| Port binding | "The app binds to a configured port and serves HTTP" (ADR-0053) | How ALB, Ingress controllers, or reverse proxies route traffic to that port |
| Logging | "App emits structured logs to stdout/stderr" (ADR-0054) | How CloudWatch, Datadog, or ELK collects and routes those logs |
| Health checks | "App exposes a health endpoint" | How ECS health checks, Kubernetes liveness probes, or ALB target groups consume it |

### Principle 3: ADR Scope Constraint

- Application ADRs (currently ADR-0044 through ADR-0079) govern code running **within the FastAPI ASGI lifespan**. They must not contain infrastructure-specific implementation requirements (e.g., "use ECS task definition secrets," "configure Lambda timeout to 30s").
- Infrastructure ADRs govern components **deployed and operated independently** of the FastAPI process. They follow the same ADR-0044 governance process (metadata, tiers, challenge review) but are not constrained by application-specific principles (layer separation, Protocol contracts, plugin registration) unless those components interact with the application's contract surface.
- When an existing application ADR contains infrastructure-specific guidance, that guidance must be treated as **informational context**, not normative constraint. Future amendments should migrate such guidance to infrastructure ADRs or clearly label it as "infrastructure fulfillment example."

### Principle 4: Portability Invariant

The application ADR corpus must remain valid and enforceable if the hosting platform changes entirely (e.g., ECS → Kubernetes, AWS → Azure, GitHub Actions → GitLab CI). Any norm in an application ADR that would not survive such a migration is either:

- **(a)** An infrastructure-specific concern that belongs in an infrastructure ADR, or
- **(b)** A violation of this boundary principle that must be corrected.

This invariant formalizes the active portability refactoring posture and provides architectural authority for the direction.

## Alternatives Considered

1. Amend ADR-0045 to add a Principle 8 (Application Portability Boundary):

   - Pros: Single Tier-1 record for all foundational principles; no new ADR to track.
   - Cons: ADR-0045 is already at 7 principles and ~290 lines. Its `primary_domain` is "Dependency and Composition" — the governance boundary is a meta-architectural concern closer to "Governance and Operating Model." Adding a boundary principle with domain definitions, contract tables, and portability invariants would violate ADR-0044's "one decision, one authority level" rule. ADR-0045 governs _how the application is structured internally_; this decision governs _what the application ADR corpus applies to_.
   - Why not chosen: Different decision, different domain. ADR-0045's seven principles constrain the app's internal architecture; this principle constrains the _scope_ of the entire ADR corpus. Mixing them creates the same scope leakage that ADR-0045's own rewrite was designed to eliminate.

2. Do not codify the boundary; handle case-by-case:

   - Pros: No new ADR to author or maintain.
   - Cons: Every new infrastructure component (Lambda function, Step Function, EventBridge rule, future Kubernetes operator) requires a case-by-case ADR scope interpretation. The ADR-0067 scope ambiguity would recur for each new infrastructure component. The portability refactoring has no architectural authority backing it.
   - Why not chosen: The gap analysis that prompted this ADR identified the missing boundary as the structural root cause of three separate scope-related findings. Case-by-case handling does not scale.

3. Create a Tier-0 governance amendment instead of a Tier-1 principle:

   - Pros: Higher authority; governs the entire repository.
   - Cons: ADR-0044 governs _how_ decisions are made (process, metadata, tiers, review). This decision governs _what domains_ the decisions apply to (app vs. infrastructure). Adding domain scope rules to Tier-0 would mix governance process with architectural intent.
   - Why not chosen: The boundary is an architectural principle (Tier-1), not a governance process rule (Tier-0).

## Consequences

- Positive impacts:
  - Resolves the structural gap — no ADR previously defined the boundary between application architecture and hosting infrastructure.
  - Unblocks ADR-0067 scope clarification (P1 action) by providing the boundary definition that ADR-0067 can reference.
  - Provides architectural authority for the portability refactoring direction.
  - Enables future infrastructure ADRs (CI/CD validation, Lambda alerting, ECS tuning) to be authored without conflicting with application ADRs.
  - Prevents infrastructure-specific guidance from leaking into application ADRs in the future.
- Tradeoffs accepted:
  - Developers must identify which governance domain a decision belongs to before authoring an ADR. This adds a classification step but prevents costly scope conflicts later.
  - Existing application ADRs with infrastructure-specific guidance (e.g., ADR-0052's ECS references) are not immediately non-compliant — the guidance is reclassified as informational context, with future amendments migrating it to infrastructure ADRs.
- Risks introduced:
  - Decisions that straddle both domains (e.g., configuration injection, health checks) require careful decomposition into app-side contract and infrastructure fulfillment. Ambiguous cases may require judgment calls.
- Mitigations:
  - Principle 2 provides a concrete contract table pattern for decomposing straddling concerns.
  - The challenge review process (ADR-0044) catches boundary violations during authoring.

## Compliance and Boundaries

- ADR scope impact: This is the primary impact. All existing application ADRs (ADR-0044 through ADR-0079) are confirmed as application-domain records. Future infrastructure ADRs will be authored under the same governance process but with a distinct scope.
- Package/infrastructure boundary impact: No change to `app/` code structure. The boundary is at the governance level, not the code level. The existing layer separation (ADR-0045 P3) governs code structure within the application domain.
- Type boundary impact: None. Protocol/dataclass/BaseModel/TypedDict rules (ADR-0065) apply within the application domain and are unaffected.
- Startup/plugin registration impact: None. Plugin registration (ADR-0049) governs in-process startup within the application domain.
- Settings partitioning impact: Settings governance (ADR-0047) governs application-domain configuration. Infrastructure configuration (Terraform variables, ECS task definition parameters, GitHub Actions workflow inputs) is infrastructure-domain and not subject to ADR-0047's partitioning rules.
- Delivery pipeline impact: ADR-0052 (Build-Release-Run) straddles both domains. Its app-side norms (immutable artifacts, build-release-run separation, config-before-start contract) are application-domain. Its ECS-specific implementation guidance is infrastructure-domain context. This ADR does not require immediate amendment of ADR-0052, but future amendments should decompose accordingly.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: New Tier-1 principle record establishing the application vs. infrastructure governance boundary. Addresses the structural gap identified when investigating CI/CD pipeline governance questions.
- Follow-up actions:
  - Update ADR-0067 scope clarification (P1 action) to reference this boundary principle.
  - Assess ADR-0052 for infrastructure-specific guidance that should be reclassified or migrated.
  - Author infrastructure-domain ADRs as needed (CI/CD validation, alerting Lambda, ECS tuning).

## Source References (Required)

1. Source title: Twelve-Factor App Methodology
   - URL: <https://12factor.net/>
   - Publisher/maintainer: 12factor contributors (Heroku / Salesforce)
   - Accessed date (YYYY-MM-DD): 2026-05-01
   - Relevance summary: Introduction states the methodology is for apps that "have a clean contract with the underlying operating system, offering maximum portability between execution environments." Factor III (Config) separates app config from deploy config. Factor V (Build, release, run) separates build artifacts from runtime configuration. These principles directly support the contract-based interface (Principle 2) and portability invariant (Principle 4).

2. Source title: Hexagonal Architecture / Ports and Adapters (Cockburn)
   - URL: <https://en.wikipedia.org/wiki/Hexagonal_architecture_(software)>
   - Publisher/maintainer: Alistair Cockburn (original, 2005); Wikipedia (reference)
   - Accessed date (YYYY-MM-DD): 2026-05-01
   - Relevance summary: "The hexagonal architecture divides a system into several loosely-coupled interchangeable components, such as the application core, the database, the user interface, test scripts and interfaces with other systems." The application core communicates with external systems through ports (abstract APIs) and adapters (technical implementations). This pattern directly maps to Principle 2: the application states contracts (ports); infrastructure provides fulfillment (adapters).

3. Source title: Clean Architecture (Robert C. Martin)
   - URL: <https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html>
   - Publisher/maintainer: Robert C. Martin
   - Accessed date (YYYY-MM-DD): 2026-05-01
   - Relevance summary: "The overriding rule that makes this architecture work is The Dependency Rule. This rule says that source code dependencies can only point inwards." Infrastructure (frameworks, drivers, DB) lives in the outer ring; application logic lives in the inner rings. Infrastructure details must never leak into application rules. Directly supports Principle 3 (ADR Scope Constraint) — application ADRs must not contain infrastructure-specific requirements.

4. Source title: CNCF Cloud Native Definition v1.1
   - URL: <https://github.com/cncf/toc/blob/main/DEFINITION.md>
   - Publisher/maintainer: Cloud Native Computing Foundation (CNCF)
   - Accessed date (YYYY-MM-DD): 2026-05-01
   - Relevance summary: Defines cloud native as "loosely coupled systems that interoperate in a manner that is secure, resilient, manageable, sustainable, and observable" with "clear separation of concerns." The emphasis on loose coupling and separation of concerns between application workloads and infrastructure supports the two-domain governance model (Principle 1).

5. Source title: Government of Canada Cloud Adoption Strategy (2018 Update)
   - URL: <https://www.canada.ca/en/government/system/digital-government/digital-government-innovations/cloud-services/government-canada-cloud-adoption-strategy.html>
   - Publisher/maintainer: Treasury Board of Canada Secretariat
   - Accessed date (YYYY-MM-DD): 2026-05-01
   - Relevance summary: Principle 8: "Departments and agencies should consider portability and interoperability of services when designing cloud-based solutions." Principle 7: "develop an appropriate exit strategy before using cloud services." Both principles require that application design be separable from hosting platform — the portability invariant (Principle 4) codifies this for the ADR corpus.

6. Source title: AWS Well-Architected Framework — Operational Excellence Pillar
   - URL: <https://docs.aws.amazon.com/wellarchitected/latest/framework/oe-design-principles.html>
   - Publisher/maintainer: Amazon Web Services
   - Accessed date (YYYY-MM-DD): 2026-05-01
   - Relevance summary: "Use managed services to reduce operational burden" and "Build operational procedures around interactions with those services." The framework explicitly separates application design principles from operational/infrastructure design principles — each pillar addresses different concerns. This structural separation supports the two-domain governance model.

7. Source title: Documenting Architecture Decisions (Nygard, 2011)
   - URL: <https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions>
   - Publisher/maintainer: Cognitect (Michael Nygard)
   - Accessed date (YYYY-MM-DD): 2026-05-01
   - Relevance summary: "Each record describes a set of forces and a single decision in response to those forces." The governance boundary decision has distinct forces (portability, scope ambiguity, infrastructure governance gaps) from ADR-0045's forces (layer separation, DI, fail-fast). This supports creating a separate ADR rather than amending ADR-0045.

## Implementation Guidance

- Required changes:
  - No immediate code changes. This is a governance-level decision.
  - Update migration map to reflect ADR-0080 allocation and status.
  - Future ADR authoring must classify the target governance domain (application vs. infrastructure) before drafting.
- Validation and quality gates:
  - Challenge review must verify that new application ADRs do not contain infrastructure-specific normative requirements.
  - Challenge review must verify that new infrastructure ADRs follow the same ADR-0044 governance process.
- Test strategy and acceptance criteria impact:
  - No direct test changes. The boundary is validated through ADR review process, not automated tests.

## Change Log

- 2026-05-01: Created. Establishes the Application Portability Boundary as a Tier-1 principle defining two governance domains (application architecture vs. hosting infrastructure) with a contract-based interface. Addresses the structural gap identified when investigating CI/CD pipeline governance questions.
- 2026-05-01: Accepted. Challenge review R1 PASS. User accepted.
