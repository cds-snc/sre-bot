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
3. **Baselines only ratchet down:** the deprecated-import allowlist and import-linter baselines never gain entries.
4. Modules register via the legacy hard-coded list *or* hookimpls, never both (the current double-registration of `dev`/`sre` is fixed first — it's a live bug risk).

**Per-module migration recipe** (one PR series per module):

1. Write/verify smoke tests for the module's Slack commands and webhooks — the external contract, captured before touching anything.
2. Build the feature package per [feature-packages.md](feature-packages.md): service layer on Protocols, Path B adapters where the module hard-codes vendor calls, handlers via hookspecs, locales via [i18n.md](i18n.md).
3. Cut over: remove the module from `_register_legacy_handlers()`; command names and behavior unchanged; smoke tests green.
4. Delete the module directory in the same series. No zombie halves — a module is either legacy or migrated, never both.

**Order** (risk × value): `webhooks` first (security-sensitive; gains signature auth from [security.md](security.md)), then `incident` (largest user surface), then the small wins (`role`, `secret`, `atip`) to cement the pattern, then the remainder. `dev`/`sre` need only de-duplication and hookimpl cleanup.

**Done means:** `app/modules/` deleted, `modules` removed from plugin discovery, `_register_legacy_handlers()` deleted, `python-i18n` removed, the deprecated-client baseline empty.

## Consequences

- Other teams see zero change per migrated module (verified by the smoke tests written *before* migration).
- The freeze creates pressure: a requested change to a frozen module is the trigger to migrate it — the strangler feeds itself.
- This is quarters of background work for a single dev; the recipe makes each module a bounded, shippable unit rather than one open-ended rewrite.

## Checks

- Baselines monotonically shrink: the deprecated-import guardrail compares the tree against its baseline and fails on any net-new violation (run in CI once [toolchain.md](toolchain.md)'s ticket wires it).
- No `from modules` imports in `packages/` or `infrastructure/`.
- Per migrated module: smoke tests exist and pass pre- and post-cutover in the same PR series.
