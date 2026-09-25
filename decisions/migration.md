---
status: Accepted
date: 2026-07-06
applies: now
scope: The strangler-fig plan for legacy app/modules/, the coexistence rules that hold until it completes, and the disposition of every non-layer top-level directory.
---

# Legacy Migration

## Context

`app/modules/` (13 module groups, 73 files, about 12k lines) is the original Slack bot. It has no layering and calls vendor SDKs directly. `server/lifespan.py` registers most of it through the hard-coded `_register_legacy_handlers()` list; `dev` and `sre` also ship hookimpls, and `sre` is registered both ways. `jobs/scheduled_tasks.py` imports `modules.aws` and `modules.incident`, and `api/v1/routes/webhooks.py` imports `modules.webhooks` and `modules.slack`. Nothing in `packages/` or `infrastructure/` imports `modules/`.

The modules are not organised around features. `modules/sre/` and `modules/aws/` are grab-bags of unrelated commands, and `modules/incident/` is built around Google Workspace resources (folders, documents, Meet) rather than around the incident itself. Moving them as they are would carry that shape into the new layers.

**Other teams depend on this code in production.** The external contract is the Slack command surface, the interactions and the webhook URLs, not the code. Those must keep working through every step.

## Decision

**Legacy modules are rebuilt by surface, not moved** ([plugin-architecture.md](plugin-architecture.md)).

**Coexistence rules (in force now):**

1. **Freeze:** no new features and no new capabilities in `app/modules/`. Bug fixes are allowed; anything more starts as a feature or capability package.
2. **No new dependents:** `features/`, `capabilities/`, `contracts/` and `infrastructure/` never import `modules/`, and neither does `packages/` while it exists. Modules may keep importing `integrations/`, `infrastructure/` and `packages/`.
3. **Baselines only ratchet down:** import-linter ignore lists and every freeze baseline under `app/bin/baselines/` never gain entries. A new baseline is seeded once, when its guard lands.
4. **One registration path per module:** the legacy hard-coded list or hookimpls, never both. The current double registration of `sre` is fixed first, because it is a live bug risk.
5. **Pure logic may leave a frozen module early.** The freeze and "no half-done surfaces" stop a module's *surfaces* (routes, Slack commands, interactions, jobs, hookimpls) from partially migrating. They do not block moving a private, dependency-free function that registers nothing. Such a function may move to its final home, `features/<feature>/<subdomain>/` or `capabilities/<c>/`, and the frozen module then imports it from there. That is an import-path change, so it counts as a bug fix under rule 1. Bright line: if the destination would need a hookimpl or an entry point to do anything, it is a surface rebuild and the full recipe below applies. The destination is the final umbrella position from creation, per [feature-packages.md](feature-packages.md), because a later rename costs more.
6. **A new capability is an expand step, not a cutover.** Until a surface is rebuilt, its legacy module keeps calling its existing vendor integration, feature-specific metadata conventions included. A new capability in `capabilities/` is not widened to reproduce those conventions just to make the legacy module a consumer. The old integration is deleted only once every consumer has moved.

**Per-surface recipe:**

1. **Inventory.** List every user-facing surface of `modules/`: slash commands, interactions, webhook routes and scheduled jobs. Assign each one to a target feature or capability.
2. **Pin.** Write smoke tests that pin each surface's external behaviour before touching it.
3. **Rebuild.** Build the surface in the standard package shape ([feature-packages.md](feature-packages.md)) in its target feature or capability, with handlers registered through hookspecs and strings through the translator contract ([i18n.md](i18n.md)). Vendor concepts leave the feature on the way: an incident works with documents and a chat channel through capability contracts, not with Google Drive folders.
4. **Cut over.** Remove the legacy registration of that surface in the same PR series. Command names and behaviour stay the same; smoke tests stay green.
5. **Delete.** A legacy module is deleted when its last surface has moved.

No migration is left half-done: a surface is either legacy or rebuilt, never both.

**Order** (risk × value): `webhooks` first, then `incident` (largest user surface), then the small wins (`role`, `secret`, `atip`) to cement the pattern, then the rest. `webhooks` is security-sensitive and runs refactor-first, ahead of this queue; [webhooks.md](webhooks.md) owns its target design, sequencing and tickets.

**Non-layer top-level directories.** The sanctioned entries under `app/` are the six layers in [plugin-architecture.md](plugin-architecture.md), `main.py` and `tests/`. Every other top-level directory is transitional, with a disposition and a ticket. None is a home for new code.

| Directory | Disposition | Ticket |
| --- | --- | --- |
| `packages/` | Current feature home. Each feature moves to `features/`, and shared engines to `capabilities/`, one package per PR. | [plugin-architecture.md](plugin-architecture.md) Migration |
| `modules/` | Legacy Slack bot. Rebuilt surface by surface into features and capabilities, then deleted. | TASK-37, TASK-38, TASK-39, TASK-40, TASK-41 |
| `jobs/` | Scheduler registry. Each job moves to its owning feature or capability and registers through the scheduler contract in `contracts/`; the runtime moves to `server/` and runs each job once across replicas on a coordination lease. | TASK-52 |
| `api/` | Legacy HTTP surface. Feature routes move to their owning packages; system endpoints (health, version, landing) move to `server/`. | TASK-53 |
| `bin/` | Operator and dev tooling, not app runtime code, so exempt from the layer contracts. Kept; `entry.sh`'s boot-time secret fetch retires once the secrets contract has an implementation. | TASK-54 |
| `models/` | Shared boundary DTOs. Each moves to its owning feature or capability, or to `contracts/` when it crosses layers; then the directory is deleted. | TASK-55 |
| `utils/` | Grab-bag helpers. Each moves to its owning layer without adding a forbidden import; then the directory is deleted. | TASK-56 |
| `locales/` | Legacy `python-i18n` catalogues. Deleted with the last legacy surface, replaced by per-package catalogues ([i18n.md](i18n.md)). | TASK-41 |
| `geodb/` | MaxMind database baked into the image by AWS-coupled CI. Rebuilt as a configurable, cloud-agnostic source. | TASK-57 |

**Done means:** `app/modules/` deleted, `modules` removed from plugin discovery, `_register_legacy_handlers()` deleted, `python-i18n` removed, and no freeze baseline lists a `modules/` path.

## Consequences

- Other teams see no change per rebuilt surface; the smoke tests written before each rebuild prove it.
- Rebuilding by surface costs more than moving files, but it is the only way to get the grab-bags and the Google-shaped incident code into features that fit the layers.
- The freeze creates pressure: a requested change to a frozen module triggers the rebuild of that surface. The strangler feeds itself.
- This is quarters of background work for one developer. The recipe makes each surface a bounded, shippable unit instead of one open-ended rewrite.

## Checks

- Each freeze guard under `app/bin/` runs in CI, compares the tree against its baseline and fails on any new entry. A guard is retired with its baseline once the baseline is empty ([toolchain.md](toolchain.md)).
- No `modules` import in `features/`, `capabilities/`, `contracts/`, `infrastructure/` or `packages/` (grep today; import-linter `forbidden` once [plugin-architecture.md](plugin-architecture.md)'s contracts land).
- Per rebuilt surface: smoke tests exist and pass before and after cutover in the same PR series, and the legacy registration of that surface is gone.
- Packages created under rule 5 ship no hookimpl or entry point until a surface rebuild adds one, and sit in their final umbrella position from creation.
- Every top-level directory under `app/` other than the six layers, `main.py` and `tests/` has a row in the table above (review when adding one).

**Changes:**
- 2026-09-03: added coexistence rule 5, relocating host-surface-free pure logic out of frozen modules ahead of their full migration.
- 2026-09-03: rule 5 destinations are final umbrella positions, per [feature-packages.md](feature-packages.md).
- 2026-09-08: added coexistence rule 6, a new shared capability is an expand step and is not widened for legacy conventions.
- 2026-09-17: rule 3 and the baseline check cover every freeze baseline under `app/bin/baselines/`.
- 2026-09-24: webhooks sequencing defers to [webhooks.md](webhooks.md); modules are rebuilt by surface into the plugin-architecture layers, the retired `PREFIX` carve-out is removed, and the non-layer directory table moved here.
