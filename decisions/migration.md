---
status: Accepted
date: 2026-07-06
applies: now
scope: The strangler-fig plan for legacy app/modules/, the coexistence rules that hold until it completes, and the disposition of every non-layer top-level directory.
---

# Legacy Migration

## Context

`app/modules/` (13 module groups, 73 files, about 12k lines) is the original Slack bot. It has no layering and calls vendor SDKs directly. `server/lifespan.py` registers it by hand: the Bolt handlers through the hard-coded `_register_legacy_handlers()` list, and the `sre` and `dev` provider subcommands through `_register_legacy_slack_commands()`; no module under `modules/` ships a hookimpl. `jobs/scheduled_tasks.py` imports `modules.aws` and `modules.incident`, and `api/v1/routes/webhooks.py` imports `modules.webhooks` and `modules.slack`. Nothing in `packages/` or `infrastructure/` imports `modules/`.

The modules are not organised around features. `modules/sre/` and `modules/aws/` are grab-bags of unrelated commands, and `modules/incident/` is built around Google Workspace resources (folders, documents, Meet) rather than around the incident itself. Moving them as they are would carry that shape into the new layers.

**Other teams depend on this code in production.** The external contract is the Slack command surface, the interactions and the webhook URLs, not the code. Those must keep working through every step.

## Decision

**Legacy modules are rebuilt by surface, not moved** ([plugin-architecture.md](plugin-architecture.md)).

**Coexistence rules (in force now):**

1. **Freeze:** no new features and no new capabilities in `app/modules/`. Bug fixes are allowed; anything more starts as a feature or capability package. A legacy edit an approved task plan names is also allowed, each tagged with a `TODO(TASK-<id>)` naming the task that removes it: a rollback guard or translated write that keeps the legacy path correct on records a rebuilt writer upgraded ([incident-management.md](incident-management.md) Migration), an import repoint under rule 5, and the deletion of a retired surface.
2. **No new dependents:** `features/`, `capabilities/`, `contracts/` and `infrastructure/` never import `modules/`, and neither does `packages/` while it exists. Modules may import `integrations/`, `infrastructure/`, `packages/`, and `features/` and `capabilities/` (settings, rule 5 destinations and named rollback guards); the dependency only ever points from `modules/` outward.
3. **Baselines only ratchet down:** import-linter ignore lists and every freeze baseline under `app/bin/baselines/` never gain entries. A new baseline is seeded once, when its guard lands. One exception, the named expand step: an entry may be added only in the PR of the task whose approved plan names it, with an owner comment naming the queued task that removes it. It covers a legacy pin task's named conftest seam ([testing.md](testing.md); the test-seam guard also checks that the fixture names the same owner) and a capability landing ahead of its queued first consumer (TASK-114 OQ2, [plugin-architecture.md](plugin-architecture.md)). Rationale: suppression baselines admit new entries only through an explicit, reviewed step and report unmatched ones ([ESLint bulk suppressions](https://eslint.org/docs/latest/use/suppressions), [PHPStan baseline](https://phpstan.org/user-guide/baseline)). A mechanical move re-keys entries, same count ([testing.md](testing.md)); that is not growth.
4. **One registration path per surface:** each command or interaction is registered by the legacy hard-coded list or by a hookimpl, never both. A rebuilt subcommand registers under a legacy parent (`sre.incident.status` beside the legacy `/sre incident` dispatcher), and the provider routes to it first.
5. **Pure logic may leave a frozen module early.** The freeze and "no half-done surfaces" stop a module's *surfaces* (routes, Slack commands, interactions, jobs, hookimpls) from partially migrating. They do not block moving a private, dependency-free function that registers nothing. Such a function may move to its final home, `features/<feature>/<subdomain>/` (or the umbrella's `core/` or `common/`) or `capabilities/<c>/`, and the frozen module then imports it from there. That is an import-path change, so it counts as a bug fix under rule 1. Bright line: if the destination would need a hookimpl or an entry point to do anything, it is a surface rebuild and the full recipe below applies. The destination is the final umbrella position from creation, per [feature-packages.md](feature-packages.md), because a later rename costs more.
6. **A new capability is an expand step, not a cutover.** Until a surface is rebuilt, its legacy module keeps calling its existing vendor integration, feature-specific metadata conventions included. A new capability in `capabilities/` is not widened to reproduce those conventions just to make the legacy module a consumer. The old integration is deleted only once every consumer has moved.
7. **Task ids in code are removal markers only.** Code, comments and docstrings describe what the code does now. A backlog task id appears in a `.py` file only as `TODO(TASK-<id>)`, naming the task that deletes or changes the lines it sits on; that task finds its markers with a search and removes them. Where code came from, which task added it, or which future task will own a behaviour goes stale the day that task ships and stays in git history and the task. Test docstrings carry no task id at all ([testing.md](testing.md)). Owner comments in TOML ignore lists and freeze baselines stay under rule 3. The task-reference guard (`app/bin/check_task_references.py`) freezes the existing mentions and fails on a new one.

**Per-surface recipe:**

1. **Inventory.** List every user-facing surface of `modules/`: slash commands, interactions, webhook routes and scheduled jobs. Assign each one to a target feature or capability.
2. **Pin.** Write pinning tests (`tests/integration/legacy_surface/`) that pin each surface's external behaviour before touching it. A pin enters only through what survives the rebuild: command names, ids on messages already posted, and event types; it opens a modal from its command and reads the modal's ids from the opened view. It asserts what users and external systems see: Slack-visible output and outcomes at the faked edges in domain terms (a field read back through the show command, one timeline entry), never stored item shapes or call shapes inside `modules/`. Message layout the bot builds (block structure, wording) is asserted by identifying facts, not as a golden layout, so a rebuilt renderer or provisioned template ([organisation-content.md](organisation-content.md)) changes layout without rewriting the pin; ids on posted messages, button values and sender-supplied content forwarded unchanged are asserted exactly. A pin does not assert the artifact of a recorded legacy bug; it asserts the surrounding fact, so the bug can end as a kind (a) change (step 4) ([characterization tests](https://en.wikipedia.org/wiki/Characterization_test)). A behaviour the rebuild deliberately ends is pinned in a test named `test_legacy_only_*`, deleted by the task that ends it. Where the pin's fakes may sit is [testing.md](testing.md)'s seam rule.
3. **Rebuild.** Build the surface in the standard package shape ([feature-packages.md](feature-packages.md)) in its target feature or capability, with handlers registered through hookspecs and strings through the translator contract ([i18n.md](i18n.md)). Vendor concepts leave the feature on the way: an incident works with documents and a chat channel through capability contracts, not with Google Drive folders.
4. **Cut over.** Remove the legacy registration of that surface in the same PR series. Command names and ids on posted messages stay (the ids keep a legacy alias until the contract task, [transport-slack.md](transport-slack.md)); modal-internal ids take the plugin prefix. Behaviour stays the same by default, and the cutover PR rewires the pins' fixtures to the target's fakes with their assertions unchanged. A cutover changes behaviour only as a **named change** of one of four kinds:
   - (a) a recorded legacy bug that no pin asserts;
   - (b) behaviour an accepted end-state decision replaces (the record written where the legacy path skipped it, roles read from the record instead of Drive properties);
   - (c) a deprecated form whose announced end date has passed, after a check of its use in production logs; one still in use keeps an alias until the contract task;
   - (d) a surface retired with no target.

   An addition (a new option, a new command) is not a named change: it needs an explicit ruling in the approved plan, or it waits for its own task. Each named change is approved in the task plan, pinned before the cutover (a `test_legacy_only_*` test for ended behaviour, deleted by the cutover, or an edited pin assertion citing the ruling), and listed in the PR body with its kind and the revert target.
5. **Delete.** A legacy module is deleted when its last surface has moved.

No migration is left half-done: each command or interaction is either legacy or rebuilt, never both. A module may hold both while its surfaces move one by one; records written by both paths meanwhile follow [incident-management.md](incident-management.md) Migration (expand, backfill, switch reads, contract; rollback guards).

**Order** (risk × value): `incident` (largest user surface, TASK-145), then the small wins (`role`, `secret`, `atip`) to cement the pattern, then the rest. `webhooks` is security-sensitive and runs refactor-first; [webhooks.md](webhooks.md) owns its target design, sequencing and tickets.

**Non-layer top-level directories.** The sanctioned entries under `app/` are the six layers in [plugin-architecture.md](plugin-architecture.md), `main.py` and `tests/`. Every other top-level directory is transitional, with a disposition and a ticket. None is a home for new code.

| Directory | Disposition | Ticket |
| --- | --- | --- |
| `packages/` | Current feature home. Each feature moves to `features/`, and shared engines to `capabilities/`, one package per PR. | [plugin-architecture.md](plugin-architecture.md) Migration |
| `modules/` | Legacy Slack bot. Rebuilt surface by surface into features and capabilities, then deleted. | TASK-37, TASK-145 (incident, replacing TASK-38), TASK-39, TASK-40, TASK-41 |
| `jobs/` | Scheduler registry. Each job moves to its owning feature or capability and registers through the scheduler contract in `contracts/`; the runtime moves to `server/` and runs each job once across replicas on a coordination lease. | TASK-52 |
| `api/` | Legacy HTTP surface. Feature routes move to their owning packages; system endpoints (health, version, landing) move to `server/`. | TASK-53 |
| `bin/` | Operator and dev tooling, not app runtime code, so exempt from the layer contracts. Kept; `entry.sh` and its boot-time fetch of the SSM blobs are deleted (TASK-111.15.1): the container starts uvicorn directly and the task definition injects each secret. | TASK-54 |
| `models/` | Shared boundary DTOs. Each moves to its owning feature or capability, or to `contracts/` when it crosses layers; then the directory is deleted. | TASK-55 |
| `utils/` | Grab-bag helpers. Each moves to its owning layer without adding a forbidden import; then the directory is deleted. | TASK-56 |
| `locales/` | Legacy `python-i18n` catalogues. Deleted with the last legacy surface, replaced by per-package catalogues ([i18n.md](i18n.md)). | TASK-41 |
| `geodb/` | MaxMind database baked into the image by AWS-coupled CI. Rebuilt as a configurable, cloud-agnostic source. | TASK-57 |

**Done means:** `app/modules/` deleted, `modules` removed from plugin discovery, `_register_legacy_handlers()` deleted, `python-i18n` removed, and no freeze baseline lists a `modules/` path; the test-seam guard's `LEGACY_ROOT` (`bin/check_test_seams.py`) is dropped with it.

## Consequences

- Other teams see only named changes per rebuilt surface, each listed in its PR body; the pins written before each rebuild prove the rest is unchanged. Strict parity is not the goal: replicating every legacy behaviour is the [feature parity trap](https://martinfowler.com/articles/patterns-legacy-displacement/feature-parity.html), and deprecated forms are removed after their announced window, as CLIs do ([Kubernetes deprecation policy](https://kubernetes.io/docs/reference/using-api/deprecation-policy/)).
- Rebuilding by surface costs more than moving files, but it is the only way to get the grab-bags and the Google-shaped incident code into features that fit the layers.
- The freeze creates pressure: a requested change to a frozen module triggers the rebuild of that surface. The strangler feeds itself.
- This is quarters of background work for one developer. The recipe makes each surface a bounded, shippable unit instead of one open-ended rewrite.

## Checks

- No task id in a `.py` file outside a `TODO(TASK-<id>)` marker (rule 7): `make check-task-references` in CI, its baseline only ratcheting down.
- Each freeze guard under `app/bin/` runs in CI, compares the tree against its baseline and fails on any new entry. A guard is retired with its baseline once the baseline is empty ([toolchain.md](toolchain.md)).
- No `modules` import in `features/`, `capabilities/`, `contracts/`, `infrastructure/` or `packages/` (grep today; import-linter `forbidden` once [plugin-architecture.md](plugin-architecture.md)'s contracts land).
- Per rebuilt surface: pins exist and pass before and after cutover in the same PR series, the legacy registration of that surface is gone, and each named change has its kind in the PR body.
- Packages created under rule 5 ship no hookimpl or entry point until a surface rebuild adds one, and sit in their final umbrella position from creation.
- Every top-level directory under `app/` other than the six layers, `main.py` and `tests/` has a row in the table above (review when adding one).

**Changes:**
- 2026-09-03: added coexistence rule 5, relocating host-surface-free pure logic out of frozen modules ahead of their full migration.
- 2026-09-03: rule 5 destinations are final umbrella positions, per [feature-packages.md](feature-packages.md).
- 2026-09-08: added coexistence rule 6, a new shared capability is an expand step and is not widened for legacy conventions.
- 2026-09-17: rule 3 and the baseline check cover every freeze baseline under `app/bin/baselines/`.
- 2026-09-24: webhooks sequencing defers to [webhooks.md](webhooks.md); modules are rebuilt by surface into the plugin-architecture layers, the retired `PREFIX` carve-out is removed, and the non-layer directory table moved here.
- 2026-10-01: rule 5 destinations include an umbrella's `core/` and `common/`, per [feature-packages.md](feature-packages.md).
- 2026-10-06: the `sre` and `dev` provider subcommands moved from hookimpls to the hand-written `_register_legacy_slack_commands()` step (TASK-110.1); no `modules/` hookimpl remains.
- 2026-11-06: pin contract (durable entry points, ids read from opened views, outcome assertions, `test_legacy_only_*` tests) and the cutover rule for ids (TASK-36.1.2 OQ1, human).
- 2026-11-06: rule 3 gains the named expand-step exception (an entry added only in the PR of the task the plan names, with an owner comment naming the removing task; covers pin-task seams and TASK-114 OQ2's capability entry) (TASK-187 OQ1, human).
- 2026-11-16: cutover named changes (step 4, kinds a-d; additions only by a plan ruling), rule 1 allows plan-named legacy edits with an owner TODO, rule 2 lets modules import features and capabilities one-way, rule 4 and "never both" apply per command or interaction, Consequences and Checks name pins and named changes, Order starts with incident; absorbs the cutover bug-fix rule TASK-145.8.5 was to add (TASK-145.8.4 OQ4, human).
- 2026-11-20: pin contract: bot-built layout asserted by identifying facts, ids, button values and forwarded sender content exactly; pins avoid asserting a recorded bug's artifact (TASK-36.2 OQ2, OQ5, human).
- 2026-11-25: rule 7: task ids in code are removal markers only (`TODO(TASK-<id>)`); history and scope pointers are written as behaviour; the task-reference guard and its baseline land with TASK-145.10.3 (human).
