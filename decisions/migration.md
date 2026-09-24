---
status: Accepted
date: 2026-07-06
applies: now
scope: The strangler-fig plan for legacy app/modules/ and the coexistence rules that hold until it completes.
---

# Legacy Migration

## Context

`app/modules/` — 77 files, ~12.4k LOC, 13 module groups — is the original Slack bot: hard-coded registration (`server/lifespan.py`), direct SDK use, no layering. **Other teams depend on it in production.** The old corpus described the target architecture in 44 records and never once decided how to get there; this record is that decision. The external compatibility contract is the *Slack command surface and webhook URLs*, not the code — those must keep working through every step.

## Decision

**Coexistence rules (in force now):**

1. **Freeze:** no new features and no new capabilities in `app/modules/`. Bug fixes are allowed; anything more starts as a feature package. **One bounded carve-out:** retiring the overloaded `AppSettings.PREFIX` command-namespace *is* permitted inside frozen modules — the overload blocks the settings-home consolidation ([configuration.md](configuration.md)) and forces the environment-derivation guardrail to carry a growing whitelist, so it is treated as a foundational cleanup rather than a feature change. It runs per-module, one PR each, behind pre/post command-name smoke tests (the same external-contract protection the freeze exists to enforce), swapping only each module's read of `AppSettings.PREFIX` for the transport's `COMMAND_PREFIX` ([transport-slack.md](transport-slack.md)); no other behavior in a frozen module changes under this carve-out.
2. **No new dependents:** `packages/` and `infrastructure/` never import from `modules/`. Modules may keep importing `integrations/` and `infrastructure/` (they already do — that's the strangler working).
3. **Baselines only ratchet down:** import-linter ignore lists and every freeze baseline under `app/bin/baselines/` never gain entries; a new baseline is seeded once, when its guard lands.
4. Modules register via the legacy hard-coded list *or* hookimpls, never both (the current double-registration of `dev`/`sre` is fixed first — it's a live bug risk).
5. **Safe-to-move pure logic is not the freeze.** Rule 1's freeze and the per-module recipe's "no zombie halves" guard stop a frozen module's *host-registrable surface* (routes, Slack commands, hookimpls, handler behavior) from partially migrating — they do not block relocating logic that has no host-registrable surface at all. A private, dependency-free function that ships no hookimpl and no entry-point may move out of a frozen module into a real `packages/<concern>/` home ahead of that module's full migration; the frozen module then imports it from its new location — an import-path change, not new behavior, so it is a bug-fix-shaped change under rule 1, not a new capability. Precedent: `packages/incident_draft` and `packages/incident_summary` already coexist with `app/modules/incident/` as net-new, independently-registered capabilities; this rule extends that same coexistence to the narrower case of relocating existing pure logic rather than building a new capability. Bright line: if the destination package would need a hookimpl or entry-point line to do anything, it is capability migration and the full per-module recipe applies undiminished; if it ships no hookimpls and only holds importable functions/values, it qualifies for this lighter path. **The destination is the concern's final home, not a flat placeholder:** logic belonging to an existing feature context lands directly in that context's umbrella (`packages/incident/scheduling/`, not `packages/incident_scheduling/`) per [feature-packages.md](feature-packages.md)'s umbrella rule. Relocating under this path is cheap only while the package is new, so paying it once at creation is strictly cheaper than a later rename.
6. **A new shared capability is an expand step, not a cutover.** Until a feature's migration slice completes, its legacy module may keep calling its existing vendor integration, including feature-specific metadata conventions. The new capability is not widened to reproduce those conventions just to make the legacy module an immediate consumer; the feature adapter owns vendor-specific behavior during migration, and the old integration is deleted only once every approved consumer has moved.

**Per-module migration recipe** (one PR series per module):

1. Write/verify smoke tests for the module's Slack commands and webhooks — the external contract, captured before touching anything.
2. Build the feature package per [feature-packages.md](feature-packages.md): service layer on Protocols, Path B adapters where the module hard-codes vendor calls, handlers via hookspecs, locales via [i18n.md](i18n.md).
3. Cut over: remove the module from `_register_legacy_handlers()`; command names and behavior unchanged; smoke tests green.
4. Delete the module directory in the same series. No zombie halves — a module is either legacy or migrated, never both.

**Order** (risk × value): `webhooks` first (security-sensitive; gains signature auth from [security.md](security.md)), then `incident` (largest user surface), then the small wins (`role`, `secret`, `atip`) to cement the pattern, then the remainder. `dev`/`sre` need only de-duplication and hookimpl cleanup.

**Webhooks runs refactor-first, ahead of this queue.** Its antipatterns must not be relocated into `packages/`, and its HMAC hardening is built on the target design, so it is rearchitected in single-PR slices in m-4, before the HMAC work, with the smoke suite holding its URLs and behaviour across every slice. [webhooks.md](webhooks.md) owns the target design and its tickets. The remaining modules follow the plain recipe in m-5.

**Done means:** `app/modules/` deleted, `modules` removed from plugin discovery, `_register_legacy_handlers()` deleted, `python-i18n` removed, the deprecated-client baseline empty.

## Consequences

- Other teams see zero change per migrated module (verified by the smoke tests written *before* migration).
- The freeze creates pressure: a requested change to a frozen module is the trigger to migrate it — the strangler feeds itself.
- This is quarters of background work for a single dev; the recipe makes each module a bounded, shippable unit rather than one open-ended rewrite.

## Checks

- Baselines monotonically shrink: each freeze guard under `app/bin/` compares the tree against its baseline in CI and fails on any net-new entry; a guard is retired with its baseline once that baseline is empty ([toolchain.md](toolchain.md)).
- No `from modules` imports in `packages/` or `infrastructure/`.
- Per migrated module: smoke tests exist and pass pre- and post-cutover in the same PR series.
- Packages created under rule 5's lighter path ship no hookimpls/entry-point line until they graduate to full capability migration under the per-module recipe, and sit in their final umbrella position from creation ([feature-packages.md](feature-packages.md)).

**Changes:**
- 2026-09-03: added coexistence rule 5, relocating host-surface-free pure logic out of frozen modules ahead of their full migration.
- 2026-09-03: rule 5 destinations are final umbrella positions, per [feature-packages.md](feature-packages.md).
- 2026-09-08: added coexistence rule 6, a new shared capability is an expand step and is not widened for legacy conventions.
- 2026-09-17: rule 3 and the baseline check cover every freeze baseline under `app/bin/baselines/`.
- 2026-09-24: webhooks sequencing defers to [webhooks.md](webhooks.md), and change notes are one sentence each.
