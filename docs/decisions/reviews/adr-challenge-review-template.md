# ADR Challenge and Content Review Template

**Purpose:** Standardized artifact for Step 9.5 (Canonical ADR Challenge and Content Review Gate) execution. Used to validate newly authored replacement ADRs (Phase A-E) for content soundness, assumption correctness, and platform-reality alignment before cascade rewrites proceed.

---

## 1. Review Metadata

| Field | Value |
|-------|-------|
| **ADR Under Review** | ADR-XXXX: [Title] |
| **Reviewer Name & Title** | [Full Name], [Role/Team] |
| **Secondary Reviewers** | [Optional: comma-separated list] |
| **Review Date** | [YYYY-MM-DD] |
| **Revalidation Due** | [YYYY-MM-DD, typically 12 months from review] |
| **Gate Outcome** | ⚪ **PASS** \| ⚪ **REVISE** |
| **Outcome Rationale** | [1-2 sentences: why pass or why revise required] |

---

## 2. Evidence Gathering & Convention Validation

**Requirement:** Before challenging assumptions, identify and search authoritative sources that govern the domain covered by this ADR. Document findings to establish whether the ADR aligns with or deliberately deviates from widely accepted best practices.

All ADRs must be anchored in official documentation and authoritative best practices. Exceptions (deliberate deviations) require explicit rationale and accepted risk. Current code might be outdated or non-compliant; the ADR must be evaluated against standards, not current implementation.

### 2.A Language & Framework Standards

**Applicable Standards (check all that apply):**

- ⚪ Python Enhancement Proposals (PEP 8, PEP 20, PEP 484, PEP 585, etc.)
- ⚪ FastAPI Official Documentation (<https://fastapi.tiangolo.com/>)
- ⚪ Pydantic V2 Documentation (<https://pydantic.dev/docs/validation/latest/get-started/>)
- ⚪ Pydantic Settings V2 (<https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/>)
- ⚪ Pluggy Documentation & Best Practices (<https://pluggy.readthedocs.io/>)
- ⚪ Python Typing Module Official Docs
- ⚪ Structlog Documentation (<https://www.structlog.org/en/stable/>)
- ⚪ Starlette Documentation (ASGI framework underlying FastAPI)
- ⚪ Uvicorn Documentation (<https://www.uvicorn.org/>)
- ⚪ HTTPX Documentation (<https://www.python-httpx.org/>)
- ⚪ Authlib Documentation (<https://docs.authlib.org/en/latest/>) — OAuth/OIDC library
- ⚪ PyJWT Documentation (<https://pyjwt.readthedocs.io/en/stable/>) — JWT handling
- ⚪ Pytest Documentation (<https://docs.pytest.org/en/stable/>) — including conftest, fixtures, parametrize patterns
- ⚪ pytest-asyncio Documentation (<https://pytest-asyncio.readthedocs.io/en/latest/>) — async test patterns
- ⚪ Mypy Documentation (<https://mypy.readthedocs.io/en/stable/>) — static type checking
- ⚪ Black Documentation (<https://black.readthedocs.io/en/stable/>) — code formatting standard
- ⚪ Flake8 Documentation (<https://flake8.pycqa.org/en/latest/>) — linting standard
- ⚪ Other: [Specify]

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| [e.g., "PEP 8: Style Guide"] | [What did you search?] | [What does the standard say?] | ✅ Aligned \| ⚠️ Deviation | [If deviation: why?] |
| [e.g., "FastAPI Lifespan Events"] | [What did you search?] | [What does the doc say?] | ✅ Aligned \| ⚠️ Deviation | [If deviation: why?] |
| [e.g., "Pluggy Plugin Registration"] | [What did you search?] | [What does the doc say?] | ✅ Aligned \| ⚠️ Deviation | [If deviation: why?] |

---

### 2.B Infrastructure & Operational Standards

**Applicable Standards (check all that apply):**

- ⚪ Twelve-Factor App Methodology (<https://12factor.net/>)
- ⚪ CNCF / Cloud-Native Best Practices
- ⚪ AWS Well-Architected Framework (for AWS-specific decisions)
- ⚪ Boto3 / AWS SDK for Python Documentation (<https://boto3.amazonaws.com/v1/documentation/api/latest/index.html>)
- ⚪ Structured Logging Standards (JSON, correlation IDs, etc.)
- ⚪ OWASP Security Best Practices
- ⚪ Slack Bolt for Python Documentation (<https://slack.dev/bolt-python/concepts>) — Slack integration framework
- ⚪ Microsoft Bot Framework SDK for Python Documentation (<https://learn.microsoft.com/en-us/azure/bot-service/python/bot-builder-python-sdk-quickstart>) — Teams integration framework (TurnContext, Adaptive Cards)
- ⚪ Google API Python Client Documentation (<https://googleapis.github.io/google-api-python-client/docs/>) — Google Workspace integration
- ⚪ Google Auth Library Documentation (<https://google-auth.readthedocs.io/en/stable/>) — Google authentication/authorization
- ⚪ SlowAPI Documentation (<https://slowapi.readthedocs.io/en/latest/>) — rate limiting middleware
- ⚪ External Provider Specs (Slack, Teams, GitHub, Google Workspace, AWS APIs)
- ⚪ Other: [Specify]

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| [e.g., "Twelve-Factor: Port Binding"] | [What did you search?] | [What does the standard say?] | ✅ Aligned \| ⚠️ Deviation | [If deviation: why?] |
| [e.g., "AWS IAM Best Practices"] | [What did you search?] | [What does the standard say?] | ✅ Aligned \| ⚠️ Deviation | [If deviation: why?] |
| [e.g., "Slack API Rate Limits"] | [What did you search?] | [What does the standard say?] | ✅ Aligned \| ⚠️ Deviation | [If deviation: why?] |

---

### 2.C Cross-Cutting Design Patterns

**Applicable Standards (check all that apply):**

- ⚪ Event-Driven Architecture Patterns
- ⚪ CQRS (Command Query Responsibility Segregation)
- ⚪ Eventual Consistency Patterns
- ⚪ Dependency Injection Best Practices
- ⚪ Circuit Breaker & Resilience Patterns
- ⚪ Observability & Logging Patterns (structured logs, tracing, metrics)
- ⚪ Idempotency Patterns (for distributed systems)
- ⚪ Other: [Specify]

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| [e.g., "Eventual Consistency Patterns"] | [What did you search?] | [What does the standard say?] | ✅ Aligned \| ⚠️ Deviation | [If deviation: why?] |
| [e.g., "Circuit Breaker Pattern"] | [What did you search?] | [What does the standard say?] | ✅ Aligned \| ⚠️ Deviation | [If deviation: why?] |

---

### 2.D Validation Summary

**Total Standards Checked:** [X]
**Aligned with Best Practice:** [X]
**Deliberate Deviations:** [X]

**High-Level Finding:**

- 🟢 **Fully Grounded:** All standards checked; no unresolved deviations
- 🟡 **Mostly Grounded:** Most standards checked; deviations have rationale
- 🔴 **Gaps Found:** Missing standard references or unexplained deviations; requires revision

**Deviation Summary (if 🟡 or 🔴):**
[List each deviation, its rationale, and accepted risk. If any deviation lacks clear rationale, flag for author clarification.]

---

## 3. Assumptions Challenged

For each architectural norm or constraint stated in the ADR, identify and challenge the underlying assumption. Document confidence level and evidence.

### Assumption 3.1: [Norm from ADR]

- **Stated Norm:** [Direct quote from ADR context/decision]
- **Underlying Assumption:** [What must be true for this to be valid?]
- **Challenge:** [How could this assumption fail in practice?]
- **Evidence Strength:** ⭐ Strong | ⭐⭐ Moderate | ⭐⭐⭐ Weak
- **Counter-Evidence Found:** [Yes / No] → [If yes, describe]
- **Confidence (ADR survives challenge):** 🟢 High | 🟡 Moderate | 🔴 Low
- **Reviewer Notes:** [Free-form assessment]

### Assumption 3.2: [Norm from ADR]

*(Repeat 3.1 structure for each major assumption)*

---

## 4. Failure Modes Identified

For each assumption that scored Moderate or Low confidence, identify specific failure scenarios and their impact on the platform.

### Failure Mode 4.1: [Assumption → Failure Scenario]

- **If Assumption Fails:** [Describe the concrete failure condition]
- **Platform Impact:**
  - Incident management workflow: [Impact: None | Low | Medium | High | Critical]
  - Access synchronization workflow: [Impact: None | Low | Medium | High | Critical]
  - Access request workflow: [Impact: None | Low | Medium | High | Critical]
  - Multi-provider integrations (Slack, Teams, GWS, AWS, GitHub): [Impact: None | Low | Medium | High | Critical]
- **Probability Estimate:** [Low % | Medium % | High %]
- **Mitigation or Acceptance:** [Describe how this is handled or accepted as risk]

### Failure Mode 4.2: [Assumption → Failure Scenario]

*(Repeat 4.1 structure for each identified failure mode)*

---

## 5. Contradiction Audit

Check for conflicts between the ADR under review and other canonical ADRs in scope. Identify unresolved ambiguities in ownership, responsibility, or interpretation.

### Cross-ADR Contradictions

| Conflict | ADRs Involved | Severity | Resolution Status |
|----------|---------------|----------|-------------------|
| [Conflict description] | ADR-XXXX, ADR-YYYY | 🟢 Low \| 🟡 Medium \| 🔴 High | ⚪ Unresolved \| ✅ Resolved → [Ref section] |
| [Conflict description] | ADR-XXXX, ADR-YYYY | 🟢 Low \| 🟡 Medium \| 🔴 High | ⚪ Unresolved \| ✅ Resolved → [Ref section] |

### Supersession Ambiguities

- **ADRs this one supersedes:** [List ADR-XXXX, ADR-YYYY]
- **Inheritance Status:** [Are all inherited constraints and impacts acknowledged in this ADR?]
- **Gaps Identified:** [If yes: list gaps; if no: none]

### Ownership Clarity

- **Primary Domain Owner:** [Named person/team]
- **Secondary Domain Owners:** [Named person/team, if applicable]
- **Plugin/Startup Registration:** [If applicable: clearly identify provider/package/pluggy contract]
- **Config Owner:** [Named service/file, or clarify "inherited from ADR-XXXX"]
- **Audit Result:** ✅ Clear | ⚠️ Needs Clarification → [Details]

---

## 6. Scenario Validation Matrix

Validate that the ADR's decisions and constraints are sound when applied across key platform workflows. Each scenario simulates a real operational pattern.

> **Important — Target-State Validation, Not Current-State Compliance**
>
> This matrix tests whether the ADR's rules *would produce correct behavior* if fully applied to each workflow. It does **not** assess whether current code already complies. At the time of this template's creation, no package in the application is fully ADR-compliant — all predate the ADR review program. The most mature package (access) was designed before the current architectural standards and may be partially non-compliant. Legacy features (e.g., webhooks) are expected to be substantially non-compliant.
>
> **Reviewer guidance:**
> - A gap means "the ADR's rule is wrong or unworkable for this workflow" — not "the code doesn't follow the ADR yet."
> - If current code deviates from the ADR, that is a *migration concern* (Section 8: Follow-Up Actions), not a scenario gap.
> - Use the workflow's *operational requirements* (what must be true for the workflow to function correctly) as the benchmark, not its current implementation.

### Scenario 6.1: Incident Management Workflow

**Context:** Emergency response requires rapid logging, context propagation, and operational decision-making under time pressure.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| [Requirement aspect] | [What ADR mandates] | [How incident team operates] | ✅ No \| ⚠️ Yes | [Explain gap or confirmation] |
| [Requirement aspect] | [What ADR mandates] | [How incident team operates] | ✅ No \| ⚠️ Yes | [Explain gap or confirmation] |

**Validation Summary:** [Does the ADR align with incident management reality?]

- ✅ Fully aligned
- ⚠️ Aligned with documented exception handling
- 🔴 Misaligned → Revision required

**Mitigation (if ⚠️):** [Document exception or required workaround]

---

### Scenario 6.2: Access Synchronization Workflow

**Context:** Automated sync from identity providers (AWS IAM, Google Workspace, GitHub) to application; must handle failure, retry, and eventual consistency.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| [Requirement aspect] | [What ADR mandates] | [How sync pipeline operates] | ✅ No \| ⚠️ Yes | [Explain gap or confirmation] |
| [Requirement aspect] | [What ADR mandates] | [How sync pipeline operates] | ✅ No \| ⚠️ Yes | [Explain gap or confirmation] |

**Validation Summary:** [Does the ADR align with access-sync pipeline reality?]

- ✅ Fully aligned
- ⚠️ Aligned with documented exception handling
- 🔴 Misaligned → Revision required

**Mitigation (if ⚠️):** [Document exception or required workaround]

---

### Scenario 6.3: Access Request Workflow

**Context:** User requests access to a resource/role; admin approves; system provisions and audits the action across multiple platforms.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| [Requirement aspect] | [What ADR mandates] | [How request system operates] | ✅ No \| ⚠️ Yes | [Explain gap or confirmation] |
| [Requirement aspect] | [What ADR mandates] | [How request system operates] | ✅ No \| ⚠️ Yes | [Explain gap or confirmation] |

**Validation Summary:** [Does the ADR align with access-request workflow reality?]

- ✅ Fully aligned
- ⚠️ Aligned with documented exception handling
- 🔴 Misaligned → Revision required

**Mitigation (if ⚠️):** [Document exception or required workaround]

---

### Scenario 6.4: Multi-Provider Integration (Slack/Teams/AWS/GWS/GitHub)

**Context:** Single operation may span multiple external APIs (rate limits, error handling, eventual consistency across platforms).

| Aspect | ADR Requirement | Integration Reality | Gap? | Notes |
|--------|-----------------|---------------------|------|-------|
| [Requirement aspect] | [What ADR mandates] | [How multi-provider ops behave] | ✅ No \| ⚠️ Yes | [Explain gap or confirmation] |
| [Requirement aspect] | [What ADR mandates] | [How multi-provider ops behave] | ✅ No \| ⚠️ Yes | [Explain gap or confirmation] |

**Validation Summary:** [Does the ADR align with multi-provider reality?]

- ✅ Fully aligned
- ⚠️ Aligned with documented exception handling
- 🔴 Misaligned → Revision required

**Mitigation (if ⚠️):** [Document exception or required workaround]

---

## 7. Tradeoffs Accepted

Document the explicit tradeoffs represented by this ADR's chosen option. Clarify what is being prioritized and what is being explicitly deferred or accepted as risk.

### Tradeoff 7.1: [Category - e.g., "Performance vs. Consistency"]

- **Chosen:** [The ADR's chosen branch]
- **Rejected:** [The alternative branch(es)]
- **Rationale:** [Why chosen > rejected]
- **Risk Accepted:** [What downside of the chosen branch will we live with?]
- **Contingency:** [If risk materializes, what is the escape hatch?]

### Tradeoff 7.2: [Category]

*(Repeat 7.1 structure for each material tradeoff)*

---

## 8. Follow-Up Actions

Capture blockers, clarifications needed, or issues discovered during review that require resolution before the ADR can be considered fully professional-grade.

| Action | Blocker? | Owner | Due Date | Description |
|--------|----------|-------|----------|-------------|
| [Action title] | ✅ Yes \| ❌ No | [Name/Team] | [YYYY-MM-DD] | [What needs to happen and why] |
| [Action title] | ✅ Yes \| ❌ No | [Name/Team] | [YYYY-MM-DD] | [What needs to happen and why] |

**Blocking Actions Must Resolve Before Step 10 Proceeds:** If any "Blocker? Yes" rows exist, the ADR revision must complete before cascade work begins.

---

## 9. Binary Gate Outcome

**GATE DECISION:**

⚪ **PASS** → ADR-XXXX is professionally sound and ready for phase-in via Step 10 cascade

⚪ **REVISE** → ADR-XXXX requires authoring revision; return to Step 5-9 author team with feedback

**If REVISE, Provide Primary Blockers:**

1. [Blocker 1: specific contradiction, assumption failure, or scenario misalignment]
2. [Blocker 2]
3. [Blocker 3, if applicable]

**Revision Deadline:** [YYYY-MM-DD, typically 5-10 business days from review date]

---

## 10. Reviewer Sign-Off

By signing off below, the reviewer confirms:

- All sections of this template have been completed
- Evidence gathering (Section 2) has been completed; authoritative standards searched and documented
- Contradictions have been audited and dispositioned
- Scenarios have been validated against operational reality
- Assumptions are defensible with documented evidence and grounded in official best practices
- Deliberate deviations from standards have explicit rationale
- Gate outcome reflects professional-grade readiness for production platform governance

| Field | Signature/Value |
|-------|-----------------|
| **Reviewer Name** | [Full legal name] |
| **Reviewer Title** | [Job title / Role] |
| **Organization/Team** | [Team or org affiliation] |
| **Sign-Off Date** | [YYYY-MM-DD] |
| **Email** | [Contact for follow-up questions] |

---

## 11. Review Artifacts Reference

**This Review Record Should Be Attached To:**

- PR or issue that delivers the revised ADR (if revisions were required)
- Internal decision tracker or ADR review calendar
- Audit trail for governance compliance verification

**This Review Template Was Completed Per:**

- ADR-0044 (Governance and Operating Model) § Step 9.5
- Revalidation Cycle: [One-time gate review] → [Then annual review_state cycle]

---

## Appendix: Review Guidance

### When to Use PASS

- Evidence gathering (Section 2) complete; ADR grounded in authoritative sources
- All deviations from standards have explicit rationale and accepted risk
- All assumptions hold under scrutiny
- No High-severity contradictions remain
- All failure modes have documented mitigations or are explicitly accepted
- Scenario validation matrix shows no 🔴 "Misaligned" outcomes
- Blocking follow-up actions are zero
- Tradeoffs are explicitly documented and defensible

### When to Use REVISE

- Evidence gathering incomplete or standards references missing
- Deviations from authoritative sources lack rationale
- One or more assumptions fail or require rethinking
- High-severity contradictions detected and unresolved
- Failure modes exist without documented mitigation or acceptance
- Scenario validation shows 🔴 "Misaligned" outcomes
- Blocking follow-up actions exist
- Tradeoffs lack clarity or were not fully considered

### Reviewer Role & Expectations

- **Evidence Authority:** Begin with official documentation search (Section 2); treat PEPs, FastAPI docs, Pluggy docs, Twelve-Factor, provider APIs as authoritative sources
- **Independence:** Reviewers should not be the ADR author
- **Adversarial Posture:** Challenge assumptions; don't validate pro-forma; verify claims against official sources
- **Operational Grounding:** Reference real incident, sync, and request workflows
- **Multi-Provider Perspective:** Consider Slack, Teams, AWS, GWS, GitHub interactions; check provider-specific documentation
- **Standards Vigilance:** Flag any deviation from authoritative sources and require explicit acceptance rationale
- **Time Commitment:** Expect 3-5 hours per ADR review (includes evidence gathering in Section 2)

---

**Template Version:** 1.0  
**Last Updated:** 2026-04-28  
**Review Gate:** Step 9.5 (Canonical ADR Challenge and Content Review Gate)
