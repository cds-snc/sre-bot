# ADR Challenge and Content Review — ADR-0064

---

## 1. Review Metadata

| Field | Value |
|-------|-------|
| **ADR Under Review** | ADR-0064: Security and Rate-Limiting API Protection |
| **Reviewer Name & Title** | AI Architectural Reviewer, SRE Team |
| **Secondary Reviewers** | — |
| **Review Date** | 2026-04-30 |
| **Revalidation Due** | 2027-04-30 |
| **Gate Outcome** | ⚪ **PASS** |
| **Outcome Rationale** | ADR-0064 consolidates two stale Tier-4 legacy records into a well-structured Tier-2 standard. All 10 standards align with authoritative best practices (OWASP, FastAPI, PyJWT, SlowAPI, RFC 9457). The single deliberate deviation (degraded-start for missing ISSUER_CONFIG vs. fail-fast per ADR-0045 P4) is explicitly documented with accepted risk and sound rationale. No blocking contradictions found. |

---

## 2. Evidence Gathering & Convention Validation

### 2.A Language & Framework Standards

**Applicable Standards:**

- ✅ FastAPI Official Documentation — Security, Dependencies, Middleware
- ✅ PyJWT Documentation — JWT validation, JWKS, registered claims
- ✅ Pydantic V2 Documentation — BaseModel for I/O boundaries
- ✅ Python Typing Module — Protocol for service contracts
- ✅ Structlog Documentation — structured logging
- ✅ SlowAPI Documentation — rate limiting for FastAPI/Starlette

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| FastAPI Security Docs | "FastAPI security tutorial Security() dependency" | FastAPI provides `Security()` as extension of `Depends()` for OAuth2 scopes. Authentication should use dependency injection, not middleware. `SecurityScopes` auto-populated from route declarations. | ✅ Aligned | — |
| FastAPI Middleware Docs | "FastAPI middleware ordering CORS" | CORSMiddleware must be outermost. Auth should be Depends, not middleware, for per-route granularity. | ✅ Aligned | — |
| PyJWT Usage | "PyJWT validate JWT JWKS RSA" | PyJWKClient provides automatic JWKS key resolution with caching. Claims `iss`, `aud`, `exp` should be verified. `algorithms` parameter must be explicit (never allow `alg: none`). Sync operations (no async). | ✅ Aligned | — |
| PyJWT Registered Claims | "PyJWT registered claim names exp aud iss" | `exp`, `aud`, `iss` verification built into `jwt.decode()`. ADR requires all three — aligns with PyJWT best practice and OWASP JWT guidance. | ✅ Aligned | — |
| SlowAPI Docs | "SlowAPI FastAPI rate limiting decorator" | Route decorator must be above limit decorator. `Request` parameter required. `Limiter` stored on `app.state`. Custom key functions return `None` to bypass. | ✅ Aligned | — |
| PEP 544 (Protocol) | "Python Protocol structural subtyping" | Protocol classes define structural interfaces for static type checking. Appropriate for service contracts where implementations may vary (test doubles, alternative providers). | ✅ Aligned | — |

---

### 2.B Infrastructure & Operational Standards

**Applicable Standards:**

- ✅ OWASP REST Security Cheat Sheet
- ✅ RFC 9457 (Problem Details for HTTP APIs)
- ✅ RFC 7519 (JSON Web Token)
- ✅ RFC 6749 (OAuth 2.0 scope claims)
- ✅ Twelve-Factor App Methodology (Config, Backing Services)

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| OWASP REST Security | "OWASP REST Security Cheat Sheet JWT CORS rate limiting headers" | JWT: verify `iss`, `aud`, `exp`; never allow `alg:none`. CORS: be specific with origins; disable if not needed. Error handling: generic messages; no stack traces. Security headers: `X-Content-Type-Options: nosniff`, `Strict-Transport-Security`, `Cache-Control: no-store`, `Content-Security-Policy: frame-ancestors 'none'`. HTTP 401/403/429 status codes for auth/authz/rate-limit failures. | ✅ Aligned | — |
| OWASP Audit Logs | "OWASP REST Security audit logs" | Log security events (auth failures, rate limits). Sanitize log data. Do not log credentials. | ✅ Aligned | — |
| RFC 9457 | "RFC 9457 Problem Details HTTP APIs" | Structured error response with `type`, `status`, `title`, `detail`. Extension members permitted (§3.2). ADR uses `application/json` initially, not `application/problem+json`. | ✅ Aligned | Deferred content-type switch documented; RFC 9457 §4.1 permits JSON without problem+json media type |
| RFC 7519 | "RFC 7519 JWT iss aud exp claims" | Standard claims: `iss`, `sub`, `aud`, `exp`, `nbf`, `iat`, `jti`. ADR validates `iss`, `aud`, `exp` — covers the security-critical claims. | ✅ Aligned | — |
| Twelve-Factor Config | "Twelve-Factor App configuration environment" | Config in environment variables. Strict separation of config from code. | ✅ Aligned | ISSUER_CONFIG as env var JSON follows 12-factor |

---

### 2.C Cross-Cutting Design Patterns

**Applicable Standards:**

- ✅ Dependency Injection Best Practices
- ✅ Defense-in-Depth (layered security)
- ✅ Observability & Logging Patterns

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| Defense-in-Depth | "Layered security defense in depth rate limiting" | Multiple independent layers reduce blast radius of single-layer failure. WAF (network) + ALB (connection) + application (business-context) is canonical three-layer pattern. | ✅ Aligned | — |
| DI Best Practices | "Dependency injection FastAPI Security() testability" | Dependencies should be overridable for testing. Provider functions centralize construction. Narrow interfaces (Protocol) enable test doubles. | ✅ Aligned | — |

---

### 2.D Validation Summary

**Total Standards Checked:** 12
**Aligned with Best Practice:** 12
**Deliberate Deviations:** 0 (at standards level; 1 internal deviation from ADR-0045 P4 documented)

**High-Level Finding:**

- 🟢 **Fully Grounded:** All standards checked; no unresolved deviations. The ADR-0045 P4 deviation (degraded-start) is an internal architectural tradeoff, not a deviation from external best practices.

---

## 3. Assumptions Challenged

### Assumption 3.1: Authentication as Dependency (not Middleware)

- **Stated Norm:** "All protected HTTP API endpoints must authenticate requests using a FastAPI Security() dependency... Authentication is not implemented as middleware" (Standard 1)
- **Underlying Assumption:** FastAPI's dependency injection system provides sufficient control for per-route authentication with scope granularity.
- **Challenge:** Could middleware-based auth be simpler for APIs where all routes require the same authentication? Middleware auth is common in other frameworks.
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — FastAPI's official documentation explicitly recommends `Security()` dependency for OAuth2 scope-based auth. Middleware cannot leverage `SecurityScopes` for per-route scope enforcement. The codebase has both authenticated and unauthenticated routes (webhooks, health), making blanket middleware auth incorrect.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** FastAPI's `Security()` is the canonical pattern. The ADR correctly identifies that middleware cannot handle per-route scope differentiation, and the codebase has mixed auth requirements.

### Assumption 3.2: JWKSManager Needs a Protocol Contract

- **Stated Norm:** "JWKSManager must implement a Protocol contract... classified as Category A (contract-required)" (Standard 2)
- **Underlying Assumption:** `JWKSManager` has a backing service (JWKS endpoints) that varies between production and test environments, warranting a Protocol for testability.
- **Challenge:** The concrete `JWKSManager` could be tested directly with mock JWKS endpoints (httpx mock, responses library). A Protocol adds abstraction overhead for a class that has exactly one implementation.
- **Evidence Strength:** ⭐⭐ Moderate
- **Counter-Evidence Found:** Partial — testing without a Protocol is possible but requires HTTP-level mocking of JWKS endpoints. A Protocol enables simple in-memory test doubles that return pre-configured keys, which is simpler and faster.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** ADR-0077 Standard 1 classifies Category A services (backing service interaction) as requiring Protocols. `JWKSManager` interacts with external JWKS URIs, making it Category A by definition. The Protocol also enables testing without network access, which is valuable for CI/CD. The constraint is consistent with the broader architectural framework.

### Assumption 3.3: Degraded-Start for Missing ISSUER_CONFIG

- **Stated Norm:** "If ISSUER_CONFIG is empty or missing at startup, the application must log a warning... The application may start in degraded mode" (Standard 5, S5-R5)
- **Underlying Assumption:** The application serves unauthenticated endpoints (health, webhooks) that must remain available even without JWT configuration. Failing startup would block the entire application for a configuration subset.
- **Challenge:** This deviates from ADR-0045 P4 (fail-fast). A misconfigured production deployment could silently accept requests and return 500 on any authenticated endpoint, creating user confusion and potential security risk.
- **Evidence Strength:** ⭐⭐ Moderate
- **Counter-Evidence Found:** Partial — fail-fast would be safer in a pure-API context. However, the application is multi-transport (HTTP + Slack + Teams) and multi-purpose (webhooks, health, authenticated API). Blocking the entire application for missing JWT config would prevent health checks and webhook processing.
- **Confidence (ADR survives challenge):** 🟡 Moderate
- **Reviewer Notes:** The deviation is explicitly documented with rationale and accepted risk. The ADR requires `event="security_services_degraded"` logging, ensuring operational visibility. This is a pragmatic tradeoff, not an oversight. The moderate confidence reflects the inherent tension between fail-fast and operational resilience for multi-purpose applications. The documented acceptance is sufficient.

### Assumption 3.4: IP-Based Rate Limiting as Default

- **Stated Norm:** "The default key function is IP-based (get_remote_address)" (Standard 3, S3-R4)
- **Underlying Assumption:** IP addresses provide a meaningful client identifier for rate limiting at the application layer.
- **Challenge:** Behind NAT gateways, VPNs, or shared corporate proxies, many users share the same IP. Rate limiting by IP could block legitimate users. Conversely, attackers can distribute requests across many IPs.
- **Evidence Strength:** ⭐⭐ Moderate
- **Counter-Evidence Found:** Yes — IP-based rate limiting has known limitations (NAT, VPN, distributed attacks). However, the ADR positions application-layer rate limiting as a complement to WAF/ALB (which also use IP), not a replacement. The ADR allows custom key functions for user-scoped limits where business context matters.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** The ADR correctly positions IP-based limiting as the default with extensibility for user-scoped limits. The layered architecture (WAF + ALB + app) means IP-based limits at the app layer are a last-resort circuit breaker, not the primary defense. This is consistent with OWASP defense-in-depth guidance.

### Assumption 3.5: CORS Wildcard is a Specification Violation

- **Stated Norm:** "Production CORS must not use wildcard (*) origins... browsers reject Access-Control-Allow-Credentials: true when Access-Control-Allow-Origin:*" (Standard 7)
- **Underlying Assumption:** The current production CORS configuration (`allow_origins=["*"]` with `allow_credentials=True`) is incorrect per the CORS specification.
- **Challenge:** Is this actually causing issues? Maybe the API doesn't need credentials in cross-origin requests.
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — the Fetch specification (and all major browsers) explicitly reject `Access-Control-Allow-Credentials: true` when `Access-Control-Allow-Origin: *`. If the API uses credentials (cookies, authorization headers) in cross-origin requests, the current config is non-functional. If it doesn't use credentials, `allow_credentials=True` is misleading. Either way, the configuration should be corrected.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** This is a factual standards compliance issue, not a judgment call. The ADR correctly identifies it and prescribes explicit origin enumeration.

---

## 4. Failure Modes Identified

### Failure Mode 4.1: Degraded-Start Leads to Silent Auth Failures in Production

- **If Assumption Fails:** ISSUER_CONFIG is accidentally unset in production. Application starts without JWT capability. All authenticated API endpoints return 500 or generic errors. Operations team may not notice if health checks pass.
- **Platform Impact:**
  - Incident management workflow: **Medium** — authenticated API actions fail
  - Access synchronization workflow: **Medium** — API-triggered syncs fail
  - Access request workflow: **Medium** — API-triggered requests fail
  - Multi-provider integrations (Slack, Teams, GWS, AWS, GitHub): **Low** — platform transports don't use JWT
- **Probability Estimate:** Low — deployment pipelines typically validate required config
- **Mitigation or Acceptance:** Accepted with mitigation: `event="security_services_degraded"` log entry enables alerting. Deployment validation in CI/CD should check for required config. The ADR explicitly documents this as a deliberate deviation from fail-fast.

---

## 5. Contradiction Audit

### Cross-ADR Contradictions

| Conflict | ADRs Involved | Severity | Resolution Status |
|----------|---------------|----------|-------------------|
| Degraded-start vs. fail-fast principle | ADR-0064 S5-R5, ADR-0045 P4 | 🟡 Medium | ✅ Resolved → ADR-0064 S5-R5 documents deliberate deviation with rationale and accepted risk |
| Auth error responses: ADR-0064 prescribes RFC 9457 for 401/403; ADR-0060 governs error schema | ADR-0064 S1-R4, ADR-0060 S1 | 🟢 Low | ✅ Resolved → ADR-0064 references ADR-0060 S1 as the canonical error schema; no duplication, only cross-reference |
| `JWKSManager` identity: ADR-0061 delegates JWT validation upstream, ADR-0064 owns it | ADR-0064 S2, ADR-0061 S3 | 🟢 Low | ✅ Resolved → ADR-0061 governs identity resolution (IdentityService); ADR-0064 governs JWT validation upstream. Boundary is clear: JWT → validated payload → IdentityService → User |

### Supersession Ambiguities

- **ADRs this one supersedes:** ADR-0037, ADR-0038
- **Inheritance Status:** All inherited constraints and impacts are acknowledged. ADR-0037's JWT validation patterns are codified in Standards 1, 2, and 9. ADR-0038's rate-limiting architecture is codified in Standards 3 and 4. No inherited content is missing.
- **Gaps Identified:** None

### Ownership Clarity

- **Primary Domain Owner:** SRE Team
- **Secondary Domain Owners:** None
- **Plugin/Startup Registration:** Security services initialize during lifespan (Standard 5) — not plugin-registered
- **Config Owner:** `infrastructure/security/` for service code; security settings in dissolution target `SecuritySettings` (Standard 6)
- **Audit Result:** ✅ Clear

---

## 6. Scenario Validation Matrix

### Scenario 6.1: Incident Management Workflow

**Context:** Emergency response requires rapid logging, context propagation, and operational decision-making under time pressure.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Auth for incident API actions | S1: JWT Bearer required for protected endpoints | Incident management uses authenticated API endpoints | ✅ No | Standard pattern applies |
| Rate limiting during incidents | S3: Application-layer rate limiting per route | Incident actions should not be rate-limited below operational needs | ✅ No | Route-specific limits can be set appropriately; sentinel bypass available |
| Error responses during auth failures | S1-R4: Structured RFC 9457 responses | Operators need clear error information | ✅ No | Structured error codes enable programmatic incident handling |

**Validation Summary:** ✅ Fully aligned

---

### Scenario 6.2: Access Synchronization Workflow

**Context:** Automated sync from identity providers (AWS IAM, Google Workspace, GitHub) to application; must handle failure, retry, and eventual consistency.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Auth for sync API triggers | S1: JWT Bearer with scopes | Sync API requires `sre-bot:access-sync` scope | ✅ No | Scope enforcement via SecurityScopes |
| Rate limiting sync endpoints | S3: Business-context aware limits | Sync runs are infrequent but must not be blocked | ✅ No | Route-specific limits can accommodate sync patterns |
| JWKS endpoint availability | S2: JWKS caching with warmup | JWKS endpoints may be temporarily unavailable | ✅ No | PyJWKClient caching (1hr TTL) provides resilience; keys cached from warmup |

**Validation Summary:** ✅ Fully aligned

---

### Scenario 6.3: Access Request Workflow

**Context:** User requests access to a resource/role; admin approves; system provisions and audits the action across multiple platforms.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Auth for request/approve actions | S1: JWT Bearer with scopes | Different scopes for requesters vs. approvers | ✅ No | Per-route scope declarations handle this |
| Webhook callbacks | S10: Webhook auth exemption | Webhook endpoints are unauthenticated | ✅ No | Platform-specific auth (Slack signing) handled by ADR-0061/0078 |
| Error responses for denied access | S1 error table: 403 for insufficient scopes | User must understand why access was denied | ✅ No | Structured error with `INSUFFICIENT_SCOPE` code |

**Validation Summary:** ✅ Fully aligned

---

### Scenario 6.4: Multi-Provider Integrations (Slack, Teams, GWS, AWS, GitHub)

**Context:** Platform integrations use different authentication mechanisms per provider.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Slack request signing | S10-R2: Platform transport auth delegated to ADR-0061/0078 | Slack uses request signing, not JWT | ✅ No | Correctly scoped out of this ADR |
| Teams bot validation | S10-R2: Platform transport auth delegated | Teams uses Bot Framework auth | ✅ No | Correctly scoped out |
| API calls from platform handlers | S1: Protected endpoints require JWT | Internal service calls triggered by platform handlers may not have JWT context | ✅ No | Platform handlers route through service layer, not through authenticated API endpoints |

**Validation Summary:** ✅ Fully aligned

---

## 7. Gate Decision

### Summary of Findings

| Category | Count | Severity |
|----------|-------|----------|
| Standards fully aligned | 12/12 | — |
| Assumptions challenged | 5 | 4 High confidence, 1 Moderate confidence |
| Failure modes identified | 1 | Medium impact, Low probability, mitigated |
| Cross-ADR contradictions | 1 (resolved) | Medium severity, explicitly documented |
| Scenario validations | 4/4 pass | — |

### Gate Outcome: **PASS**

**Rationale:** ADR-0064 is a well-structured Tier-2 standard that:

1. Correctly consolidates two stale Tier-4 records (ADR-0037, ADR-0038) into a single authority
2. Aligns with OWASP, FastAPI, PyJWT, and RFC 9457 best practices (12/12 standards checked)
3. Maintains clear boundaries with adjacent ADRs (ADR-0060 for error schema, ADR-0061 for identity, ADR-0063 for API composition)
4. Explicitly documents its one deliberate deviation (degraded-start) with rationale and accepted risk
5. Passes all four scenario validations without gaps

No blocking issues found. Recommended for user acceptance decision.
