---
adr_id: ADR-0053
title: "Port Binding and Runtime Exposure Standard"
status: Accepted
decision_type: Standard
tier: Tier-2
primary_domain: Delivery and Environment Parity
secondary_domains:
  - Transport and API
owners:
  - SRE Team
date_created: 2026-04-28
last_updated: 2026-04-28
last_reviewed: 2026-04-28
next_review_due: 2026-08-26
constrained_by:
  - ADR-0044
  - ADR-0051
  - ADR-0052
impacts:
  - ADR-0063
  - ADR-0064
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0033
  - ADR-0039
related_packages:
  - app/server
---
## Context

- Problem statement: Port exposure and runtime binding behavior were implicit across server and deployment layers, increasing configuration drift risk. The current deployment hardcodes port 8000 in three separate locations — `app/bin/entry.sh` (Uvicorn invocation), `terraform/ecs.tf`, and `terraform/templates/sre-bot.json.tpl` — with no settings-driven bind contract and no `PORT` or `HOST` configuration slice in `app/infrastructure/configuration/infrastructure/server.py`. This means the exposure contract is scattered and cannot be changed without source modifications across multiple layers.
- Business/operational drivers:
  - Define one stable, settings-driven contract for service exposure in every environment.
  - Eliminate environment-specific hardcoding of network bind settings across entrypoint, container manifest, and Terraform.
- Constraints:
  - Must align with Twelve-Factor factor VII (Port Binding).
  - Must support containerized and non-containerized runtime paths.
- Non-goals:
  - This record does not define ingress/load-balancer vendor specifics.

## Decision

- Chosen approach:
  - Services expose themselves via a configured runtime port and host binding contract.
  - Runtime bind target (host and port) is supplied through settings/environment configuration, not source-level constants. The canonical setting names are `SERVER_HOST` and `SERVER_PORT`, owned by the infrastructure/server settings slice.
  - Port 8000 is the designated service port for this platform. It must be declared once as a settings default and referenced from that authority everywhere else; it must not be independently hardcoded in entrypoint scripts, container manifests, or Terraform resources.
  - Health and readiness probes must operate through the same externally exposed service interface (the bound host:port). They must not rely on localhost bypasses or side-ports not declared in the deployment manifest.
  - Internal admin endpoints must remain explicitly scoped and must not piggyback on undocumented side ports.
- Why this approach:
  - Makes service exposure predictable and auditable across local, CI preview, and production environments.
  - Eliminates three-way hardcode drift by making settings the single authority.
- Principles established:
  - Port binding is application responsibility, expressed through settings.
  - Exposure contract is configuration-driven, not source-driven.

### Known Migration Gap

The following artifacts currently violate this standard and require migration before compliance is achieved:

| Artifact | Current Behaviour | Required Change |
|---|---|---|
| `app/bin/entry.sh` | Invokes Uvicorn with `--host=0.0.0.0` and no port flag (Uvicorn defaults to 8000) | Read `SERVER_HOST` and `SERVER_PORT` from environment; pass explicitly to Uvicorn |
| `terraform/ecs.tf` | Pins container and host port to hardcoded 8000 | Reference a Terraform variable or SSM-resolved value aligned to the settings default |
| `terraform/templates/sre-bot.json.tpl` | Hardcodes port 8000 in container port mapping | Reference the same Terraform variable |
| `app/infrastructure/configuration/infrastructure/server.py` | No `SERVER_HOST` or `SERVER_PORT` setting exists | Add typed `SERVER_HOST` (default `0.0.0.0`) and `SERVER_PORT` (default `8000`) settings |

## Alternatives Considered

1. Hardcode bind host/port by environment profile.
   - Pros: Simple implementation in one code path.
   - Cons: Drift-prone and brittle across deployment targets.
   - Why not chosen: Violates Twelve-Factor port-binding expectations.
2. Rely solely on external wrappers to expose the service.
   - Pros: App code remains minimal.
   - Cons: Runtime exposure contract is hidden and less testable.
   - Why not chosen: Ownership must remain explicit in architecture records.

## Consequences

- Positive impacts:
  - Reduced ambiguity in environment-specific runtime wiring.
  - Better portability and clearer operations diagnostics.
- Tradeoffs accepted:
  - Requires consistent deployment configuration for bind values.
- Risks introduced:
  - `app/bin/entry.sh`, `terraform/ecs.tf`, `terraform/templates/sre-bot.json.tpl`, and the server settings module all currently violate this standard. They must be migrated together; a partial migration leaves a split authority between old hardcodes and new settings.
  - Downstream ADRs (ADR-0063, ADR-0064) must not treat the env-driven contract as already implemented; it is the migration target.
- Mitigations:
  - Track migration via a dedicated Tier-5 decision that owns the four-file migration and defines the acceptance test (startup fails explicitly when SERVER_PORT is missing or invalid).

## Compliance and Boundaries

- Package/infrastructure boundary impact:
  - No business-domain changes; this governs server/runtime exposure policy.
- Type boundary impact (Protocol/dataclass/BaseModel/TypedDict):
  - Not applicable.
- Startup/plugin registration impact:
  - Startup checks should validate exposure configuration before serving traffic.
- Settings partitioning impact:
  - Bind settings belong in infrastructure/server settings and should be injected as config.

## Best-Practice Revalidation

- Revalidation date: 2026-04-28
- Sources rechecked:
  - Twelve-Factor factor VII (port binding)
  - FastAPI deployment/runtime guidance for externally served applications
- Alignment summary:
  - Decision aligns with application-owned service exposure and env-driven bind configuration.
- Intentional deviations:
  - None.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Port-binding concern now has explicit Tier-2 ownership. The desired end state (settings-driven bind contract) is defined. The current deployment is a known non-compliant baseline; compliance requires the four-file migration described in the Decision section and Implementation Guidance.
- Follow-up actions:
  - Author a Tier-5 migration ADR covering the `entry.sh`, `terraform/ecs.tf`, `terraform/templates/sre-bot.json.tpl`, and server settings changes as a single atomic migration unit.
  - Do not allow downstream ADRs to treat the env-driven contract as currently implemented.

## Source References (Required)

1. Source title: The Twelve-Factor App - Port Binding
   - URL: https://12factor.net/port-binding
   - Publisher/maintainer: 12factor contributors
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Defines self-contained app exposure via bound ports.
2. Source title: FastAPI Deployment Concepts
   - URL: https://fastapi.tiangolo.com/deployment/concepts/
   - Publisher/maintainer: FastAPI maintainers
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Provides runtime/deployment expectations for exposing FastAPI services.
3. Source title: Build-Release-Run Delivery Standard
   - URL: docs/decisions/adr/0052-build-release-run-delivery-standard.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-28
   - Relevance summary: Constrains runtime exposure behavior to released artifacts and environment configuration.

## Implementation Guidance

- Required changes:
  - Add `SERVER_HOST` (str, default `0.0.0.0`) and `SERVER_PORT` (int, default `8000`) to `app/infrastructure/configuration/infrastructure/server.py` as the single authority for bind values.
  - Update `app/bin/entry.sh` to read `$SERVER_HOST` and `$SERVER_PORT` and pass them as explicit Uvicorn arguments.
  - Update `terraform/ecs.tf` and `terraform/templates/sre-bot.json.tpl` to derive the container port from a shared Terraform variable rather than a hardcoded literal.
  - Align health and readiness probe targets in the ECS task definition to the declared `SERVER_PORT` rather than a separately hardcoded value.
  - Startup must fail with a clear error message if bind configuration is absent or invalid; silent fallback to a default is not acceptable after migration.
- Validation and quality gates:
  - Validate runtime startup fails clearly when bind configuration is invalid or absent.
  - Confirm deployment manifests derive bind parameters from settings rather than independent literals.
  - Confirm health/readiness probes reference the same port declared in settings.
- Test strategy and acceptance criteria impact:
  - Route and startup tests must cover valid and invalid bind configuration paths.
  - Acceptance test: container starts successfully with `SERVER_PORT` set; container fails with a logged error when `SERVER_PORT` is set to an unparseable value.

## Change Log

- 2026-04-28: Added Tier-2 standard for Twelve-Factor port binding ownership and runtime exposure contract.
- 2026-04-28: Revised following REVISE challenge-review gate; named existing hardcode violations explicitly, defined migration gap table, tightened probe interface wording, and scoped SERVER_HOST/SERVER_PORT as the canonical settings authority.
