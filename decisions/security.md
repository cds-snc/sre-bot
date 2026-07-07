---
status: Accepted
date: 2026-07-06
applies: target
scope: API authentication, authorization, CORS, rate limiting, headers, and webhook authenticity.
---

# API Security

## Context

The 2026-07 review found production CORS resolving to wildcard-with-credentials, an in-memory rate limiter bypassable via a client-set header, JWT validation skipping audience/issuer checks, and bearer-URL-only webhooks. This record states the binding rules; the hotfix ticket closes the gaps. Slack inbound verification is owned by [transport-slack.md](transport-slack.md).

## Decision

**Authentication (HTTP):** JWT bearer tokens validated against configured issuers via JWKS. Non-negotiable per token: signature (algorithms pinned to the asymmetric set configured per issuer — never `HS*`, never token-driven), `exp` (required present and valid), `nbf` (validated whenever present — it is optional in RFC 7519 and many issuers omit it), `iss` (passed to `decode`, matched against the issuer whose keys verified the token), and `aud` (required in every issuer config; a config without an audience fails boot). JWKS refreshes at runtime with fail-degraded semantics (missing issuer → its tokens 401, app still serves).

**Identity:** one frozen `User` value type per request. `user_id` is the **JWT `sub`** (stable, non-reassignable); email is a display/correlation attribute, not the key. `User.permissions` derives from the same claim authorization enforces (`scope`/`scp`, normalized) — one source of truth. Route authorization uses FastAPI `SecurityScopes`; routes are authenticated by default, and an unauthenticated route is an explicit, commented decision. Object-level authorization (who may act on *this* resource) is the service layer's job and every feature PR states its answer.

**Dev bypass:** requires `ENVIRONMENT != "production"` **and** `DEV_BYPASS_ENABLED=true` (default false) — two independent guards ([configuration.md](configuration.md)); every use is logged.

**CORS:** explicit origin allow-list from settings. A validator rejects `*` combined with credentials at boot, in every environment. No environment-derived origin logic.

**Rate limiting:** SlowAPI with a shared storage backend (`redis://`) whenever more than one replica can run; `memory://` only for local. Keyed per-principal when authenticated, per-IP otherwise. **No header-based exemptions** — trusted internal sources authenticate like everyone else. 429s are problem-details with `Retry-After` ([errors-and-http.md](errors-and-http.md)). Default limits apply to all routes; exemptions (health) are explicit.

**Headers:** one middleware sets, on every response: `Strict-Transport-Security` (max-age ≥ 1 year, `includeSubDomains`), `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` (the anti-embedding control — ASVS 5.0 treats `X-Frame-Options` as obsolete; include it only as a legacy extra), `Referrer-Policy`, and a restrictive `Permissions-Policy`.

**Webhooks:** every inbound webhook authenticates by signature — provider-verified where the provider signs (SNS: verified in **all** environments), HMAC with a per-webhook secret for generic webhooks (URL knowledge alone is never sufficient). Bodies have a size cap. Payloads are data, never trusted identity: actor attribution happens only after signature verification.

**Request limits:** body size capped at the server; no unbounded `Body(...)` on public routes.

## Consequences

- The trust model is uniform: verify at the boundary (transport or route), then code downstream assumes an authenticated principal.
- Redis becomes a deployment dependency for multi-replica environments — accepted; a broken limiter is worse.

## Checks

- Tests: JWT missing-`aud` config fails boot; tampered/HS256 tokens rejected; CORS validator rejects wildcard+credentials; unauthenticated request to a feature route → 401; unsigned webhook → 403; 429 carries `Retry-After`.
- grep: no `X-Sentinel-Source` (or any header-presence) limiter exemption; `allow_origins` never computed from environment shape.

## Migration

Ticket: Phase-0 security hotfixes — known gaps at adoption time: prod CORS wildcard+credentials, header-based limiter exemption, in-memory limiter across replicas, JWT `aud`/`iss` not enforced, unsigned generic webhooks, SNS verification skipped outside prod. Nothing here is a tolerated divergence for new code.
