# ADR Challenge and Content Review

## 1. Review Metadata

| Field | Value |
|-------|-------|
| **ADR Under Review** | ADR-0053: Port Binding and Runtime Exposure Standard |
| **Reviewer Name & Title** | SRE Team, Architecture Reviewer |
| **Secondary Reviewers** | None |
| **Review Date** | 2026-04-28 |
| **Revalidation Due** | 2027-04-28 |
| **Gate Outcome** | **REVISE** |
| **Outcome Rationale** | The ADR is well grounded in Twelve-Factor and FastAPI guidance, but its core normative statement assumes an env-driven bind contract that the current repository does not actually implement. The record needs to either reflect the fixed-port ECS baseline or explicitly define the change as a migration target. |

## 2. Evidence Gathering & Convention Validation

### 2.A Language & Framework Standards

**Applicable Standards:**
- FastAPI Official Documentation
- Starlette / process model implications via FastAPI deployment guidance

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| FastAPI deployment concepts | FastAPI deployment runtime startup restarts workers ports | FastAPI deployment guidance assumes an externally supervised process model and notes that only one process can listen on a given IP:port combination, with external orchestration handling replication. | ✅ Aligned | None |
| FastAPI deployment concepts | FastAPI separate startup supervisor previous steps | Startup, restart, and process management belong to external tooling, which fits the ADR's effort to define a runtime exposure contract. | ✅ Aligned | None |

### 2.B Infrastructure & Operational Standards

**Applicable Standards:**
- Twelve-Factor App Methodology

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| Twelve-Factor App - Port Binding | export services via port binding env-agnostic runtime exposure | The app should export HTTP by binding to a port, with routing layers forwarding to port-bound processes. | ✅ Aligned | None |
| Repository deployment artifacts | ECS task definition and ALB port mapping | The repository currently standardizes on a fixed container and host port of 8000, not a runtime `PORT` setting. | ⚠️ Deviation | Current deployment contract is fixed-port ECS/ALB, while the ADR states an env-driven bind target. |

### 2.C Cross-Cutting Design Patterns

**Applicable Standards:**
- Dependency Injection Best Practices
- Observability and deployment configuration boundaries

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| Repository server configuration | server settings HOST/PORT bind configuration | The server settings model defines `BACKEND_URL` but no explicit `PORT` or `HOST` configuration slice. | ⚠️ Deviation | The ADR's chosen contract is not yet represented in settings or deployment configuration. |

### 2.D Validation Summary

**Total Standards Checked:** 4  
**Aligned with Best Practice:** 2  
**Deliberate Deviations:** 2

**High-Level Finding:**
- 🔴 **Gaps Found:** Missing alignment between the ADR's normative bind contract and the repository's current deployment baseline

**Deviation Summary:**
- `app/bin/entry.sh` launches `uvicorn main:server_app --host=0.0.0.0` with no env-driven port setting.
- `terraform/templates/sre-bot.json.tpl` and `terraform/ecs.tf` explicitly pin the service to port 8000.
- `app/infrastructure/configuration/infrastructure/server.py` has no `PORT` or `HOST` setting that would make the ADR's contract concrete.

## 3. Assumptions Challenged

### Assumption 3.1: Runtime bind target is supplied through environment configuration
- **Stated Norm:** "Runtime bind target is supplied through environment configuration (for example `PORT`), not source changes."
- **Underlying Assumption:** The repository already has, or is ready to adopt without ambiguity, an env-driven bind contract.
- **Challenge:** Current deployment artifacts do not expose that contract. They hardcode port 8000 through Terraform and the container entrypoint.
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** Yes → `app/bin/entry.sh`, `terraform/templates/sre-bot.json.tpl`, `terraform/ecs.tf`, and `app/infrastructure/configuration/infrastructure/server.py` all contradict the stated norm.
- **Confidence (ADR survives challenge):** 🔴 Low
- **Reviewer Notes:** This is the primary blocker. The ADR needs revision before downstream work relies on it.

### Assumption 3.2: Health and readiness probes should operate through the same externally exposed service interface
- **Stated Norm:** "Health and readiness probes must operate through the same externally exposed service interface."
- **Underlying Assumption:** The repo has a clearly defined exposure interface and can distinguish that interface from admin-only endpoints.
- **Challenge:** The ADR does not define whether the current ALB and container contract counts as that interface, nor how admin-only endpoints are expected to differ.
- **Evidence Strength:** ⭐⭐ Moderate
- **Counter-Evidence Found:** Partial → the deployment stack exposes a single fixed port, but the ADR leaves the present baseline under-specified.
- **Confidence (ADR survives challenge):** 🟡 Moderate
- **Reviewer Notes:** This could be resolved with clarifying language once the bind-contract baseline is corrected.

## 4. Failure Modes Identified

### Failure Mode 4.1: Downstream ADRs assume a configurable bind contract that does not exist
- **If Assumption Fails:** Later ADRs, tests, or runtime refactors assume `PORT`-driven configuration and make decisions that conflict with the fixed ECS/ALB baseline.
- **Platform Impact:**
  - Incident management workflow: Medium
  - Access synchronization workflow: Medium
  - Access request workflow: Medium
  - Multi-provider integrations (Slack, Teams, GWS, AWS, GitHub): Medium
- **Probability Estimate:** High %
- **Mitigation or Acceptance:** Revise ADR-0053 to describe either the current fixed-port standard or an explicit migration path from fixed-port to env-driven binding.

### Failure Mode 4.2: Operators interpret "same externally exposed service interface" differently
- **If Assumption Fails:** Health checks, readiness checks, and admin endpoints diverge without a clear standard, creating inconsistent deployment and troubleshooting behavior.
- **Platform Impact:**
  - Incident management workflow: High
  - Access synchronization workflow: Low
  - Access request workflow: Medium
  - Multi-provider integrations (Slack, Teams, GWS, AWS, GitHub): Low
- **Probability Estimate:** Medium %
- **Mitigation or Acceptance:** Clarify the intended exposure interface and any allowed exceptions in the revised ADR.

## 5. Contradiction Audit

### Cross-ADR Contradictions

| Conflict | ADRs Involved | Severity | Resolution Status |
|----------|---------------|----------|-------------------|
| ADR-0053 states an env-driven bind target, while the current deployment baseline is a fixed ECS/ALB port 8000. | ADR-0053, current deployment artifacts | 🔴 High | ⚪ Unresolved |
| ADR-0053 implies settings-driven bind control, but the server settings model does not define bind settings. | ADR-0053, current server settings model | 🟡 Medium | ⚪ Unresolved |
| No conceptual contradiction found with Twelve-Factor or FastAPI guidance. | ADR-0053, Twelve-Factor, FastAPI docs | 🟢 Low | ✅ Resolved |

### Supersession Ambiguities

- **ADRs this one supersedes:** None
- **Inheritance Status:** `constrained_by` links to ADR-0044, ADR-0051, and ADR-0052 are structurally correct.
- **Gaps Identified:** The ADR does not distinguish current-state baseline from future-state migration target.

### Ownership Clarity

- **Primary Domain Owner:** SRE Team
- **Secondary Domain Owners:** None
- **Plugin/Startup Registration:** Not owned here
- **Config Owner:** Should be inherited from the later canonical configuration ADR, but bind settings are not yet modeled
- **Audit Result:** ⚠️ Needs Clarification → runtime bind ownership is conceptually clear, but the concrete configuration surface is missing

## 6. Scenario Validation Matrix

### Scenario 6.1: Incident Management Workflow
**Context:** Emergency response requires rapid operational decision-making under time pressure.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Health and readiness clarity | Incident responders need a clear, stable service interface to verify service health. | The deployment stack clearly uses port 8000 today, but the ADR describes a different bind contract. | ⚠️ Yes | This creates ambiguity during incident triage. |

**Validation Summary:**
- 🔴 Misaligned → Revision required

**Mitigation:** Revise the ADR so the current health and exposure contract is accurately stated.

### Scenario 6.2: Access Synchronization Workflow
**Context:** Automated sync jobs and HTTP surfaces must behave predictably.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Runtime exposure predictability | HTTP ingress paths should have a clear bind contract. | The repo can support a single fixed port today, but the ADR does not acknowledge that baseline. | ⚠️ Yes | Not a workflow-specific blocker, but still a platform-contract ambiguity. |

**Validation Summary:**
- ⚠️ Aligned with documented exception handling

**Mitigation:** Either document fixed-port 8000 as the standard or add a migration clause.

### Scenario 6.3: Access Request Workflow
**Context:** User-facing HTTP request flows need stable exposure and health behavior.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Bind contract for HTTP APIs | The service exposure contract should be explicit and testable. | Access request routes assume a stable HTTP service, but current deployment evidence points to a fixed contract rather than the stated env-driven one. | ⚠️ Yes | The ADR needs to match the repo contract before it constrains API-composition ADRs. |

**Validation Summary:**
- ⚠️ Aligned with documented exception handling

**Mitigation:** Clarify the canonical contract and how it is configured.

### Scenario 6.4: Multi-Provider Integration (Slack/Teams/AWS/GWS/GitHub)
**Context:** Provider-heavy workflows depend on reliable runtime exposure.

| Aspect | ADR Requirement | Integration Reality | Gap? | Notes |
|--------|-----------------|---------------------|------|-------|
| Stable ingress expectations | The app should present one stable service interface to upstream infrastructure. | The repo already does that with a single ALB and container port, but the ADR's specific env-driven statement is not what is deployed. | ⚠️ Yes | The issue is accuracy of the canonical statement, not the value of having a standard. |

**Validation Summary:**
- ⚠️ Aligned with documented exception handling

**Mitigation:** Revise wording to match or deliberately migrate from the fixed-port baseline.

## 7. Tradeoffs Accepted

### Tradeoff 7.1: Portable generic standard vs. current deployment accuracy
- **Chosen:** The ADR currently favors a generic env-driven contract.
- **Rejected:** An ADR that first states the fixed ECS/ALB baseline and then scopes future change separately.
- **Rationale:** Generic wording is attractive because it looks environment-agnostic.
- **Risk Accepted:** Downstream readers may treat a non-existent configuration surface as canonical.
- **Contingency:** Revise ADR-0053 before using it as an upstream constraint.

### Tradeoff 7.2: Simplicity of one exposure rule vs. migration clarity
- **Chosen:** Single exposure rule without explicit migration framing.
- **Rejected:** Current-state rule plus Tier-5 migration path.
- **Rationale:** A short standard is easier to author.
- **Risk Accepted:** The gap between present infra and stated contract becomes hidden.
- **Contingency:** Add explicit current-state and migration language in revision.

## 8. Follow-Up Actions

| Action | Blocker? | Owner | Due Date | Description |
|--------|----------|-------|----------|-------------|
| Revise bind-contract statement | ✅ Yes | SRE Team | 2026-05-05 | Update ADR-0053 to either define fixed-port 8000 as the current standard or mark env-driven binding as a migration target with explicit scope. |
| Add explicit settings/deploy surface | ✅ Yes | SRE Team | 2026-05-05 | If env-driven binding remains the target, define concrete `PORT`/`HOST` settings and deployment wiring instead of relying on implied configuration. |
| Clarify probe interface wording | ❌ No | SRE Team | 2026-05-05 | Specify what counts as the canonical externally exposed service interface for health and readiness behavior. |

**Blocking Actions Must Resolve Before Step 10 Proceeds:** Yes.

## 9. Binary Gate Outcome

**GATE DECISION:**

**REVISE** → ADR-0053 requires authoring revision; return to Step 5-9 author team with feedback

**If REVISE, Provide Primary Blockers:**
1. The ADR's env-driven bind target is contradicted by the current fixed-port ECS and entrypoint baseline.
2. The configuration surface for bind settings is not defined in the repository's server settings.
3. The probe-interface wording is too vague to safely constrain downstream ADRs.

**Revision Deadline:** 2026-05-05

## 10. Reviewer Sign-Off

| Field | Signature/Value |
|-------|-----------------|
| **Reviewer Name** | SRE Team |
| **Reviewer Title** | Architecture Reviewer |
| **Organization/Team** | SRE Team |
| **Sign-Off Date** | 2026-04-28 |
| **Email** | Not provided |

## 11. Review Artifacts Reference

**This Review Record Should Be Attached To:**
- Step 5 ADR challenge-review packet for canonical ADRs
- Follow-on revision work for ADR-0053

**This Review Template Was Completed Per:**
- ADR-0044 (Governance and Operating Model) § Step 9.5
- Revalidation Cycle: One-time gate review → annual review_state cycle
