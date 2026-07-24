---
id: TASK-3
title: Remove the X-Sentinel-Source rate-limiter bypass
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-07 19:56'
updated_date: '2026-07-24 16:11'
labels:
  - security
  - phase-0
milestone: m-0
dependencies: []
references:
  - decisions/security.md
  - 'https://github.com/cds-snc/sre-bot/issues/1257'
priority: high
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/security.md (Rate limiting): "No header-based exemptions - trusted internal sources authenticate like everyone else."

Today _sentinel_key_func at app/infrastructure/security/rate_limiter.py:19-23 returns None (= exempt from all limits) on bare presence of an X-Sentinel-Source header, and get_limiter() (lines 32-35) builds the Limiter with that key_func (SEC-2, OWASP API4:2023). Anyone can set that header.

The header was originally meant to exempt Microsoft Sentinel's alerting Playbook (Azure Logic App), which posts to our generic alerting endpoint (POST /hook/{webhook_id} in app/api/v1/routes/webhooks.py). That endpoint currently authenticates only by URL/webhook_id knowledge (bearer-URL-only, tracked separately). Per decisions/security.md's amended Webhooks clause, the durable elevated-limit mechanism for this sender is a per-webhook_id keyed rate limit backed by HMAC-verified webhook identity (TASK-47/48/49) - not JWT/Entra ID, which doesn't fit this ingress path. See comment below for the full research trail.

Steps:
1. Delete the header-presence exemption from _sentinel_key_func in app/infrastructure/security/rate_limiter.py.
2. If the internal source that motivated the exemption still needs elevated limits, it gets one through TASK-49 (per-webhook_id rate-limit override, gated on the HMAC identity work in TASK-47/48) - do NOT re-add any header check.
3. Keep scope minimal: shared Redis storage, Retry-After, and route coverage are TASK-31 (Phase 4); per-webhook_id keyed limits and elevated overrides are TASK-49 (Phase 4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 grep -rn "X-Sentinel-Source" app/ returns zero hits
- [x] #2 A request carrying arbitrary X-* headers is rate limited exactly like one without them (test exists)
- [x] #3 Sentinel's real-world peak alert burst rate is confirmed sufficient for the current uniform 30/minute limit on POST /hook/{webhook_id}, or that limit is raised to a confirmed-safe value in this same PR - applied uniformly to every caller of the route, never a Sentinel-specific carve-out (documented in the PR description)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Tests pass
- [ ] #2 PR references SEC-2 and decisions/security.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Codebase findings (grep -rn "X-Sentinel-Source" app/, 2 files, 7 hits):
- app/infrastructure/security/rate_limiter.py:19-21 (_sentinel_key_func def + docstring + header check)
- app/infrastructure/security/rate_limiter.py:35 (Limiter(key_func=_sentinel_key_func))
- app/tests/api/dependencies/test_rate_limits.py: test_header_exists_and_not_empty, test_header_not_present, test_header_empty (lines ~13-53) directly assert the bypass exists.
No other file in the repo imports or calls _sentinel_key_func (app/infrastructure/security/__init__.py only re-exports get_limiter/setup_rate_limiter). ADR-REVIEW-AND-MIGRATION-PLAN.md and backlog/docs/doc-1 mention the old bypass as historical analysis - out of scope (AC#1 greps app/ only).

Step 1 (app/infrastructure/security/rate_limiter.py):
- Delete the _sentinel_key_func function entirely (it only wraps get_remote_address with the header exemption).
- Change get_limiter() to build Limiter(key_func=get_remote_address) directly (get_remote_address already imported from slowapi.util).
- Result: zero remaining references to X-Sentinel-Source or a header-presence exemption in this file.

Step 2 (app/tests/api/dependencies/test_rate_limits.py):
- Remove test_header_exists_and_not_empty, test_header_not_present, test_header_empty (they assert _sentinel_key_func, which no longer exists).
- Drop the now-unused `patch` import (keep `Mock`, still used by test_rate_limit_handler).
- Add `rate_limits.get_limiter.cache_clear()` at the start of test_system_endpoint_rate_limiting (before it builds the app) so the two integration tests below don't share slowapi's in-memory counters across test order (verified: each Limiter() gets its own fresh limits.storage.memory.MemoryStorage instance, so cache_clear + rebuild == isolated window).
- Add new test test_rate_limited_regardless_of_arbitrary_headers: clears the limiter cache, builds a fresh app via setup_rate_limiter + system_router, sends 50 GET /version requests carrying {"X-Sentinel-Source": "trusted", "X-Another-Header": "value"} expecting 200 each, then a 51st expecting 429 with {"message": "Rate limit exceeded"} - proving arbitrary/spoofed headers no longer grant exemption (AC#2).

Step 3 (app/api/v1/routes/webhooks.py) - prep step, satisfies AC#3:
- Before merging, confirm with whoever owns the Sentinel workspace what real-world peak burst rate the Playbook produces. Removing the header bypass drops Sentinel straight onto the shared per-IP 30/minute ceiling; if Sentinel currently relies on the bypass for effectively unlimited throughput, this could functionally rate-limit real alerts before the durable per-webhook_id mechanism (TASK-49) exists.
- If 30/minute already covers the confirmed peak, no code change needed here.
- If it does not, raise the "30/minute" value on the existing `@limiter.limit(...)` decorator for `POST /hook/{webhook_id}` to a value that comfortably covers it. This is a **uniform** change - it applies to every caller of this shared route, not a Sentinel-specific carve-out - so it stays fully compliant with "No header-based exemptions."
- Document the confirmed peak value (or the "already covered" finding) in the PR description.
- The durable, differentiated (per-webhook_id) elevated limit is out of scope here and lands via TASK-49 (blocked on TASK-47/48) - do not attempt per-principal or per-webhook differentiation in this task.

AC-to-step-to-test traceability:
- AC#1 (grep -rn "X-Sentinel-Source" app/ -> zero hits): satisfied by Step 1 + Step 2.
- AC#2 (arbitrary X-* headers rate limited like no headers): satisfied by the new test_rate_limited_regardless_of_arbitrary_headers in Step 2, plus the untouched test_system_endpoint_rate_limiting.
- AC#3 (Sentinel peak burst confirmed sufficient, or limit raised uniformly): satisfied by Step 3 - a human confirmation recorded in the PR description, plus the numeric edit if the confirmed peak requires one.

Test matrix:
- Unit: none needed for the key func anymore (get_remote_address is slowapi library code, not app logic worth re-testing).
- Integration (existing, now isolated): test_system_endpoint_rate_limiting - no headers, 50 ok then 429.
- Integration (new): test_rate_limited_regardless_of_arbitrary_headers - arbitrary/spoofed X-* headers (including the old bypass header name), 50 ok then 429, identical shape to the no-header case.
- Unchanged: test_rate_limit_handler (429 JSON handler) unaffected by this change.
- Step 3 has no new automated test (numeric-value/human-confirmation prep step); verified by PR-description review.

Validation commands (from app/):
- grep -rn "X-Sentinel-Source" app/  (expect zero hits)
- uv run pytest tests/api/dependencies/test_rate_limits.py -q
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'
- uv run ruff check .

Verified fact: slowapi's Limiter() creates independent in-memory storage per instance (not a shared global) - confirmed via a throwaway `uv run python3` check: two Limiter() instances have distinct `_storage` objects of type limits.storage.memory.MemoryStorage. cache_clear() + re-invoking get_limiter() is therefore sufficient to reset rate-limit counters between tests.

Blast radius: primarily app/infrastructure/security/rate_limiter.py plus its dedicated test file (no settings, no DI wiring, no schema/API surface changes). Also touches app/api/v1/routes/webhooks.py IF Step 3's confirmed peak requires raising the numeric limit (a one-line edit to the existing `@limiter.limit("30/minute")` decorator) - otherwise that file is untouched.

Rollback: revert the single commit/PR; no data migration, no schema change, no feature flag involved - safe to revert directly if a real internal caller unexpectedly regresses (mitigation: that caller must be migrated to a signed tier and get a per-webhook limit via TASK-49, not by re-adding a header check).

Size verdict: fits comfortably in one PR (2-3 files touched, ~15 lines removed/changed in production code plus at most a one-line numeric edit, ~40 lines net in tests including one new test) - no decomposition needed.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented app-only webhook limit increase based on observed CloudWatch burst data.

Changes applied:
- app/api/v1/routes/webhooks.py
  - Updated webhook route limiter from 30/minute to 300/minute.
- app/tests/api/v1/test_webhooks.py
  - Updated rate limit test expectation to allow 300 requests and rate-limit the 301st.

Validation:
- cd /workspace/app && uv run pytest tests/api/v1/test_webhooks.py -k rate_limiting -q
  - 1 passed.
- cd /workspace/app && uv run ruff check .
  - All checks passed.
- cd /workspace/app && uv run pytest tests --ignore=tests/smoke -q
  - 2870 passed, 37 skipped.
- cd /workspace/app && uv run mypy . --exclude '(?:^|/)\\.venv(?:/|$)'
  - Fails due to pre-existing baseline typing issues outside this task's changed files.

Operational input used for AC#3:
- CloudWatch Logs Insights for webhook path over last 21 days showed daily peak one-minute bursts up to 233 rpm.
- Uniform webhook route limit raised to 300/minute to avoid blocking observed Sentinel bursts.

Scope decision:
- WAF was intentionally left unchanged in this task per explicit user direction.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-24 15:20
---
Research summary: how Sentinel's alerts reach this bot, and the durable elevated-limit mechanism (out of scope for this task's implementation - informs the follow-up chain below).

Delivery path (confirmed against Microsoft Sentinel/Logic Apps docs): Sentinel doesn't call us directly. A Sentinel Automation Rule fires on incident/alert creation and runs a Playbook (Azure Logic App); the Playbook's HTTP action posts to our generic alerting endpoint (POST /hook/{webhook_id}, rate-limited "30/minute ... since some slack channels use this for alerting"). That endpoint authenticates only by URL/webhook_id knowledge today (bearer-URL-only, a separate known gap) and had the X-Sentinel-Source bypass this task removes.

Durable elevated-limit mechanism: per decisions/security.md's Webhooks clause (amended 2026-07-24, tiered trust model), the correct fix keys rate limits per `webhook_id` and grants elevated limits only to HMAC-authenticated webhooks - not JWT/Entra ID Managed Identity (that path was investigated and set aside: it fits authenticated API routes generally, not this webhook ingress, which has its own clause and its own already-planned task chain). Sequencing: TASK-7 (SNS/hardening, Phase 0) -> TASK-46 (origin-fingerprint observability, Phase 0/1) -> TASK-24 (SecuritySettings slice, parallel-safe) -> TASK-47 (HMAC verification + secure-by-default secret issuance, gives a webhook_id a verifiable identity) -> TASK-48 (migrates Sentinel's existing webhook_id off the legacy unsigned tier) -> TASK-49 (webhook_id-keyed limiter + per-webhook elevated override, closes the loop). This task must not wait for that chain - AC#3 and Implementation Plan Step 3 are the interim safeguard so removing the bypass now doesn't silently drop real alerts while TASK-47/48/49 are still Phase 4/To Do.

Not verified: which Logic App / resource group hosts the actual Sentinel Playbook in our tenant, and whether it currently uses the webhook_id URL directly or via another intermediary - needs confirmation from whoever owns the Sentinel workspace before TASK-48 scopes Sentinel's specific migration.
---

created: 2026-07-24 15:30
---
AC#3 pending human verification: confirm Sentinel playbook peak burst against uniform webhook limit (currently 30/minute) and decide if a uniform increase is needed in this PR.
---
<!-- COMMENTS:END -->
