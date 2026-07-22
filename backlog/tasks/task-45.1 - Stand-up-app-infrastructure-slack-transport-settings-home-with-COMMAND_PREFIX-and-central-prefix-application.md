---
id: TASK-45.1
title: >-
  Stand up app/infrastructure/slack transport settings home with COMMAND_PREFIX
  and central prefix application
status: Done
assignee:
  - '@me'
created_date: '2026-07-21 19:13'
updated_date: '2026-07-22 16:43'
labels:
  - phase-0
  - slack
milestone: m-0
dependencies:
  - TASK-1.3
references:
  - decisions/transport-slack.md
  - decisions/configuration.md
  - decisions/platform-transports.md
parent_task_id: TASK-45
priority: high
ordinal: 52000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Foundational slice (no frozen-module edits yet). Create the Slack transport settings home app/infrastructure/slack/settings.py with a SlackTransportSettings BaseSettings exposing COMMAND_PREFIX: str = '' (env SLACK__COMMAND_PREFIX) and a cached get_slack_transport_settings() provider, consumed directly by the Slack provider factory. Do NOT wire this into the legacy app/infrastructure/configuration/settings.py aggregator: an open PR removes that global settings aggregator, and open/future tasks should avoid depending on it. Apply COMMAND_PREFIX centrally for hookspec-registered commands at registration/compose time (infrastructure/plugins manager register_slack_commands path) so migrated/new commands get the prefix in one place. Set SLACK__COMMAND_PREFIX in terraform/, CI (ci_code.yml env), and the app/Makefile dev/debug targets to the SAME value as PREFIX per environment (dev- in dev, '' in prod) for coexistence. No app/modules/** file changes in this slice.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 app/infrastructure/slack/settings.py defines SlackTransportSettings with COMMAND_PREFIX (env SLACK__COMMAND_PREFIX, default '') and a cached get_slack_transport_settings() provider; invalid config fails boot with a pydantic error
- [x] #2 The transport applies COMMAND_PREFIX once, centrally, to hookspec-registered Slack commands at registration; a unit test asserts a base command name 'sre' registers as '<COMMAND_PREFIX>sre'
- [x] #3 SLACK__COMMAND_PREFIX is set in terraform/ task definition, .github/workflows/ci_code.yml, and local compose/.env examples, matching PREFIX per environment
- [x] #4 No file under app/modules/ is modified in this slice; AppSettings.PREFIX still exists and is untouched
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Verified anchors (2026-07-22, re-verified against current code; updated same day to drop legacy-aggregator wiring per architecture note — see task comments):

- app/infrastructure/slack/ does NOT exist yet (list_dir confirms ENOENT) — this slice creates it as the transport settings home, per decisions/transport-slack.md ("Home... app/infrastructure/slack/... COMMAND_PREFIX field on the Slack transport settings").
- Two existing Slack settings classes are vendor/credential homes with FLAT env aliases (no env_nested_delimiter precedent anywhere in the repo: checked infrastructure/configuration/base.py, infrastructure/configuration/settings.py, integrations/slack/settings.py): app/integrations/slack/settings.py::SlackSettings (target home, used at runtime by provider.py:31) and the legacy twin app/infrastructure/configuration/integrations/slack.py::SlackSettings (retiring under TASK-24). COMMAND_PREFIX is a NEW, separate transport-presentation field and does not belong in either.
- CORRECTED central registration point (the 07-21 draft pointed at register_command():658, flagged as an unverified "doubt" — now resolved): the Bolt slash-command string is built in SlackPlatformProvider._auto_register_root_commands() at app/integrations/slack/provider.py:392-461, specifically `slash_command = f"/{root_command}"` at provider.py:424, then `self._app.command(slash_command)(create_handler(root_command))` at provider.py:456. register_command() (provider.py:658) only stores base command names into self._commands; it never builds the Bolt slash string. _auto_register_root_commands() is called once, centrally, from initialize_app() at provider.py:186 — which itself runs from app/server/lifespan.py:265, AFTER register_feature_integrations() (lifespan.py:258) has fired the register_slack_commands hookspec (app/infrastructure/plugins/manager.py:89) and populated self._commands. This confirms one central, post-registration point — exactly what AC #2 needs.
- Provider construction/injection point: SlackPlatformProvider.__init__ (provider.py:72-91) currently takes settings/formatter/name/enabled/version/translation_service only. The assembly point is get_slack_provider() (provider.py:942-955), a @cache factory that builds `SlackPlatformProvider(settings=get_slack_settings(), formatter=...)`. Per the settings-singleton skill ("providers inject narrow settings slices... keep providers in assembly layers, not service constructors"), get_slack_provider() is the right place to also call the new get_slack_transport_settings() and pass COMMAND_PREFIX in — not have the provider reach into infrastructure.configuration itself.
- ARCHITECTURE NOTE (2026-07-22, supersedes the prior "Step 2 — Aggregator wiring"): an open, unmerged PR removes the global settings aggregator (app/infrastructure/configuration/settings.py's Settings class, its settings_map, and get_settings()). Per that direction and the settings-singleton skill ("avoid growing root settings aggregators for new package-owned concerns"), this task and all other open/future tasks must NOT wire new settings into that aggregator, whether or not the removal PR has merged yet. get_slack_transport_settings() is therefore a standalone singleton provider, consumed ONLY by get_slack_provider() (Step 3) — no aggregator field, no settings_map entry. Original plan's "Step 2" is dropped entirely.
- CORRECTED local-dev anchor (the 07-21 draft said "local compose/.env examples", which does not exist — there is no .env.example in the repo, and .devcontainer/docker-compose.yml sets ENVIRONMENT=dev but never sets PREFIX): the ONLY place PREFIX is actually set to "dev-" today is app/Makefile's `dev` and `debug` targets (`PREFIX="dev-" uv run uvicorn main:server_app --reload`, app/Makefile:3-4 and :11-12) — confirmed by user, and reconfirmed on plan review as the deliberate target anchor (a broader non-secret configuration strategy, e.g. .env.example/compose env, is explicitly deferred to later, separately-evaluated work — not in scope here).
- Terraform anchor confirmed: the ECS container environment array lives in terraform/templates/sre-bot.json.tpl:42-49 (rendered by terraform/ecs.tf:33 via `data.template_file.sre-bot.rendered`), currently only "BACKEND_URL" and "ENVIRONMENT"="production" — PREFIX is NOT set there (defaults to "" via AppSettings). There is also no dev/staging Terraform environment or deploy workflow in this repo (build_and_deploy.yml:100 only deploys "environment": "production"; .github/workflows/ci_code.yml:44-58 only sets ENVIRONMENT: ci for tests). So "matching PREFIX per environment" in terraform/CI reduces to: both PREFIX and the new SLACK__COMMAND_PREFIX are simply absent/"" in prod and CI manifests (no literal value to mirror there); the only environment with a real non-default value is local dev via the Makefile.
- decisions/transport-slack.md confirms the target shape: `COMMAND_PREFIX: str = ""` field, transport-owned, applied "once, centrally, at registration/compose time"; default "" (prod), "dev-" for dev instances; during coexistence PREFIX and SLACK__COMMAND_PREFIX must carry the SAME value per environment.
- decisions/configuration.md confirms: "Transport settings -> app/infrastructure/<platform>/settings.py", "One env var has exactly one owning class. Namespaced env names (SLACK__..., AWS__...) via env_nested_delimiter" (aspirational repo-wide convention; no existing slice actually uses env_nested_delimiter yet). Plan review confirmed: use an explicit Field alias for this single scalar field, consistent with the two existing flat-alias Slack settings classes; do not force env_nested_delimiter as a one-off in this slice.
- Existing test anchors to extend (not create new suites where an obvious extension point exists): app/tests/unit/integrations/slack/test_slack_auto_registration.py (already tests _auto_register_root_commands() with a make_slack_settings factory + FakeApp — the natural home for the dev-/'' slash-command-prefix assertions), app/tests/unit/infrastructure/configuration/test_infra_settings_singletons.py (pattern for singleton/model_config/env-read tests to mirror for the new slice — NOT the aggregator-wiring tests, which are no longer applicable).

Step 1 — Settings home (AC #1). Create app/infrastructure/slack/__init__.py (empty/minimal, no side-effecting registration code per plugin rules) and app/infrastructure/slack/settings.py: `class SlackTransportSettings(BaseSettings)` with `model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")` and `COMMAND_PREFIX: str = Field(default="", alias="SLACK__COMMAND_PREFIX")` (explicit alias, matching the flat-alias convention already used by integrations/slack/settings.py::SlackSettings — do not introduce env_nested_delimiter as a one-off; confirmed on plan review). Add `@lru_cache(maxsize=1) def get_slack_transport_settings() -> SlackTransportSettings`. This is a fully standalone settings slice — it is NOT added to app/infrastructure/configuration/settings.py's aggregator (see architecture note above). New test file app/tests/unit/infrastructure/slack/test_slack_transport_settings.py mirroring test_infra_settings_singletons.py's structure: default "", env override via monkeypatch.setenv("SLACK__COMMAND_PREFIX", "dev-"), singleton identity, model_config assertions.

Step 2 — Central prefix application (AC #2; renumbered from "Step 3" in the prior draft now that aggregator wiring is dropped). (a) Add `command_prefix: str = ""` parameter to SlackPlatformProvider.__init__ (provider.py:72), store as `self._command_prefix = command_prefix`. (b) In _auto_register_root_commands (provider.py:424), change `slash_command = f"/{root_command}"` to `slash_command = f"/{self._command_prefix}{root_command}"` — this is the single, central, post-hookspec-registration point; handlers/features keep declaring base names via register_command(command="sre", ...). (c) In get_slack_provider() (provider.py:942), call `transport_settings = get_slack_transport_settings()` (new import from infrastructure.slack.settings) and pass `command_prefix=transport_settings.COMMAND_PREFIX` into the SlackPlatformProvider constructor — this is the assembly-layer injection point per the settings-singleton skill, keeping the provider itself free of a direct infrastructure.configuration/infrastructure.slack settings read inside business logic, and is now the ONLY consumer of get_slack_transport_settings() (no aggregator involved). Guard: only the auto-registered root-command slash string changes; register_command()'s internal self._commands keys (used for help/dot-path routing, e.g. "sre.incident") are NOT prefixed, and help text generated by SlackHelpGenerator is intentionally left un-prefixed in this slice (confirmed on plan review — command-namespace configurability + prefix-aware help text is deferred until all legacy app/modules/ packages have migrated off AppSettings.PREFIX; not needed now and explicitly out of scope for TASK-45.1). Extend app/tests/unit/integrations/slack/test_slack_auto_registration.py: construct the provider with command_prefix="dev-" and assert `self._app.command` was invoked with "/dev-sre" (or equivalent captured via the existing FakeApp.command mock) for a registered base command "sre"; a second case with command_prefix="" (default) asserts "/sre" (unchanged behavior — regression guard for existing callers that don't pass the new kwarg).

Step 3 — Manifests (AC #3; renumbered from "Step 4"). Add SLACK__COMMAND_PREFIX in three places, each matching the value PREFIX effectively carries in that same context (verified above — PREFIX is default "" everywhere except the local Makefile):
  - terraform/templates/sre-bot.json.tpl:42-49 environment array: add `{"name": "SLACK__COMMAND_PREFIX", "value": ""}` alongside the existing ENVIRONMENT entry (prod default, matching PREFIX's absent/"" value there).
  - .github/workflows/ci_code.yml test-step env block (currently lines ~44-58, `ENVIRONMENT: ci`): add `SLACK__COMMAND_PREFIX: ""` (matching PREFIX, which is likewise unset/"" for CI/tests).
  - app/Makefile `dev` (line 3-4) and `debug` (line 11-12) targets: add `SLACK__COMMAND_PREFIX="dev-"` alongside the existing `PREFIX="dev-"` in the same command line, e.g. `PREFIX="dev-" SLACK__COMMAND_PREFIX="dev-" uv run uvicorn main:server_app --reload` — this is the actual, currently-real "dev-" coexistence value and the confirmed target anchor for local config (not docker-compose or .env.example — those remain out of scope per plan review, pending a later non-secret configuration strategy). Verify with `grep -n 'PREFIX=\"dev-\"' app/Makefile` post-edit shows both vars on each of the two targets.

Step 4 — Freeze respected (AC #4; renumbered from "Step 5"). No app/modules/** file is edited in this slice; AppSettings.PREFIX (app/infrastructure/configuration/app.py) is untouched — still default "", read only by the frozen module command-registration files. TASK-1.3's guardrail baseline/whitelist is unchanged (no reader removed or added outside app/modules/).

Test matrix:
  AC#1 -> Step 1: app/tests/unit/infrastructure/slack/test_slack_transport_settings.py (new) — default "", env override, singleton identity, model_config (env_file/extra). No aggregator-wiring test (dropped).
  AC#2 -> Step 2: app/tests/unit/integrations/slack/test_slack_auto_registration.py extended with dev-/'' prefixed-slash-command cases; optionally a get_slack_provider() assembly test (new or extended app/tests/unit/integrations/slack/test_slack_provider.py) asserting the factory reads get_slack_transport_settings().COMMAND_PREFIX and threads it through.
  AC#3 -> Step 3: grep/manifest presence checks for SLACK__COMMAND_PREFIX in the three files above (can be a simple assertion in an existing terraform/CI lint step, or a manual review checklist item — no automated test framework currently covers terraform templates or Makefile targets in this repo).
  AC#4 -> Step 4: existing TASK-1.3 guardrail test/script (bin/check_prefix_command_namespace.py via `make check-prefix-guardrail`) still passes unchanged; `git diff --stat` (reviewer-side, not agent-run) shows no app/modules/ path touched.

Assumptions/doubts (decided on plan review 2026-07-22, see task comments for full rationale):
  (a) RESOLVED — help text stays as-is for this slice; SlackHelpGenerator output is NOT prefixed. Command-namespace configurability + flexible/prefix-aware help text is deferred until all legacy app/modules/ packages have cut over to COMMAND_PREFIX; explicitly out of scope for TASK-45.1.
  (b) STILL OPEN — verify during implementation that no other code path builds a Bolt slash command outside _auto_register_root_commands (e.g. any remaining `@bot.command(...)` literal in integrations/slack/bootstrap.py or provider.py) that would need the same prefix and currently isn't centralized — a quick grep for `.command(\"/` / `.command('/'` beyond provider.py:456 before finishing Step 2.
  (c) RESOLVED — use an explicit Field(alias="SLACK__COMMAND_PREFIX"), matching existing precedent; env_nested_delimiter is not adopted as a one-off in this slice.
  (d) RESOLVED (2026-07-22) — do not wire get_slack_transport_settings() into app/infrastructure/configuration/settings.py's aggregator; an open PR removes that aggregator, and this and all future tasks must not add new dependencies on it. Before starting implementation, re-check whether that PR has merged (aggregator file may already be gone) — if merged, nothing changes for this task since Step 1 never depended on it; if not yet merged, still do not touch/extend it.

Blast radius: two new files (app/infrastructure/slack/__init__.py, settings.py, ~30-40 LOC), one provider.py edit (constructor param + one f-string + factory injection, ~10-15 LOC), three manifest edits (terraform template, ci_code.yml, app/Makefile, ~6 LOC total), plus new/extended unit tests. No edit to app/infrastructure/configuration/settings.py at all (dropped). Single subsystem (Slack transport settings + central registration), no frozen-module edit, no PREFIX deletion, no cross-cutting refactor, no dependency on the legacy aggregator — fits comfortably within the single-PR size gate (well under ~400 production LOC / ~10 files / one subsystem; smaller than the original draft now that aggregator wiring is dropped). Rollback: revert the PR; COMMAND_PREFIX defaults to "" everywhere it isn't explicitly set to "dev-" (app/Makefile only), so behavior is byte-identical to today until a module actually cuts over to reading COMMAND_PREFIX (later TASK-45.x slices).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented TASK-45.1 Slack transport command-prefix slice.

What changed:
- Added app/infrastructure/slack/__init__.py and app/infrastructure/slack/settings.py with SlackTransportSettings and cached get_slack_transport_settings(); COMMAND_PREFIX is owned by env alias SLACK__COMMAND_PREFIX with default ''.
- Updated app/integrations/slack/provider.py to accept command_prefix in SlackPlatformProvider constructor, apply prefix centrally in _auto_register_root_commands(), and inject transport settings from get_slack_transport_settings() in get_slack_provider().
- Added SLACK__COMMAND_PREFIX in terraform/templates/sre-bot.json.tpl, .github/workflows/ci_code.yml, and app/Makefile dev/debug targets (matching PREFIX behavior per environment).
- No app/modules/** files were edited; AppSettings.PREFIX remains untouched.

Verification evidence:
- Targeted behavior tests: uv run pytest tests/unit/infrastructure/slack/test_slack_transport_settings.py tests/unit/integrations/slack/test_slack_auto_registration.py tests/unit/integrations/slack/test_slack_provider.py -q -> 33 passed.
- Prefix guardrail: cd app && make check-prefix-guardrail -> clean tree.
- Manifest presence: grep confirms SLACK__COMMAND_PREFIX in CI workflow, terraform task template, and Makefile dev/debug targets.
- Formatting: cd app && uv run black --check . -> pass.
- Fast lint on changed files: cd app && uv run ruff check <changed files> -> pass.

DoD left for human verification:
- PR description references decisions/transport-slack.md and decisions/configuration.md.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-07-22 14:27
---
Plan review decisions (2026-07-22): (1) Help text stays as-is for this slice — SlackHelpGenerator output is NOT prefixed. Command-namespace configurability + flexible/prefix-aware help text generation is deferred until all legacy app/modules/ packages have cut over to COMMAND_PREFIX (out of scope here, no follow-up ticket created yet). (2) app/Makefile's dev/debug targets remain the target anchor for local PREFIX/SLACK__COMMAND_PREFIX; a broader non-secret configuration strategy (e.g. .env.example, docker-compose env, etc.) is deferred to a later, separately-evaluated piece of work.
---

author: @task-planner
created: 2026-07-22 14:32
---
Architecture note (2026-07-22): an open, unmerged PR removes the global settings aggregator (app/infrastructure/configuration/settings.py Settings/get_settings() + its settings_map). Per that direction and the settings-singleton skill ('avoid growing root settings aggregators for new package-owned concerns'), this task and all other open/future tasks must NOT wire new settings into that aggregator. Plan's Step 2 (aggregator wiring) is dropped; get_slack_transport_settings() is consumed directly by get_slack_provider() only.
---

author: @copilot
created: 2026-07-22 14:56
---
Alignment review (2026-07-22): direction confirmed against decisions/transport-slack.md + platform-transports.md. Two notes for reviewers: (1) The new settings home app/infrastructure/slack/settings.py is target-correct. But Step 2 adds transport logic (command_prefix param, _auto_register_root_commands prefixing, get_slack_provider() importing infrastructure.slack.settings) into app/integrations/slack/provider.py, which is the transport runtime still awaiting relocation under TASK-26. This upward integrations->infrastructure.slack import is a deliberate, tolerated interim coupling (provider already imports infrastructure.i18n/operations/configuration); TASK-26 now carries a cross-ref to move this logic+tests. (2) Test hygiene: new/edited tests must NOT import infrastructure.configuration.infrastructure.platforms.SlackPlatformSettings (the third dead settings duplicate slated for deletion per transport-slack.md/TASK-24). Fixed test_slack_auto_registration.py's make_slack_settings factory to use a lightweight attribute stub (SimpleNamespace), matching the sibling MockSlackSettings pattern.
---
<!-- COMMENTS:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 PR references decisions/transport-slack.md and decisions/configuration.md
<!-- DOD:END -->
