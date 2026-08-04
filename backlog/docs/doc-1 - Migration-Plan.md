---
id: doc-1
title: Migration Plan
type: specification
created_date: '2026-07-07 20:00'
---

# Migration Plan — verified against the codebase on 2026-07-07

This is the operational plan behind the backlog. Source analyses: `ADR-REVIEW-AND-MIGRATION-PLAN.md` (§10) and `claude-research-outcome.md`, reconciled against the `decisions/` corpus (the architectural source of truth) and re-verified claim-by-claim against the code on branch `docs/gaps_reconciliation`. Every finding below was confirmed at the cited location; three counts were corrected (the deprecated client tree is 72 files, not ~24; `modules/webhooks` is 57 files; `modules/incident` is 51 files) and one assumption removed (`.python-version` does not exist yet — TASK-13 creates it).

## Structure

- **One milestone per phase** (`m-0` … `m-6`), matching plan §10's waves.
- **One task per reviewable outcome.** Each task carries its acceptance criteria (what a reviewer checks), definition of done (what must be true to merge), dependencies, and a `--ref` to the decision record it implements. Several tasks are explicitly "PR series" — land them as multiple small PRs (per consumer, per vendor, per module) rather than one.
- `backlog sequence list` computes the parallelizable waves from the dependency graph; `backlog board` shows status.

## Phase 0 — Security hotfixes (m-0, TASK-1…9) — do first, days not weeks

Code-only fixes, no architecture. Verified defects:

| Task | Defect (verified location) |
| --- | --- |
| TASK-1 | `is_production = not bool(PREFIX)` — one overloaded bit drives the whole security posture (`app/infrastructure/configuration/app.py:17-20`) |
| TASK-2 | Wildcard CORS **with credentials** in production (`app/server/server.py:21-32`) |
| TASK-3 | Any request with an `X-Sentinel-Source` header bypasses all rate limits (`app/infrastructure/security/rate_limiter.py:19-23`) |
| TASK-4 | JWT: `aud` skipped when unconfigured, `issuer=` never passed, algorithms config-driven (`app/infrastructure/security/jwt.py:116-122`) |
| TASK-5 | Idempotency is a get-then-put TOCTOU race; truncated payload-hash keys (`app/infrastructure/idempotency/dynamodb.py:47,89-111`, `key_builder.py:49`) |
| TASK-6 | Scheduler double-fire prevented only by a PREFIX gate (`app/server/lifespan.py:105`) → Tier-2 TTL lease on TASK-5's primitive |
| TASK-7 | SNS signature validation skipped outside prod (`app/modules/webhooks/aws_sns.py:84-85`); 5xx leaks exception text (`:108,:120`); `/hook/{id}` is a bearer-capability URL |
| TASK-8 | Redaction exists but is not in the structlog chain (`formatters.py:64` vs `setup.py:168-204`) |
| TASK-9 | `SIGNING_SECRET` configured, never used for HTTP-mode verification |

Order inside the phase: TASK-1 first (TASK-2/6/7 read the typed `ENVIRONMENT`); TASK-5 before TASK-6. The rest are independent and can be reviewed in parallel.

**Exit:** all nine closed or explicitly risk-accepted in writing.

## Phase 1 — Decision corpus adoption (m-1, TASK-10…12) — writing, no code

`decisions/*.md` becomes the only source of truth; `docs/adr/` (47 files, still present) is banner-archived; the four root-level analysis documents move to history; the two open policy deltas (dependency-scanning gate ownership, hookspec deprecation lifecycle) get their own short records.

**Exit:** zero dangling references; no document claims a decision is missing that now exists.

## Phase 2 — Mechanical enforcement (m-2, TASK-13…21) — mostly config

Align tooling with `decisions/toolchain.md` before refactors, so later phases are held by CI instead of discipline: Python 3.14 everywhere (today: CI 3.11 / venv 3.12 / image 3.14, no `.python-version`); Dockerfile honors `uv.lock` (today it globs the lock and installs editable); ruff replaces black + standalone bandit; mypy blocking (kill the `|| true` at `app/Makefile:80`); pre-commit; import-linter with the four layer contracts and a ratcheting `ignore_imports` baseline; the two `app/bin/` guardrail scripts committed and enforced; test gates (`--strict-markers`, `fail_under` ratchet, single test tree); the EN/FR parity gate.

**Exit:** CI enforces the boundaries the decisions claim; baselines only ratchet down.

## Phase 3 — Client layer convergence (m-3, TASK-22…26) — mechanical, low risk

One client generation. Migrate the six verified consumers of the deprecated 72-file `infrastructure/clients/` tree, then delete it plus the empty `app/clients/`; resolve the six `_next.py` twins; one settings home per vendor plus a wired `SecuritySettings` slice; apply the clients-raise/adapters-classify contract (`classify_<vendor>_error`, retire `AWSShield` and the executor tier); consolidate Slack (transport → `infrastructure/slack/`, Web client + classifier stay in `integrations/slack/`, shims keep `modules/` working).

**Exit:** usage matrix reports zero deprecated consumers; no `_next` files; `integrations/` imports nothing above the shared kernel.

## Phase 4 — Infrastructure hardening (m-4, TASK-27…34) — parallel with Phase 3

Make the `applies: target` records true: capability-shaped `StorageService` (the current Protocol leaks DynamoDB `KeyConditionExpression` strings) + in-memory fakes per Path A Protocol; the middleware/edge trio (correlation `request_id`, security headers, RFC 9457) + logging pipeline; provider registry with eager phase-2 warmup; the owned ~50-line event dispatcher replacing blinker; distributed rate limiting; resolve the empty `persistence/`/`notifications/` packages; async Bolt after the Slack home move. TASK-34 (QueueService + outbox) is deliberately deferred until a real durable consumer exists — per `claude-research-outcome.md`, cross the cloud boundary only when a reaction must outlive a crash.

**Exit:** the security/ops decisions' Checks pass; records flip `applies: target` → `now`.

## Phase 5 — Legacy modules strangler (m-5, TASK-35…41) — quarters, background pace

Per `decisions/migration.md`. Fix the double-registration first (TASK-35, live bug risk), capture the external contract in smoke tests (TASK-36 — the oracle for every cutover), then migrate module by module: `webhooks` (57 files, security-sensitive), `incident` (51 files), the small wins (`role`, `secret`, `atip`), then the remainder (`aws`, `ops`, `permissions`, `provisioning`, `reports`, `slack`, residual `dev`/`sre`). Each module: smoke first → feature package → cutover → delete, no zombie halves. TASK-41 executes the "Done means" checklist (delete `modules/`, the legacy list, `python-i18n`; retire the guardrail scripts).

**Exit:** `app/modules/` gone; other teams verifiably unaffected (smoke suite green throughout).

## Phase 6 — Multi-transport (m-6, TASK-42…43) — blocked until Teams is funded

Do not start speculatively. Write `transport-teams` properly, implement, and only then promote the composition pattern with n=2 learnings.

## Review-batch guidance

Small-PR seams are built into the tasks: per-consumer (TASK-22), per-vendor (TASK-23, 25), per-module (TASK-37–40), reformat-only commits isolated (TASK-15). A task is the unit of *acceptance*, not necessarily one PR. Keep `main` releasable after every merge — that constraint is inherited from plan §10 and non-negotiable.
