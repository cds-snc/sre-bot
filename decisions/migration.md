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
5. **Safe-to-move pure logic is not the freeze.** Rule 1's freeze and the per-module recipe's "no zombie halves" guard stop a frozen module's *host-registrable surface* (routes, Slack commands, hookimpls, handler behavior) from partially migrating — they do not block relocating logic that has no host-registrable surface at all. A private, dependency-free function that ships no hookimpl and no entry-point may move out of a frozen module into a real `packages/<concern>/` home ahead of that module's full migration; the frozen module then imports it from its new location — an import-path change, not new behavior, so it is a bug-fix-shaped change under rule 1, not a new capability. Precedent: `packages/incident_draft` and `packages/incident_summary` already coexist with `app/modules/incident/` as net-new, independently-registered capabilities; this rule extends that same coexistence to the narrower case of relocating existing pure logic rather than building a new capability. Bright line: if the destination package would need a hookimpl or entry-point line to do anything, it is capability migration and the full per-module recipe applies undiminished; if it ships no hookimpls and only holds importable functions/values, it qualifies for this lighter path. **The destination is the concern's final home, not a flat placeholder:** logic belonging to an existing feature context lands directly in that context's umbrella (`packages/incident/scheduling/`, not `packages/incident_scheduling/`) per [feature-packages.md](feature-packages.md)'s umbrella rule. Relocating under this path is cheap only while the package is new, so paying it once at creation is strictly cheaper than a later rename.

**Per-module migration recipe** (one PR series per module):

1. Write/verify smoke tests for the module's Slack commands and webhooks — the external contract, captured before touching anything.
2. Build the feature package per [feature-packages.md](feature-packages.md): service layer on Protocols, Path B adapters where the module hard-codes vendor calls, handlers via hookspecs, locales via [i18n.md](i18n.md).
3. Cut over: remove the module from `_register_legacy_handlers()`; command names and behavior unchanged; smoke tests green.
4. Delete the module directory in the same series. No zombie halves — a module is either legacy or migrated, never both.

**Order** (risk × value): `webhooks` first (security-sensitive; gains signature auth from [security.md](security.md)), then `incident` (largest user surface), then the small wins (`role`, `secret`, `atip`) to cement the pattern, then the remainder. `dev`/`sre` need only de-duplication and hookimpl cleanup.

**Webhooks is a rearchitecture, not a lift-and-shift — and it is pulled ahead of this milestone.** The `webhooks` module predates the corpus and carries antipatterns that the per-module recipe's step 2 ("build the feature package") must *not* relocate into `packages/`: probabilistic payload-type guessing, filesystem-walk handler registries resolved by runtime import strings, a Slack-terminal output shape, raw DynamoDB item shapes at the route edge, and no ingest idempotency. Its target shape — the `verify → interpret (by declared source) → dispatch (multi-sink)` pipeline, transport-neutral intents, and secure-by-default lifecycle — is a decision of its own ([webhooks.md](webhooks.md)). Because the Phase-4 authenticity hardening (HMAC verification and secure-by-default secret issuance, [security.md](security.md)) must be built on that target design rather than on the legacy CRUD and rewritten later, the webhooks migration runs **refactor-first**: it is pulled out of this milestone's general strangler queue and into **m-4**, sequenced *before* the HMAC work. The move-recipe still holds per slice — the external contract (webhook URLs and behaviour) is captured by smoke tests (TASK-36) before any change and stays green across every slice — but webhooks uniquely also *adds* capability (multi-transport dispatch, cross-feature triggering, idempotency) as it migrates, so it is decomposed into single-PR slices rather than one PR series: coordinator TASK-37 with slices TASK-37.1–TASK-37.5 (extraction, source-declared parsing, intent+renderer, cutover+delete, dispatch fan-out), then TASK-47 (lifecycle + HMAC), TASK-48 (legacy-sender enforcement burn-down), and TASK-49 (per-`webhook_id` rate limiting). The remaining modules follow the plain lift-and-shift recipe in this milestone (m-5).

**Done means:** `app/modules/` deleted, `modules` removed from plugin discovery, `_register_legacy_handlers()` deleted, `python-i18n` removed, the deprecated-client baseline empty.

## Consequences

- Other teams see zero change per migrated module (verified by the smoke tests written *before* migration).
- The freeze creates pressure: a requested change to a frozen module is the trigger to migrate it — the strangler feeds itself.
- This is quarters of background work for a single dev; the recipe makes each module a bounded, shippable unit rather than one open-ended rewrite.

## Checks

- Baselines monotonically shrink: the deprecated-import guardrail compares the tree against its baseline and fails on any net-new violation (run in CI once [toolchain.md](toolchain.md)'s ticket wires it).
- No `from modules` imports in `packages/` or `infrastructure/`.
- Per migrated module: smoke tests exist and pass pre- and post-cutover in the same PR series.
- Packages created under rule 5's lighter path ship no hookimpls/entry-point line until they graduate to full capability migration under the per-module recipe, and sit in their final umbrella position from creation ([feature-packages.md](feature-packages.md)).

**Change note (2026-09-03, post-acceptance):** added coexistence rule 5, permitting relocation of host-surface-free pure logic out of frozen modules into a real `packages/<concern>/` home ahead of that module's full migration, grounded in the already-shipped `packages/incident_draft`/`packages/incident_summary` precedent. Motivated by TASK-25.1.6.2 (Google Workspace vendor-mirror cleanup), which needed a non-legacy home for pure Calendar-availability helpers living inside `app/integrations/google_workspace/` and consumed only by `app/modules/incident/schedule_retro.py`.

**Change note (2026-09-03, second amendment):** closed rule 5's open shape/naming question. [feature-packages.md](feature-packages.md) now decides it — complex features get an umbrella directory with subdomain subpackages, and flat `<feature>_<subfeature>` naming is rejected — so rule 5 destinations are stated as final umbrella positions rather than deferred. `packages/incident_draft` and `packages/incident_summary` become named deviations relocated by TASK-38.
