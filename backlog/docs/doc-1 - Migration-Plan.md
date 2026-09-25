---
id: doc-1
title: Migration Plan
type: specification
created_date: '2026-07-07 20:00'
updated_date: '2026-09-24 20:12'
---
# Migration Plan

This is the operational plan behind the backlog. It was first verified against the codebase on 2026-07-07, and realigned on 2026-09-24 to decisions/plugin-architecture.md. That record replaced the three-tier model (packages -> infrastructure -> integrations) and deleted decisions/layers.md, capability-packages.md and events.md. The `decisions/` corpus remains the architectural source of truth; this document only sequences the work.

## Structure

- **One milestone per phase** (`m-0` … `m-7`). m-7 ("Phase 2b - Plugin Architecture Foundation") runs between Phase 2 and the legacy strangler: every package move and legacy rebuild depends on it.
- **One task per reviewable outcome**, with acceptance criteria, definition of done, dependencies (recorded with the backlog CLI) and a `--ref` to the record it implements. Coordinator tasks hold no implementation; their children are the PRs.
- **No lingering migration state.** No task leaves a shim, a re-export, a second home, or a new import-linter ignore entry. A package moves only after every service it uses is reachable in its final form (a contract from the service registry, or a capability's `api.py`); that is encoded as dependencies.
- `backlog sequence list` computes the parallelizable waves from the dependency graph; `backlog board` shows status.

## Target (decisions/plugin-architecture.md)

Six layers under `app/`:
- `server/`: host, lifespan, plugin manager, Slack runtime, scheduler runtime, framework services.
- `features/`: business plugins.
- `capabilities/`: engines and shared business capabilities (approvals, webhooks, notifications, audit, people, rotations, workplace systems).
- `infrastructure/`: hosting implementations only.
- `integrations/`: vendor clients (factory + classifier + settings).
- `contracts/`: the public plugin API (hookspecs, core-service Protocols, shared types).

Features and capabilities never import `infrastructure/` or `server/`; features never import each other. Core services come from an svcs registry. Plugins load from pyproject entry points and are enabled per environment in TOML configuration files. Reactions go through capability extension points or the queue contract; there is no in-process event bus. Legacy `modules/` is rebuilt by surface, not moved.

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

## Phase 1 — Decision corpus adoption (m-1) — done

`decisions/*.md` is the only source of truth; `docs/adr/` is retired.

## Phase 2 — Mechanical enforcement (m-2)

Toolchain per decisions/toolchain.md: Python 3.14 everywhere, uv lockfile end to end (TASK-14), ruff, blocking mypy with a strict ratchet (TASK-16), pre-commit (TASK-17), test gates (TASK-20), the EN/FR parity gate (TASK-21), the dependency-vulnerability gate (TASK-66).

## Phase 2b — Plugin architecture foundation (m-7)

Enforcement first, then the layers, in dependency order:
1. **Contract and rules:** CLAUDE.md, the Copilot instructions and the skills restate the six layers (TASK-104). import-linter lands with the six-layer contracts and a shrink-only ignore list (TASK-18).
2. **contracts/:** OperationResult envelope fix (TASK-105), then `app/contracts/` with OperationResult/OperationStatus (TASK-106). The Slack handler contract (TASK-26.1), then all hookspecs, the hookimpl marker and the scheduler Protocol (TASK-107). The storage Protocol after its redesign (TASK-27.1 -> TASK-108). The coordination Protocol with its rename (TASK-58).
3. **Host:** svcs service registry with eager boot validation (TASK-109, replaces the retired TASK-29), entry-point plugin loading (TASK-110), TOML configuration (TASK-111), per-environment enablement (TASK-112), the extension-point phase (TASK-113), the package generator and shape check (TASK-114).
4. **Framework services to server/:** Slack runtime (TASK-26.2, then async Bolt TASK-33), logging (TASK-115), security plus the current-user contract (TASK-116), i18n library decision and translator contract (TASK-117 -> TASK-118), scheduler runtime (TASK-64 -> TASK-52).
5. **Capabilities:** directory, drive and spreadsheets (TASK-119, TASK-120, TASK-121), audit (TASK-122), rotations, which removes the oncall_sync -> user_rotations import (TASK-123), notifications with its first consumer (TASK-125), approvals (TASK-60, on hold behind 1-3).
6. **Features:** existing packages move to `features/` one per PR (TASK-124 and children); `packages/` is deleted last.

**Exit:** the six layers exist; import-linter enforces them with a shrinking ignore list; no package imports `infrastructure/`, `server/` or another feature.

## Phase 3 — Client layer convergence (m-3)

One client generation per decisions/outbound-clients.md and sdk-typing.md. Done: the deprecated `infrastructure/clients` tree, the `_next` twins, the Google dispatcher and mirror layer, and the AWS dispatcher, shield and mirrors. Remaining: the AWS cleanup (TASK-25.2.6 series), Slack factory and classifier (TASK-25.4), MaxMind, Opsgenie, Sentinel, Notify, Trello and OpenAI (TASK-25.5 to 25.10), one settings home per vendor (TASK-24), Google write replay safety (TASK-87 series). Business operations leaving a vendor package go to a feature's or capability's `adapters/`, never to `infrastructure/`. Integrations import only `contracts/` shared types.

**Exit:** every vendor package exports only factories, a classifier and settings; the vendor-contract baseline is empty.

## Phase 4 — Infrastructure hardening (m-4)

Hosting contracts made real: capability-shaped storage (TASK-27 series), the coordination rename and lease hardening (TASK-58, TASK-99 to TASK-103), the queue contract and outbox when its first consumer exists (TASK-34), the RetryStore consolidation (TASK-59), the middleware trio and logging pipeline (TASK-28 series), distributed rate limiting (TASK-31), the service health model (TASK-92), the event-bus deletion with no replacement (TASK-30, after TASK-61), the webhooks capability (TASK-37 series, then TASK-47 to TASK-49 for HMAC and rate limits). The approvals consumers follow: access (TASK-61), SaaS subscriptions (TASK-62), AI keys (TASK-63).

**Exit:** the security and operations records' Checks pass; records flip `applies: target` -> `now`.

## Phase 5 — Legacy strangler (m-5) — rebuild by surface

Per decisions/migration.md: fix the double registration (TASK-35), inventory every legacy surface with its target feature or capability and pin it with smoke tests (TASK-36), then rebuild surface by surface:
- webhooks (TASK-37);
- incident, after the architecture decision (TASK-97 -> TASK-38);
- role, secret and atip (TASK-39);
- AWS and provisioning (TASK-88);
- the remainder (TASK-40);
- jobs, strangled as their surfaces move (TASK-65);
- system endpoints and `app/api/` (TASK-53);
- `models/` and `utils/` (TASK-55, TASK-56).
TASK-41 executes the "Done means" checklist.

**Exit:** `app/modules/` gone; other teams verifiably unaffected (smoke suite green throughout).

## Phase 6 — Multi-transport (m-6) — blocked until Teams is funded

Teams follows the Slack split: runtime in `server/teams/`, handler contract in `contracts/`, client in `integrations/` (TASK-42, TASK-43).

## Review-batch guidance

A task is the unit of acceptance, not necessarily one PR. Keep `main` releasable after every merge. Never mix a mechanical move with a behaviour change in one PR. A mechanical move rewrites every importer in the same change, because a split that needs a re-export shim is the brittle state this plan avoids.
