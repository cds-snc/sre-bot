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

**Webhooks (amended 2026-07-24):** the SRE Bot is the organization's single webhook ingress — teams do not stand up their own apps — so inbound authenticity follows a **tiered trust model** rather than one blanket rule. *Provider-signed* (e.g. AWS SNS): the provider signature is verified in **all** environments, never environment-gated. *Shared-secret HMAC* (issuer-provisioned): the target state for every Bot-issued webhook — a per-webhook secret, HMAC over the body, constant-time compared. *Hardened secret-URL* (legacy / arbitrary sender): a high-entropy `webhook_id` path with the body treated as fully untrusted — a **time-boxed, tracked exception**, never a resting state, retained only until observability migrates each live sender to a signed tier. Because the Bot is the sole issuer, new webhooks are **secure-by-default**: a secret is minted at creation and HMAC is enforced from day one. The legacy unsigned population is retired observability-first — every request is fingerprinted (source IP, user-agent, matched payload type, signature-header presence) to build the known-sender inventory, then moved to a signed tier under monitor-then-enforce rollout. Unauthenticated acceptance of a not-yet-migrated legacy webhook is **risk-accepted in writing** (m-0 exit), never silent. Across all tiers, controls bind regardless of auth state: bodies have a size cap; every webhook ID is independently revocable; rate limits are keyed per `webhook_id`; and **payloads are data, never trusted identity** — actor attribution and target selection (channel, action) come from the Bot's own webhook record, never the request body. CORS is a browser control and offers no protection for these server-to-server calls; webhook authenticity is governed solely by this clause.

**Request limits:** body size capped at the server; no unbounded `Body(...)` on public routes.

## Consequences

- The trust model is uniform: verify at the boundary (transport or route), then code downstream assumes an authenticated principal.
- Redis becomes a deployment dependency for multi-replica environments — accepted; a broken limiter is worse.

## Checks

- Tests: JWT missing-`aud` config fails boot; tampered/HS256 tokens rejected; CORS validator rejects wildcard+credentials; unauthenticated request to a feature route → 401; provider-signed webhook with an invalid signature → 403 in all environments; a Bot-issued HMAC webhook with a missing/invalid signature → 401/403; oversized webhook body rejected; a not-yet-migrated legacy webhook is accepted only while flagged legacy and each acceptance emits an origin-fingerprint event; 429 carries `Retry-After`.
- grep: no `X-Sentinel-Source` (or any header-presence) limiter exemption; `allow_origins` never computed from environment shape.

## Migration

Ticket: Phase-0 security hotfixes — known gaps at adoption time: prod CORS wildcard+credentials, header-based limiter exemption, in-memory limiter across replicas, JWT `aud`/`iss` not enforced, generic webhook authenticity, SNS verification skipped outside prod. Generic webhooks were originally slated for mandatory HMAC in Phase 0; per the amended Webhooks clause this is now an observability-first, tiered migration — SNS-everywhere verification, exception-leakage removal, and the body-size cap land in Phase 0, while HMAC enforcement and secure-by-default issuance move to Phase 4, with the legacy unsigned population risk-accepted in writing until each sender is migrated. Nothing here is a tolerated divergence for new code: every newly issued webhook is signed from day one.
