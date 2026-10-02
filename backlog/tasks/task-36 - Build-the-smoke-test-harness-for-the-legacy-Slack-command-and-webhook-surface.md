---
id: TASK-36
title: Build the smoke-test harness for the legacy Slack command and webhook surface
status: Done
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-10-02 14:59'
labels:
  - migration
  - phase-5
  - testing
milestone: m-5
dependencies:
  - TASK-35
references:
  - decisions/migration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1290'
  - decisions/plugin-architecture.md
  - decisions/testing.md
  - decisions/transport-slack.md
priority: high
ordinal: 36000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rescoped 2026-09-24; test-layer placement corrected 2026-09-28 against decisions/testing.md; follow-up split and TASK-35 dependency confirmed 2026-09-28 (see comment log). decisions/migration.md step 1 (Inventory) now asks for more than a smoke-test list: every user-facing surface of modules/ (slash commands and subcommands, interactions, webhook routes, HTTP routes under app/api/, and scheduled jobs in app/jobs/) is listed with a target feature or capability, so each rebuild ticket knows where its surface lands. Surfaces are assigned by what they do, not by which module holds them today: modules/sre and modules/aws are grab-bags, and incident surfaces follow the TASK-97 decision.

Aligns with decisions/migration.md recipe step 1: capture the external compatibility contract (Slack command surface + webhook URLs) BEFORE touching any module. Other teams depend on this surface.

Depends on TASK-35 (fixes the modules/sre dev/sre double registration) landing first, so this task's sre pinning test can pin correct single-registration behaviour rather than working around or asserting a known bug.

register_slack_listeners(app: AsyncApp) is a declared hookspec with zero hookimpls today (confirmed 2026-09-28); the 8 register_slack_commands hookimpls are therefore the complete TASK-26.1 AC#3 surface, not a subset of it.

Steps:
1. Inventory every Slack command, action, webhook route, app/api/ route and scheduled job exposed by app/modules/ and the Slack-registering app/packages/ (grep registration sites + _register_legacy_handlers() in server/lifespan.py). Record the inventory as a checked-in table at app/tests/integration/legacy_surface/INVENTORY.md (not under app/tests/smoke/ - see step 3).
2. Write pinning tests that exercise each surface through the transport boundary (slack_bolt's public App.dispatch(BoltRequest) / AsyncApp.async_dispatch, or httpx.AsyncClient + ASGITransport for HTTP routes) asserting: command/listener acknowledged, response shape/text, side-effect stub invoked. Use fakes for backing services and for the outbound Slack client - the contract under test is the surface's external behaviour, not the vendor SDK or the hookimpl signature, so the tests keep passing unmodified when TASK-26.1 re-signs the hookimpls.
3. These are decisions/testing.md "integration" tests (<500ms, external deps stubbed), not "smoke" (on-demand, live backends, excluded from the PR gate by `pytest tests --ignore=tests/smoke`). They live in app/tests/integration/legacy_surface/ and run in the normal CI gate, because TASK-26.1 AC#4 needs them green in the standard `pytest tests --ignore=tests/smoke` run, before and after its change. The task title/labels predate this correction; decisions/testing.md is authoritative over the task's original "smoke layer" framing.
4. These tests are the pass/fail oracle for every TASK-37..40, TASK-52/TASK-65 and TASK-53 cutover, and for TASK-26.1 specifically.

Single-PR size gate: the full surface (6 slash commands, 34 interactions, 1 webhook route, 5 job entry points - see plan) is too large for one reviewable PR of pinning tests. This task is Slice 1: the full inventory (all surfaces, documentation only) plus pinning tests for exactly the Slack command/listener registration surface that TASK-26.1 rewrites (the 8 register_slack_commands hookimpls under modules/ and packages/). Remaining rows are inventoried with an owning ticket and a "pinned" column marking them not-yet-covered, naming their follow-up task: TASK-36.1 (the 6 hard-coded legacy slash commands plus the 34 interactions), TASK-36.2 (the webhook route), TASK-36.3 (the 5 job entry points).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A checked-in inventory lists every legacy command/action/webhook with its owning module
- [x] #2 Runbook note: how to run the suite pre- and post-cutover for a module
- [x] #3 The checked-in inventory assigns every surface (commands, interactions, webhook and HTTP routes, scheduled jobs) a target feature under app/features/ or capability under app/capabilities/, or marks it for deletion with the reason
- [x] #4 The inventory records, per surface, the rebuild ticket that owns it (TASK-37, TASK-38, TASK-39, TASK-40, TASK-88, TASK-52/TASK-65 for jobs, TASK-53 for app/api/ routes)
- [x] #5 Every register_slack_commands hookimpl under app/modules/ and app/packages/ (the 8 hookimpls: modules/sre, modules/dev, packages/rant, packages/user_rotations, packages/access/sync, packages/incident_draft, packages/incident_summary, packages/geolocate) has a pinning test that dispatches through slack_bolt's public App.dispatch/AsyncApp.async_dispatch boundary and asserts ack, response shape/text and a side-effect fake invoked
- [x] #6 Pinning tests live under app/tests/integration/legacy_surface/ and pass in the normal 'pytest tests --ignore=tests/smoke' run (not under app/tests/smoke/, and not excluded from the PR gate)
- [x] #7 Every inventory row not covered by this task's pinning tests (the 6 hard-coded slash commands and 34 interactions, the webhook route, the 5 job entry points) is marked not-yet-pinned in the inventory and named to its owning follow-up task: TASK-36.1, TASK-36.2 or TASK-36.3 respectively
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Suite green on main
- [ ] #2 PR references decisions/migration.md recipe step 1
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Scope (Slice 1 of TASK-36; follow-ups TASK-36.1/36.2/36.3 now exist)

Full legacy-surface inventory (documentation) + Bolt/ASGI-boundary pinning tests for exactly
the Slack command/listener registration surface TASK-26.1 rewrites: the 8 register_slack_commands
hookimpls. register_slack_listeners(app: AsyncApp) is a declared hookspec with zero hookimpls
today (confirmed 2026-09-28), so the 8 register_slack_commands hookimpls are the *complete*
TASK-26.1 AC#3 surface, not a subset of it. This task depends on TASK-35 (fixes the modules/sre
dev/sre double registration) so its sre pinning test can pin correct, single-registration
behaviour rather than working around a known bug.

Confirmed inventory (codebase-researcher, 2026-09-28):
- 6 slash commands directly in app/modules/: /aws (modules/aws/aws.py:55), /talent-role (modules/role/role.py:37), /secret
  (modules/secret/secret.py:24), /atip + /aiprp (modules/atip/atip.py:39-40), /incident
  (modules/incident/incident.py:38). Owned by TASK-36.1. (/sre is hookimpl-only after TASK-35
  deletes modules/sre/sre.py; it is covered by this task's register_slack_commands row.)
- 34 interactions (18 actions, 12 views, 4 events) across modules/incident/incident.py,
  modules/incident/incident_helper.py (18), modules/sre/webhook_helper.py (6),
  modules/aws/aws.py, modules/role/role.py, modules/secret/secret.py, modules/atip/atip.py —
  all wired inside each module's register(bot) called from
  server/lifespan.py _register_legacy_handlers(). Owned by TASK-36.1.
- 1 webhook route: POST /hook/{webhook_id} (api/v1/routes/webhooks.py:41); already has partial
  coverage at app/tests/api/v1/test_webhooks.py (FastAPI TestClient, mocked bot + DynamoDB
  adapter). Owned by TASK-36.2.
- 5 job entry points calling into app/modules/ or app/packages/: scheduled_tasks.py:101
  (provision_aws_identity_center -> modules.aws.identity_center), :104
  (notify_stale_incident_channels -> modules.incident), :109 (spending job -> modules.aws),
  plus 2 plugin-registered jobs (packages/access/sync/__init__.py:94, packages/oncall_sync/
  __init__.py:34). Owned by TASK-36.3.
- 8 register_slack_commands hookimpls (the complete TASK-26.1 AC#3 surface): modules/sre/
  __init__.py:8, modules/dev/__init__.py:12, packages/rant/__init__.py,
  packages/user_rotations/__init__.py, packages/access/sync/__init__.py,
  packages/incident_draft/__init__.py, packages/incident_summary/__init__.py,
  packages/geolocate/__init__.py — each delegates to a package-local
  platforms/slack.py::register_commands(provider) (access/sync uses interactions/slack.py).
  Owned by this task (TASK-36).
- Existing Slack test infra to reuse: tests/integration/modules/sre/conftest.py
  (SlackPlatformProvider + mock bot/ack/respond fixtures), tests/unit/integrations/slack/
  test_slack_auto_registration.py (SlackPlatformProvider factory), tests/api/v1/
  test_webhooks.py (ASGI TestClient pattern for the webhook row, reusable by TASK-36.2). No
  existing test drives a real Bolt dispatch end-to-end — new in this task.

## Why app/tests/integration/, not app/tests/smoke/ (resolves the task's stale framing)

decisions/testing.md defines "integration" as component-wired tests with external deps stubbed,
<500ms, part of the normal gate; "smoke" as on-demand tests against live backends, never in the
PR gate. This harness uses fakes for every backing service and for the outbound Slack client —
it is an integration test by that definition, not a smoke test. Because TASK-26.1 AC#4 requires
the suite to be "green before and after" as an automatic gate (not an on-demand manual run), and
CLAUDE.md's `pytest tests --ignore=tests/smoke` explicitly excludes app/tests/smoke/, placing
these tests there would silently stop enforcing AC#4. Tests therefore live at
app/tests/integration/legacy_surface/ and run in the standard gate.

## Steps

1. **Inventory** — app/tests/integration/legacy_surface/INVENTORY.md: one table row per surface
   from the confirmed inventory above (46 rows: 6 commands + 34 interactions + 1 webhook route +
   5 job entries), columns: surface, defining file:line, registration mechanism (hard-coded
   register(bot) vs hookimpl), target feature/capability (features/incident, features/role,
   features/secret, features/atip, capabilities/webhooks, features/access... per
   decisions/migration.md's ordering and TASK-97 for incident), owning rebuild ticket (TASK-37,
   TASK-38, TASK-39, TASK-40, TASK-88, TASK-52/TASK-65 for jobs), and a "pinned by" column: this
   task's test name for the 8 hookimpl rows, "TASK-36.1" for the 6 hard-coded commands and 34
   interactions, "TASK-36.2" for the webhook row (noting existing partial coverage at
   tests/api/v1/test_webhooks.py), "TASK-36.3" for the 5 job rows. Satisfies AC#1, AC#3, AC#4.
2. **Runbook section** — same file, a "Running this suite" section: `cd app && uv run pytest
   tests/integration/legacy_surface -v` for a normal run; for a pre/post-cutover check of one
   module, `-k <module-name>` and a one-line note to re-run the full file both immediately before
   and immediately after a surface's cutover PR, per decisions/migration.md's per-surface recipe
   step 4. Satisfies AC#2.
3. **Harness fixtures** — new app/tests/integration/legacy_surface/conftest.py:
   - A fixture building a real, unmodified `slack_bolt.App` (matching production's sync Bolt —
     integrations/slack/provider.py still uses sync `App`, not `AsyncApp`; TASK-33 changes this
     later and only this fixture's construction, not the assertions, will need updating then).
   - A fixture that runs the real pluggy PluginManager registration path for exactly the 8
     hookimpls under test (import the 8 modules, call their `register_slack_commands(provider)`
     hookimpl through the same SlackPlatformProvider used in production, not a fake registrar —
     this is what makes the test assert through the public Bolt boundary rather than the
     hookimpl signature: when TASK-26.1 changes the hookimpl's parameter type, only this
     fixture's construction call changes, never the dispatch/assert code below it).
   - Per-package fakes for backing services reached by each of the 8 commands (e.g. a fake
     AccessSyncCoordinator for packages/access/sync, a fake MaxMind lookup for
     packages/geolocate, a fake transcript store for incident_draft/incident_summary), wired via
     each package's existing provider/dependency-override seam — no new production code.
   - A fake outbound Slack client/`respond`/`say` capturing calls for assertion, per
     decisions/testing.md's Protocol-fake-first preference.
4. **Pinning tests** — app/tests/integration/legacy_surface/test_slack_command_registration_surface.py,
   one parametrized case per hookimpl (8 cases): build a `slack_bolt.BoltRequest` with the
   command's real slash-command form-encoded body, call `app.dispatch(req)` (the public,
   documented Bolt API — confirmed present at slack_bolt/app/app.py:540), and assert: a) the
   command is registered under its documented name exactly once (including the sre/dev
   COMMAND_PREFIX behaviour per decisions/transport-slack.md), b) `dispatch()` returns an ack
   (BoltResponse status 200 / ok=True) within the same call, c) the response text/shape matches
   the module's current behaviour, d) the per-package fake side-effect was invoked exactly once
   with the expected arguments. For modules/sre specifically, since TASK-35 has already fixed the
   double registration, assert the correct, single-registration behaviour directly (one ack, one
   response, one side-effect call per dispatch) — do not construct a case around the old bug.
   modules/dev is pinned with a minimal "registers and acks" case (dev-only, no production
   traffic, no response-shape assertion needed). Satisfies AC#5, AC#6.
5. **Mark deferred rows** — in INVENTORY.md, tag the 6 hard-coded commands + 34 interactions as
   owned by TASK-36.1, the webhook row as owned by TASK-36.2 (crediting its existing partial
   coverage), and the 5 job rows as owned by TASK-36.3, each explicitly out of scope for this PR.
   Satisfies AC#7.
6. No production code changes. Run `cd app && uv run ruff check .`, `uv run mypy . --exclude
   '(?:^|/)\.venv(?:/|$)'` (0 new errors in the touched test files), and `uv run pytest tests
   --ignore=tests/smoke` (new tests included and green, no regressions elsewhere).

## AC traceability

- AC#1 (checked-in inventory, every surface) -> step 1, INVENTORY.md.
- AC#2 (runbook note) -> step 2.
- AC#3 (target feature/capability per surface) -> step 1.
- AC#4 (owning rebuild ticket per surface) -> step 1.
- AC#5 (pinning test per register_slack_commands hookimpl) -> steps 3-4.
- AC#6 (tests live in integration/, run in normal gate) -> steps 3-4, verified by step 6's
  `pytest tests --ignore=tests/smoke` run actually collecting and passing them.
- AC#7 (deferred rows named to TASK-36.1/36.2/36.3) -> step 5.
- DoD#1 (suite green on main) -> step 6.
- DoD#2 (PR references decisions/migration.md recipe step 1) -> PR description, human step.

## Test matrix (the 8 pinning tests, one per hookimpl)

| Hookimpl | Happy path | Boundary | Failure |
| --- | --- | --- | --- |
| modules/sre | /sre <subcommand> acks + responds exactly once (post-TASK-35 single-registration) | prefix applied in dev env | n/a |
| modules/dev | dev command registers and acks | only active behind its own registration | n/a (dev-only, minimal case) |
| packages/rant | /rant acks + posts uppercase message | empty message text | n/a |
| packages/user_rotations | rotation command acks + reads current assignment | no active rotation configured | fake store raises -> OperationResult error mapped to response |
| packages/access/sync | sync command acks + triggers fake coordinator | already-in-progress sync | fake coordinator raises -> error response |
| packages/incident_draft | draft subcommand acks + calls fake draft service | empty transcript | fake service raises -> error response |
| packages/incident_summary | summarize subcommand acks + calls fake summarizer | empty transcript | fake service raises -> error response |
| packages/geolocate | geolocate command acks + calls fake MaxMind lookup | invalid IP argument | fake lookup raises -> error response |

## Assumptions / doubts (verify during implementation)

- Assumes TASK-35 has merged and modules/sre registers through exactly one path (hookimpl or
  hard-coded list, not both) before this task's sre test is written; if TASK-35 lands with a
  different fix shape than expected, adjust the sre fixture accordingly, but the test still
  asserts single, correct registration.
- Assumes `slack_bolt.App.dispatch(BoltRequest)` is safely callable without an active
  SocketMode/HTTP connection (confirmed importable and present at app.py:540; verify no hidden
  requirement on `app.start()` having run first).
- Assumes each of the 8 packages' `platforms/slack.py::register_commands(provider)` can be
  invoked in isolation against a fresh `SlackPlatformProvider`/`App` without needing the full
  lifespan (other hookimpls, i18n registry, etc.) — verify per package; if one needs more startup
  state, wire the minimum via existing fixtures rather than booting the full app.
- Assumes command names/response text asserted are today's actual behaviour (not the tickets'
  future intent) — read each package's platforms/slack.py to confirm exact strings before writing
  assertions, since the test's job is to pin what exists, not what TASK-37..40 will produce.
- Assumes no app/api/ route besides the webhook route is legacy-module-owned (researcher found
  none); if a review surfaces one, add it to the inventory as a documentation-only addition
  under TASK-36.2/36.3 scope as appropriate, not a new pinned test in this PR.

## Blast radius and rollback

Test-only change (INVENTORY.md, conftest.py, one test file); no production code touched. A
`git revert` fully restores prior state with no runtime impact. Risk is confined to CI signal:
if a fixture is flaky, only this suite's tests fail, not other suites. TASK-26.1 must not merge
until this task's suite is green on main, per its AC#4. This task must not merge until TASK-35
is merged, per its new dependency.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added app/tests/integration/legacy_surface/ (__init__.py, conftest.py, INVENTORY.md, test_slack_command_registration_surface.py). No production code changed.

Harness: registers the 8 register_slack_commands hookimpls through a fresh pluggy PluginManager (FeatureLifecycleSpecs) onto a real SlackPlatformProvider bound to a real slack_bolt App, then drives form-encoded slash commands through App.dispatch(BoltRequest). Fakes only at the edges: a recording Web API client on the provider, WebhookClient.send_dict (where Bolt's respond posts to response_url), and each package's service seam via monkeypatch. Bolt runs with a static authorize function (no auth.test) and an inline listener executor so the production ack-then-run ordering is kept but side effects are observable when dispatch returns.

Findings:
- tests/conftest.py pytest_configure replaces slack_bolt.App.__init__ session-wide with a stub that registers nothing. The harness restores the library's own __init__ (loaded from a private copy of slack_bolt.app.app) for its fixture only, via monkeypatch. The shared stub was left untouched (out of scope); it is a candidate for removal once nothing constructs App at import time.
- Interaction count was 34 (18 actions, 12 views, 4 events), not 31: incident_helper.register has 18 registrations, not 14. TASK-36 and TASK-36.1 counts corrected; inventory has 46 legacy rows.
- The inventory also lists the other app/api/ routes (GET /geolocate/{ip}, /version, /health, /) for TASK-53, marked as covered by their existing route tests.

Deviation from plan: 17 named tests grouped per hookimpl instead of one parametrized case each, so each surface keeps its happy path plus boundary/failure cases; INVENTORY.md "Pinned by" gives the -k keyword selecting each surface's tests (verified each keyword selects only that surface). modules/dev is pinned with the plan's minimal registers-and-acks case (no side-effect fake), and /sre version is exercised by the prefix test.

Gates: ruff check clean, ruff format applied; mypy 69 errors repo-wide, 0 in touched files (tests/ is outside mypy's configured scope); pytest tests --ignore=tests/smoke 3494 passed, 6 failed (known TASK-90 order leaks, unchanged); make test 2740 + 760 passed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-28 14:35
---
2026-09-28: depends on TASK-35 so the harness pins correct single-registration behaviour for modules/sre instead of asserting the double-registration bug. Uncovered inventory rows are owned by TASK-36.1 (hard-coded commands and interactions), TASK-36.2 (webhook route) and TASK-36.3 (jobs).
---

created: 2026-09-28 14:55
---
2026-09-28: implementation plan approved by human (Guillaume Charest) for the doc-2 Stack A / Wave 0 realignment.
---
<!-- COMMENTS:END -->
