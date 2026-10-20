---
id: TASK-111.1
title: >-
  Record the configuration decisions and the production inventory; three
  environments, ENVIRONMENT required
status: To Do
assignee: []
created_date: '2026-10-20 23:25'
updated_date: '2026-10-20 23:35'
labels:
  - configuration
milestone: m-7
dependencies: []
references:
  - decisions/configuration.md
  - decisions/plugin-architecture.md
  - 'https://github.com/cds-snc/sre-bot/issues/1742'
parent_task_id: TASK-111
type: feature
ordinal: 407000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
First slice of TASK-111. Commit 1 amends decisions/configuration.md (casing, environments, loading order, platform-provided values and external namespaces, rename protocol, SSM SecureString per secret via task-definition secrets:, extra=forbid and unowned tables, migration scope, tolerated list) and decisions/plugin-architecture.md (contracts/ may import pydantic-settings for the settings-slice base; loader implementation in server/configuration/), and adds the production inventory as a backlog doc (keys only, no values). Commit 2 narrows ENVIRONMENT to local, ci and production with no default, moves the legacy 'dev' checks to 'local', sets the devcontainer to local and the pytest env to ci, and adds set -eu to app/bin/entry.sh.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 decisions/configuration.md records the 2026-10-20 TASK-111 planning decisions: lower snake_case fields and TOML keys with upper-case <SLICE>__<FIELD> env names and case_sensitive=False (replacing the earlier casing rule); ENVIRONMENT in {local, ci, production}, required, one file per value; identity-first load order with deep-merged base and environment files; the closed list of platform-provided names and the exempt SDK namespaces (AWS_*, UVICORN_*, OTEL_*); the rename protocol (new names published beside old ones, no compatibility code, old ones removed once the deploy is verified); secrets as one SSM SecureString per key through task-definition secrets:; extra=forbid per migrated slice and no unowned table; TASK-111 moves every value production sets; the tolerated list updated
- [ ] #2 decisions/plugin-architecture.md lets contracts/ import pydantic-settings for the settings-slice base and names server/configuration/ as the loader implementation home
- [ ] #3 A backlog doc lists every key of the sre-bot-config and sre-bot-config-infrastructure SSM parameters and the terraform task-definition env and secrets, by key with no values, each mapped to its owning slice and to a file table, a renamed secret, a platform-provided name or deletion; it records that production sets AWS_ORG_ACCOUNT_ROLE_ARN and ISSUER_CONFIG and does not set ACCESS_SYNC_ENABLED or DIRECTORY_REQUIRE_STARTUP_WARMUP
- [ ] #4 ENVIRONMENT accepts only local, ci and production and has no default; boot without it fails naming ENVIRONMENT
- [ ] #5 Code that checked ENVIRONMENT == 'dev' checks 'local'; the devcontainer sets ENVIRONMENT=local; the pytest env and the CI workflow set ENVIRONMENT=ci
- [ ] #6 app/bin/entry.sh stops on the first failing command (set -eu), so a failed SSM read no longer starts the app with a partial .env
- [ ] #7 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Branch: task-111.1-configuration-decisions from an up-to-date main. Two commits, one PR.

Commit 1 — decisions and inventory (docs only)
1. decisions/configuration.md, amended in place (Decision, Checks, Current code, Tolerated, Changes 2026-10-20), citing the sources found in planning (pydantic-settings releases and settings docs, ASP.NET Core configuration, Spring Boot external config, Backstage app-config, AWS ECS secrets and circuit breaker, AWS SDK endpoint settings, uvicorn settings):
   a. Casing: fields and TOML keys lower snake_case; env names upper case <SLICE>__<FIELD>; case_sensitive=False; ownership compared case-insensitively (replaces the 2026-10-20 case-sensitive rule; the reason: case_sensitive=True forces upper-case fields and keys). Requires pydantic-settings >= 2.15 (toml_table_header).
   b. Environments: ENVIRONMENT in {local, ci, production}, required, no default; files app/config/base.toml + one per value; adding an environment = one Literal value + one file.
   c. Loading: an env-only identity slice (ENVIRONMENT, GIT_SHA) selects the files; base and environment file deep-merged; each slice reads its own table; priority init > env > .env > files > defaults; a missing file fails boot.
   d. Platform-provided names (closed list): ENVIRONMENT, GIT_SHA, FORWARDED_ALLOW_IPS. External namespaces AWS_*, UVICORN_*, OTEL_* are left to their SDK or runtime and never declared as fields. "Deployment identity" is replaced by this list.
   e. Rename protocol: new names published on the deployment side beside the old ones; no aliases or compatibility code; old names removed once the deploy is verified (ECS circuit-breaker rollback restores the previous task definition, which still reads the old names).
   f. Secrets: task-definition secrets:, one SSM SecureString per key, created by terraform with values set outside it (ignore_changes), so values stay out of state; the entry.sh SSM fetch is retired by TASK-111 (absorbs TASK-54).
   g. Unknown keys: every migrated slice sets extra=forbid; CI fails on a table no slice owns.
   h. Migration: values ride with a package move where one is scheduled; TASK-111 moves every value production sets, feature values included, under the current class's table (table names do not depend on module paths).
   i. Tolerated list: GOOGLE_RESOURCES becomes the interim [google_resources] table until TASK-158; feature slices in infrastructure/configuration/features/ until TASK-159; tenant entry line rewritten (TASK-111.9 and 111.10 move them into the files; TASK-112 keeps the Slack transport key); the SSM-parameter line ends with TASK-111.15. The comment-#2 conflict (AliasChoices vs no per-field alias) is resolved by 1e.
2. decisions/plugin-architecture.md: the contracts/ row may import pydantic-settings for the settings-slice base and the file-list Protocol; server/configuration/ implements the loader. Changes entry 2026-10-20.
3. backlog doc create "TASK-111 production configuration inventory": one table row per key of sre-bot-config, sre-bot-config-infrastructure and the task definition (keys from TASK-111's 2026-10-20 notes, no values): owning slice (file:line) or "no reader", destination (file table and key / renamed secret <SLICE>__<FIELD> / platform-provided / delete), carrying subtask. Records the AC6 facts. This is the rename map TASK-111.4 reads.

Commit 2 — environment set and entry.sh
4. app/infrastructure/configuration/app.py: ENVIRONMENT: Literal["local", "ci", "production"] with no default (required).
5. app/modules/incident/core.py:426: environment = "prod" if ENVIRONMENT == "production" else "dev" (same rule as :300; today a local run named "local" would label channels prod).
6. app/modules/dev/platforms/slack.py:7,40: the dev commands register only when ENVIRONMENT == "local".
7. .devcontainer/docker-compose.yml:30: ENVIRONMENT 'local'. app/pyproject.toml [tool.pytest.ini_options] env: add ENVIRONMENT=ci (ci_code.yml:78 already sets ci). .env.example: ENVIRONMENT=local if it names one (unread in planning; check).
8. app/bin/entry.sh: set -eu after the shebang, so a failed SSM read stops the container (ECS then rolls back) instead of starting uvicorn with a partial .env.

AC → step → test
- AC1 (ADR casing … tolerated) → 1 → review; markdown only.
- AC2 (plugin-architecture) → 2 → review.
- AC3 (inventory doc) → 3 → review against TASK-111 notes; every key appears once.
- AC4 (ENVIRONMENT values, required) → 4 → tests/unit/infrastructure/configuration/test_app_settings.py: test_environment_default_is_local becomes test_environment_missing_fails_naming_it; the parametrized accepted values become local, ci, production; dev and staging rejected.
- AC5 (dev checks, devcontainer, pytest/CI env) → 5, 6, 7 → tests/modules/incident/test_incident_core.py (new case: local creates a dev-labelled channel, production a prod one); tests/modules/slack/test_dev_platforms_slack_contract.py (local registers, ci and production do not); tests/unit/modules/atip/test_atip_command_registration.py:43 and the two value-set asserts (test_app_state_initialization.py:53, test_settings_structure.py:79) updated to the three values.
- AC6 (entry.sh) → 8 → new tests/unit/bin/test_bin_entry_script_failure.py: runs entry.sh in a temp dir with a PATH stub aws that exits 1 and a stub uvicorn that writes a marker; asserts a non-zero exit and no marker. A second case with a succeeding stub asserts uvicorn is exec'd with the .env written.
- AC7 (gates) → all → ruff, mypy on touched files, pytest tests --ignore=tests/smoke.

Test matrix
- Happy: each of local, ci, production accepted; entry.sh with both SSM reads succeeding starts uvicorn.
- Boundary: ENVIRONMENT set to the empty string rejected; the dev command gate under ci (not registered).
- Failure: ENVIRONMENT missing fails naming ENVIRONMENT; dev and staging rejected; first SSM read failing stops entry.sh before uvicorn.

Assumptions and doubts
- No code branches on "staging" or "dev" beyond steps 5 and 6 (rg in planning found only these, plus docstrings); re-run rg before the commit.
- Production sets ENVIRONMENT=production in the task definition (sre-bot.json.tpl:58) and in the blob, so required-with-no-default cannot fail there; the blob value is overridden by the real env.
- A developer .env with ENVIRONMENT=dev is overridden by docker-compose's real env var (env beats .env); a bare uvicorn run outside the devcontainer needs ENVIRONMENT=local — say so in the PR description.
- set -eu with /bin/sh: the image shell is dash or busybox sh; both support it. Verify with the image's sh in CI (ci_container.yml build) or sh -n locally.
- bin scripts that build settings (dev-token.py and others) run inside the devcontainer, which sets ENVIRONMENT.

Blast radius and rollback
- A production boot needs ENVIRONMENT, which terraform sets; worst case a typo'd ENVIRONMENT fails boot and the circuit breaker rolls back to the previous revision. entry.sh now stops on a failed SSM read, which is the intended change; previously the app started half-configured. One git revert restores both. No terraform, SSM or data change.
<!-- SECTION:PLAN:END -->
