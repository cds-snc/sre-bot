---
id: TASK-25.2.4.7
title: >-
  Delete the seven legacy AWS mirror modules and their tests; prune both guard
  baselines
status: In Progress
assignee: []
created_date: '2026-09-14 17:39'
updated_date: '2026-09-15 18:40'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.4.3
  - TASK-25.2.4.4
  - TASK-25.2.4.5
  - TASK-25.2.4.6
references:
  - app/integrations/aws/organizations.py
  - app/integrations/aws/sso_admin.py
  - app/integrations/aws/config.py
  - app/integrations/aws/cost_explorer.py
  - app/integrations/aws/guard_duty.py
  - app/integrations/aws/security_hub.py
  - app/integrations/aws/lambdas.py
  - app/bin/baselines/vendor_package_contract.txt
  - app/bin/baselines/sdk_typing_antipatterns.txt
  - app/locales/dev.en-US.yml
  - app/locales/dev.fr-FR.yml
  - app/modules/dev/platforms/slack.py
  - app/modules/dev/__init__.py
  - app/bin/check_sdk_typing.py
  - app/bin/check_vendor_package_contract.py
parent_task_id: TASK-25.2.4
priority: high
ordinal: 206000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 7 (contract, final) of TASK-25.2.4, following the TASK-25.2.3.2.4 precedent (one bundled deletion subtask once every caller is migrated). TASK-25.2.4.3 through .4.6 are Done. On 2026-09-15, rg finds no import of the seven mirrors anywhere in app/ outside the mirrors and their own legacy tests.

Delete:
- app/integrations/aws/{organizations,sso_admin,config,cost_explorer,guard_duty,security_hub,lambdas}.py
- app/tests/integrations/aws/{test_organizations,test_sso_admin,test_legacy_config,test_cost_explorer,test_guard_duty,test_security_hub,test_lambas}.py (the Lambda test is misspelled 'test_lambas.py' on disk)

Prune the seven modules' lines from app/bin/baselines/vendor_package_contract.txt (lines 8, 9, 11, 12, 13, 15, 18) and app/bin/baselines/sdk_typing_antipatterns.txt (lines 7, 8, 10, 11, 12, 13, 15).

Also in scope (human decision 2026-09-15): remove every trace of the dead `/sre dev aws` dev command. Its handler and registration are commented out and call an aws_dev_router that no longer exists, and no Python code reads its locale keys:
- app/locales/dev.en-US.yml and app/locales/dev.fr-FR.yml: subcommands.aws.description (line 2) and the eleven aws.* keys (lines 12-22).
- app/modules/dev/platforms/slack.py: the commented handle_aws_dev_command block (:291-336), the commented aws registration (:402-408), and 'aws' in the module docstring (:4-5).
- app/modules/dev/__init__.py: 'AWS' in the module docstring (:4).

Close-out (human decision 2026-09-15): once verified, tick the TASK-25.2.4 coordinator's ACs #1-#4, with a note tracing each AC to its children. A human changes the parent's status.

Out of scope, owned by later tasks: execute_aws_api_call, handle_aws_api_errors, paginator, assume_role_session, get_aws_service_client and the re-exported constants in integrations/aws/client.py; sqs.py, shield.py, schemas.py and tests/integrations/aws/{test_legacy_aws_client,test_sqs}.py (TASK-25.2.6); integrations/aws/dynamodb.py (TASK-25.2.5). The remaining baseline entries for those files stay.

Size gate: this touches about 20 files. The diff deletes ~489 production LOC of mirrors, ~819 lines of legacy tests, 14 baseline lines, ~24 locale lines and ~55 lines of commented-out dead code, and edits two docstrings. Nothing is added and live behaviour does not change. It stays one PR under the config/manifest-only and bundled-deletion exception accepted for TASK-25.2.3.2.4.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 integrations/aws/{organizations,sso_admin,config,cost_explorer,guard_duty,security_hub,lambdas}.py and tests/integrations/aws/{test_organizations,test_sso_admin,test_legacy_config,test_cost_explorer,test_guard_duty,test_security_hub,test_lambas}.py no longer exist; client.py, dynamodb.py, settings.py, shield.py, sqs.py, schemas.py, test_legacy_aws_client.py and test_sqs.py are untouched
- [x] #2 bin/baselines/vendor_package_contract.txt and bin/baselines/sdk_typing_antipatterns.txt carry no entry for the seven deleted modules and every other entry is unchanged; make check-sdk-typing and make check-vendor-package-contract print OK with no stale INFO line naming any of the seven
- [x] #3 rg over app/ (production, tests and mock.patch strings) for the seven module paths (integrations.aws.<name> / from integrations.aws import <name>) returns zero hits; rg for execute_aws_api_call|handle_aws_api_errors hits only integrations/aws/{client,dynamodb,sqs}.py, tests/integrations/aws/{test_legacy_aws_client,test_sqs}.py, bin/check_sdk_typing.py, the sdk_typing_antipatterns.txt header and decisions/sdk-typing.md, recorded in notes as owned by TASK-25.2.5/25.2.6
- [x] #4 locales/dev.en-US.yml and dev.fr-FR.yml no longer contain subcommands.aws.description or any aws.* key and still load with yaml.safe_load; modules/dev/platforms/slack.py no longer contains the commented handle_aws_dev_command block or aws registration, and neither its docstring nor modules/dev/__init__.py's lists AWS; rg for aws_dev_router|handle_aws_dev_command|dev.subcommands.aws in app/ returns zero hits
- [x] #5 ruff check, mypy (error count no higher than the pre-edit baseline minus the two organizations.py errors) and pytest tests --ignore=tests/smoke (only the known order-dependent failures) pass, with commands and output recorded in notes
- [x] #6 TASK-25.2.4's AC#1-#4 are checked with a traceability note to its children; TASK-25.2.4's status is left for a human
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (verified 2026-09-15 on main @ ccb61942)
- Callers: TASK-25.2.4.3/.4/.5/.6 are all Done. `rg "integrations[./]aws[./](organizations|sso_admin|config|cost_explorer|guard_duty|security_hub|lambdas)\b|from integrations\.aws import"` over app/ finds the seven mirror modules only in their seven legacy test files. Every other `from integrations.aws import` hit is `client` (tests) or `dynamodb` (modules/slack/webhooks.py:10, modules/incident/db_operations.py:6, modules/incident/incident_folder.py:20, owned by TASK-25.2.5).
- Mirrors: organizations.py 96, sso_admin.py 145, config.py 45, cost_explorer.py 42, guard_duty.py 71, security_hub.py 32, lambdas.py 58 = 489 LOC. Nothing else in integrations/aws imports them, and integrations/aws/__init__.py is empty.
- Legacy tests: test_organizations.py 424, test_sso_admin.py 84, test_legacy_config.py 57, test_cost_explorer.py 76, test_guard_duty.py 88, test_security_hub.py 50, test_lambas.py 40 = 819 lines. Each imports only its own mirror. tests/integrations/aws/ has no conftest or __init__.py, and keeps test_legacy_aws_client.py and test_sqs.py (TASK-25.2.6).
- Baselines: vendor_package_contract.txt lines 8 config, 9 cost_explorer, 11 guard_duty, 12 lambdas, 13 organizations, 15 security_hub, 18 sso_admin. sdk_typing_antipatterns.txt lines 7 config, 8 cost_explorer, 10 guard_duty, 11 lambdas, 12 organizations, 13 security_hub, 15 sso_admin. Both checkers (bin/check_vendor_package_contract.py:123-150, bin/check_sdk_typing.py:76-96) report stale entries only as INFO and fail only on net-new violations, so pruning cannot break CI.
- Dispatcher after this PR: execute_aws_api_call/handle_aws_api_errors remain in integrations/aws/client.py, dynamodb.py and sqs.py, in tests/integrations/aws/test_legacy_aws_client.py and test_sqs.py, in bin/check_sdk_typing.py, in the sdk_typing_antipatterns.txt header comment (:2) and in decisions/sdk-typing.md. All belong to TASK-25.2.5/25.2.6. The original AC#3 ("zero hits in production code") could not pass, so it was rescoped on 2026-09-15.
- mypy: the baseline is 87 errors in 31 files (TASK-25.2.4.3-.6 notes). Two of them are in a deleted file (integrations/aws/organizations.py:63 and :77, no-any-return), so the expected result is 85 errors in 30 files.
- Dev aws traces: app/locales/dev.{en-US,fr-FR}.yml line 2 (subcommands.aws.description) and lines 12-22 (aws.services.*, aws.identitystore.*, aws.organizations.*, aws.sso_admin.*, aws.health.check). rg over *.py finds no reader of these keys. dev.subcommands.aws.description appears only in commented code. modules/dev/platforms/slack.py :291-336 is the commented handle_aws_dev_command, which calls aws_dev_router (zero definitions anywhere in the repo), and :402-408 is the commented registration; the docstring at :4-5 lists "and aws". modules/dev/__init__.py:4 lists "AWS". tests/modules/slack/test_dev_platforms_slack_contract.py only patches get_app_settings and is unaffected. The i18n loader (infrastructure/i18n/loader.py:104) globs *.<locale>.yml, so the files must stay valid YAML.

ORDERED STEPS
Step 0 - Re-verify preconditions (from app/). No edits.
  rg -n "integrations[./]aws[./](organizations|sso_admin|config|cost_explorer|guard_duty|security_hub|lambdas)\b|from integrations\.aws import (organizations|sso_admin|config|cost_explorer|guard_duty|security_hub|lambdas)\b" --glob '!.venv/**' .
  Expect hits only in the seven legacy test files. Any other hit (a script, job or mock.patch string) blocks the deletion and goes back to the human.
  Record the mypy baseline count before editing.

Step 1 - Delete the seven legacy test files, then the seven mirrors (AC#1). rm only. No other file under integrations/aws or tests/integrations/aws is touched.

Step 2 - Prune both baselines (AC#2). Remove exactly the seven listed lines from each file and leave the header comments unchanged. Result: vendor_package_contract.txt keeps module:integrations/aws/{dynamodb,schemas,shield,sqs}.py plus every non-AWS entry; sdk_typing_antipatterns.txt keeps integrations/aws/{client,dynamodb,sqs}.py.

Step 3 - Remove the dev aws traces (AC#4).
  a. Both dev locale files: delete line 2 and lines 12-22. Each file keeps `dev:`, subcommands.{google,slack,stale,incident,load_incidents,add_incident}.description, help.{title,section_header,footer} and errors.environment_restricted.
  b. modules/dev/platforms/slack.py: change the docstring's "google, slack, stale, incident,\nload-incidents, add-incident, and aws." to "google, slack, stale, incident,\nload-incidents and add-incident.". Delete the commented block :291-336, keeping two blank lines before `def register_commands`. Delete the blank line and commented registration :401-408, so the add-incident registration is the function's last statement. No import changes: the removed code was commented out and used no live names.
  c. modules/dev/__init__.py:4: change "Google Workspace, Slack, AWS, and incidents." to "Google Workspace, Slack and incidents.".

Step 4 - Gates and evidence (AC#3, AC#5). All from app/; record the command and actual output in notes.
  uv run ruff check . && uv run ruff format --check modules/dev
  uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'   -> expect 85 errors in 30 files, never more than the recorded baseline
  uv run pytest tests --ignore=tests/smoke          -> only the 6 known order-dependent failures (test_webhooks_aws_sns.py x3, infrastructure/directory/test_google.py x3); run make test for confirmation if needed
  make check-sdk-typing && make check-vendor-package-contract -> OK, and no INFO stale line naming any of the seven
  uv run python -c "import yaml; [yaml.safe_load(open(f'locales/dev.{l}.yml')) for l in ('en-US','fr-FR')]"
  rg the AC#3 and AC#4 patterns and paste the output.

Step 5 - Backlog close-out (AC#6). Check this task's ACs one by one as each is verified. Check TASK-25.2.4 ACs #1-#4 and append a traceability note there (#1 <- .4.1/.4.2, #2 and #4 <- .4.3-.4.6, #3 <- .4.7). Leave TASK-25.2.4 and this task In Progress for a human.

AC TRACEABILITY
- AC#1 <- Step 1; evidence: ls app/integrations/aws app/tests/integrations/aws
- AC#2 <- Step 2; evidence: the two make checks plus a diff of the baselines
- AC#3 <- Steps 0, 1, 4; evidence: the two rg outputs
- AC#4 <- Step 3; evidence: rg output and the YAML load
- AC#5 <- Step 4
- AC#6 <- Step 5

TEST MATRIX
No new tests. This PR only deletes code and changes no live behaviour, so there is nothing to TDD.
- Deleted tests covered only the deleted mirrors. Behaviour now lives in, and stays covered by, tests/unit/packages/aws_platform/test_aws_platform_*.py (adapters) and tests/unit/modules/aws/test_{ops_group_assignment,spending,aws_account_health,lambdas}_handler.py (callers).
- Regression guards: the full pytest run shows no ImportError or collection error from a leftover reference; mypy/ruff show no dangling import; both guard scripts pass; the i18n loader still parses both dev locale files; test_dev_platforms_slack_contract.py passes with slack.py edited.

ASSUMPTIONS AND DOUBTS
- No non-Python reference to the seven modules exists (scripts, Makefile, CI, docs, decisions). Verified on 2026-09-15 with an rg over the repo excluding backlog/, .venv and *.py: hits only in the two baselines and the unrelated types-boto3-sso-admin entry in uv.lock, which stays because the SSO-Admin adapter uses the stubs. Re-run in Step 0.
- No code builds dev aws.* locale keys dynamically. Verified: no f"aws. or "aws.<x>. string literal in *.py outside module paths. The translator is never asked for these keys, so removing them cannot surface a missing-key fallback.
- The mypy baseline of 87 may have drifted on main since TASK-25.2.4.6. Step 0 records the actual pre-edit count, and the AC is "no higher than that count, minus the two organizations.py errors".
- The 6 known order-dependent pytest failures are pre-existing (memory: TASK-90 leaks). They are called out, not fixed.

BLAST RADIUS AND ROLLBACK
- Production risk is near zero: no live import of the deleted modules remains, and the dev-command removals touch commented code, orphaned locale keys and docstrings only. If Step 0 missed a reference, the failure is an ImportError at collection or import time, which CI's pytest and mypy catch before merge.
- A single git revert restores every file, and the guard baselines only ratchet down, so a revert cannot trip them.
- Ordering: no env, settings or terraform prerequisite. This task does not block TASK-25.2.5/25.2.6 beyond shrinking their baselines.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Planning 2026-09-15 (human decisions):
- AC#3 rescoped. The dispatcher (execute_aws_api_call/handle_aws_api_errors) still has production users in client.py, dynamodb.py and sqs.py, owned by TASK-25.2.5/25.2.6, so "zero hits in production code" could not pass. The grep now requires zero references to the seven module paths anywhere in app/, and remaining dispatcher hits are listed and attributed.
- Scope widened to remove the dead /sre dev aws dev command: its orphaned locale keys in both dev locale files, the commented-out handler and registration in modules/dev/platforms/slack.py, and the AWS mentions in two docstrings. AC#4 added.
- Close-out: the implementer ticks TASK-25.2.4 AC#1-#4 with traceability (AC#6). A human moves the parent.
- Gates AC (#5) added, following the TASK-25.2.3.2.4 precedent. mypy is expected to drop by 2, because organizations.py:63 and :77 carry no-any-return errors.
- Size: about 20 files, all deletions or docstring edits, no live behaviour change. Kept as one PR on the TASK-25.2.3.2.4 bundled-deletion precedent.

Implementation 2026-09-15:
- Deleted app/integrations/aws/{organizations,sso_admin,config,cost_explorer,guard_duty,security_hub,lambdas}.py and app/tests/integrations/aws/{test_organizations,test_sso_admin,test_legacy_config,test_cost_explorer,test_guard_duty,test_security_hub,test_lambas}.py. integrations/aws/ keeps __init__, client, dynamodb, schemas, settings, shield and sqs; tests/integrations/aws/ keeps test_legacy_aws_client.py and test_sqs.py.
- Pruned the seven lines from each baseline. vendor_package_contract.txt keeps aws dynamodb/schemas/shield/sqs plus every non-AWS entry; sdk_typing_antipatterns.txt keeps client, dynamodb and sqs.
- Dev aws traces removed: line 2 and lines 12-22 from locales/dev.{en-US,fr-FR}.yml; the commented handle_aws_dev_command block and the commented aws registration from modules/dev/platforms/slack.py (408 -> 352 lines); "and aws" from its docstring; "AWS" from modules/dev/__init__.py's docstring.
- Red/green check: a temporary pytest module in the session scratchpad (outside the repo, deleted afterwards, never committed) asserted mirror and test-file absence (incl. importlib find_spec), baseline pruning, retention of out-of-scope files and entries, dev locale keys (yaml.safe_load) and the slack.py/__init__.py traces. Before edits: 31 failed, 15 passed (the 15 are the retention guards). After: 46 passed.

Evidence (from app/ unless noted):
- uv run ruff check . -> All checks passed! ; uv run ruff format --check modules/dev -> 6 files already formatted
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> before edits: Found 87 errors in 31 files (checked 359 source files); after: Found 85 errors in 30 files (checked 352 source files). The two removed errors were organizations.py:63/:77.
- uv run pytest tests --ignore=tests/smoke -> 6 failed, 3439 passed. The 6 are the known order-dependent failures: tests/modules/webhooks/test_webhooks_aws_sns.py (3) and tests/unit/infrastructure/directory/test_google.py (3). Not touched here.
- make check-sdk-typing -> OK: no net-new SDK anti-patterns (3 baselined file(s) remain). make check-vendor-package-contract -> OK: no net-new vendor-package contract violations (21 baselined entry(ies) remain). Neither printed a stale INFO line.
- rg (repo root, app/) for the seven module paths and from-imports -> no hits.
- rg -l execute_aws_api_call|handle_aws_api_errors (repo, excluding backlog/) -> app/integrations/aws/{client,dynamodb,sqs}.py, app/tests/integrations/aws/{test_legacy_aws_client,test_sqs}.py, app/bin/check_sdk_typing.py, app/bin/baselines/sdk_typing_antipatterns.txt (header comment), decisions/sdk-typing.md. dynamodb.py belongs to TASK-25.2.5; client.py/sqs.py and the two legacy tests belong to TASK-25.2.6; the checker, baseline header and ADR stay until those baselines empty.
- rg aws_dev_router|handle_aws_dev_command|dev\.subcommands\.aws in app/ -> no hits.

For the human: no settings, env, terraform or runtime behaviour changes. TASK-25.2.4 ACs #1-#4 are now checked with traceability; both tasks await a human to move them to Done.
<!-- SECTION:NOTES:END -->
