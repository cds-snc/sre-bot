---
id: TASK-111.5
title: Lower-case the host, security and hosting settings fields
status: To Do
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-21T20:24:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.2
references:
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1752
parent_task_id: TASK-111
type: feature
ordinal: 411000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Mechanical: the fields of AppSettings, ServerSettings, SecuritySettings, SlackTransportSettings and the hosting slices (retry, audit, coordination, scheduler, directory, drive, spreadsheets) become lower snake_case with case_sensitive=False; every reader follows. Environment names do not change. LoggingSettings is not in scope: TASK-111.2 lower-cases it when it moves onto the files.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Those slices declare lower snake_case fields with case_sensitive=False and read the same environment names as before
- [ ] #2 No behaviour change: the existing tests pass with only attribute renames
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [ ] #4 A parametrized test pins every production environment name per touched slice (doc-14 inventory plus the deploy-interface names): each name set to a sentinel is received by the renamed field, so a silent fallback to a default fails CI
- [ ] #5 The implementation notes carry the post-deploy checklist (build_and_deploy Slack success, one PRIMARY deployment COMPLETED, no plugin_boot_failed or ERROR in the first minutes of logs, one Slack command in the test channel) and the manual-retag rollback
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
DRAFT - GATE TRIPPED, NOT APPROVED FOR HANDOFF. The full task touches ~34 production files (see Size gate); this plan is written for SLICE 1 only. The human must approve the split below before any subtask exists or any code is written.

== Findings that shape the plan ==
- retry, directory, drive and spreadsheets fields are ALREADY lower snake_case (they carry aliases like RETRY_ENABLED). They need only case_sensitive=False, inherited from InfrastructureSettings. No field rename, no reader change.
- Renames needed: AppSettings (ENVIRONMENT, GIT_SHA, WEBHOOK_MAX_BODY_BYTES); ServerSettings (BACKEND_URL, NOTIFY_OPS_CHANNEL_ID, NOTIFY_ONCALL_GROUP_ID, SRE_TEST_CHANNEL_ID, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES, ACCESS_TOKEN_MAX_AGE_MINUTES) and DevSettings (SLACK_DEV_MSG_CHANNEL, same file, same base class, no reader); SecuritySettings (ISSUER_CONFIG, CORS_ALLOWED_ORIGINS/METHODS/HEADERS, DEV_BYPASS_ENABLED/TOKEN); SlackTransportSettings (COMMAND_PREFIX); AuditSettings (AUDIT_TABLE_NAME); ConditionalWriteSettings (IDEMPOTENCY_TTL_SECONDS, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS); SchedulerSettings (DEFAULT_TIER2_LEASE_TTL_SECONDS).
- Verified with a probe (pydantic-settings, case_sensitive=False): a lower-case field with NO alias reads the upper-case env name; a lower-case field with an alias reads the alias; constructor kwargs in either case are accepted. So test constructors like Settings(ENVIRONMENT=...) keep working; only attribute reads change.
- Production sets none of the hosting names (retry, audit, coordination, scheduler, directory, drive, spreadsheets): per doc-14 they run on code defaults. For slice 1 the env-name pin therefore protects the deploy interface, not a live production value; state this in the test docstring.

== Env-name mechanism ==
1. Field whose env name == UPPER(field name): rename the field to lower case and DROP the alias; case_sensitive=False reads the same env name. (decisions/configuration.md: no per-field aliases is the end state.)
2. Field whose env name differs from the field name (SECRET_KEY<-SESSION_SECRET_KEY, COMMAND_PREFIX<-SLACK__COMMAND_PREFIX, retry/directory/drive/spreadsheet aliases): KEEP the alias unchanged. ADR line 94 permits aliased names until TASK-111 migrates the slice.
3. Why it survives 111.7/111.8/111.13: those rows put the slice on ConfigurationSlice (env_prefix="<TABLE>__", field name = TOML key). Mechanism 1 fields already equal the TOML key and carry no alias, so nothing is undone; the prefix simply starts applying. Mechanism 2 aliases must be deleted by the row that migrates the slice (a field with an alias would make the TOML source look up the alias, and check_settings_key_ownership env-naming rule rejects bare names on a ConfigurationSlice). That deletion is already in those rows' scope (rename map in doc-14). 111.5 adds no alias that is not already there.
4. check_settings_key_ownership: case-folds keys and reads a no-alias field as env_prefix+field name; lower-cased field gives the same folded key, so ownership is unchanged. Run make check-settings-key-ownership and make check-import-contracts every slice.

== Behaviour-change risks found (must be handled, not assumed away) ==
R1 infrastructure/coordination/factory.py:18 model_copy(update={"IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS": ...}): string key. model_copy does NOT validate; after the rename it would silently add a stray attribute and the custom in-progress TTL would be ignored (leases keep the default 300s). Must change to the new field name; add a test asserting the copy's in_progress ttl equals the argument (tests/unit/infrastructure/coordination/test_coordination_store_factory.py already builds base settings; extend it).
R2 server/lifespan.py:97-101 logs tuple(model_dump().keys()) as configuration_loaded keys=... : the logged key names change from upper to lower case for app/server/security/directory/sre_ops. Log-content change only; no consumer found in app/, terraform/ or .github/ (rg for configuration_loaded). Accepted and called out in the PR description; confirm no CloudWatch metric filter/alarm matches these keys (check terraform for aws_cloudwatch_log_metric_filter).
R3 server/lifespan.py:93 {"GIT_SHA": app_settings.GIT_SHA} and :92 {"LOG_LEVEL": ...}: the dict KEY is a log label, not a field name. Keep the label as is (tests/integration/server/test_lifespan.py:99 asserts {"LOG_LEVEL": ...}); only the attribute changes.
R4 MagicMock/Mock settings in tests (tests/integration/infrastructure/coordination/conftest.py:24, tests/unit/infrastructure/coordination/test_coordination_dynamodb_store_operations.py:34-35, tests/unit/jobs/test_scheduled_tasks.py:321,353,415): a Mock auto-creates any attribute, so a missed rename passes silently or fails far from the cause. Rename each mock attribute assignment; grep for the old names across app/tests must return zero at the end of each slice.
R5 Validator/error-message text names the env var (security/settings.py "ISSUER_CONFIG entry...", "CORS_... cannot include '*'", jwks.py:24,27, lifespan.py:156-166): keep the env-var spelling, it is what an operator edits. Not renamed.
R6 tests/unit/infrastructure/security/test_security_settings_load.py:127-132 asserts case_sensitive is True; becomes False in the security slice (deliberate test change, not an attribute rename). Also _NAMES / model_fields tests there change to lower-case.
R7 InfrastructureSettings.case_sensitive flips for DevSettings and every hosting slice at once. FeatureSettings (atip, groups, incident, sre_ops, aws_ops) is NOT touched (111.14).
R8 docs_generator.py iterates model_fields names for generated docs: output changes only if run; not wired into CI or startup (no caller found).
No getattr(settings, "NAME") or settings["NAME"] access to renamed fields found (rg over app/, bin/).

== Size gate (honest) ==
Production readers + settings, all slices: ~34 files (8 settings/base, 15 non-legacy readers, 11 legacy app/modules readers), est. 80-100 changed LOC. Tests: 59 files / ~205 lines reference the old names. LOC is far under 400 but files are ~3x the ~10-file bar; touching legacy modules and tests makes it unreviewable as one diff. VERDICT: gate trips (files). No subtasks created; proposed split for approval:
 S1 Hosting infrastructure (THIS DRAFT): InfrastructureSettings.case_sensitive=False; audit, coordination, scheduler renames; retry/directory/drive/spreadsheets pinned only. 9 prod files, ~25 LOC, ~7 test files + 1 new.
 S2 Server + dev + security: ServerSettings, DevSettings, SecuritySettings. 8 prod files (settings x2, security/jwks.py, security/current_user.py (DEV_BYPASS only), server/server.py, server/lifespan.py, modules/webhooks/slack.py, modules/webhooks/patterns/aws_sns_notification/api_key_detected.py), ~35 LOC, ~6 test files (security tests are the bulk).
 S3 Slack transport COMMAND_PREFIX: infrastructure/slack/settings.py, integrations/slack/provider.py:1156, modules/{aws/aws.py:55, role/role.py:37, secret/secret.py:24, atip/atip.py:38, incident/incident.py:38}. 7 files, ~15 LOC, 6 test files (the five *_command_registration tests and test_slack_transport_settings).
 S4 App identity: ENVIRONMENT, GIT_SHA, WEBHOOK_MAX_BODY_BYTES: configuration/app.py, api/routes/system.py:17, infrastructure/logging/setup.py:201, infrastructure/security/current_user.py:103,109, server/server.py:34, server/lifespan.py:93,134,250, integrations/notify/client.py:116, two doc-comment hits (configuration/__init__.py:23, logging/formatters.py:201), legacy modules (sre/platforms/slack.py:40, dev/platforms/slack.py:40, atip/atip.py:402, incident/core.py:300,426,565, incident/incident_conversation.py:38, api_key_detected.py:19). ~15 files, ~30 one-line edits: still over the file bar but every edit is a one-token attribute rename; reviewable by grep. Order S4 last (largest blast radius: ENVIRONMENT required at boot, gates production behaviour). Each slice is independently shippable and revertible; order S1, S2, S3, S4; all before 111.7/8/13 as the dependency graph already requires.

== SLICE 1 PLAN (draft) ==
Steps (each names files):
1. Write the failing pin test first: app/tests/unit/infrastructure/configuration/test_configuration_settings_production_names.py. One parametrized table of (settings class, environment name, attribute, sentinel). S1 rows: AUDIT_TABLE_NAME->audit_table_name; IDEMPOTENCY_TTL_SECONDS->idempotency_ttl_seconds; IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS->idempotency_in_progress_ttl_seconds; DEFAULT_TIER2_LEASE_TTL_SECONDS->default_tier2_lease_ttl_seconds; RETRY_ENABLED/BACKEND/DYNAMODB_TABLE_NAME/DYNAMODB_TTL_DAYS/MAX_ATTEMPTS/BASE_DELAY_SECONDS/MAX_DELAY_SECONDS/BATCH_SIZE/CLAIM_LEASE_SECONDS; DIRECTORY_PROVIDER, DIRECTORY_REQUIRE_STARTUP_WARMUP, DIRECTORY_CACHE_TTL_SECONDS, DIRECTORY_STARTUP_WARMUP_TIMEOUT_SECONDS; DRIVE_PROVIDER; SPREADSHEET_PROVIDER. Sentinel is a non-default value of the right type; monkeypatch.setenv(name, sentinel), build with _env_file=None, assert the attribute equals it (a silent fallback to the default fails). Also assert the upper-case name works under a lower-case-field class and that a lower-case env name is accepted (case_sensitive=False). Later slices append rows; S4 row set includes ENVIRONMENT and GIT_SHA (Dockerfile:50 sets GIT_SHA). Docstring states what each table row pins; no task ids.
2. infrastructure/configuration/base.py: InfrastructureSettings case_sensitive=False.
3. infrastructure/audit/settings.py: audit_table_name, drop alias; update docstring env-var note unchanged. Reader: infrastructure/audit/service.py:263.
4. infrastructure/coordination/settings.py: idempotency_ttl_seconds, idempotency_in_progress_ttl_seconds, drop aliases. Readers: coordination/in_memory.py:26-27, coordination/dynamodb.py:40-41, coordination/factory.py:18 (string key, R1).
5. jobs/settings.py: default_tier2_lease_ttl_seconds, drop alias. Reader: jobs/scheduled_tasks.py:92.
6. Update tests (attribute renames only, plus R1 test): tests/unit/infrastructure/coordination/{test_coordination_settings.py:31-49, test_coordination_dynamodb_store_operations.py:34-35, test_coordination_store_factory.py, test_coordination_in_memory_store_operations.py, test_coordination_dynamodb_ownership.py, test_coordination_run_if_leased.py}, tests/integration/infrastructure/coordination/conftest.py:24, tests/unit/infrastructure/audit/test_audit_settings_table_name.py:21,27, tests/unit/jobs/test_jobs_settings.py:23,32, tests/unit/jobs/test_scheduled_tasks.py:321,353,415. Constructor kwargs (ConditionalWriteSettings(IDEMPOTENCY_TTL_SECONDS=...)) stay valid (case-insensitive) and are left unchanged. Final check: rg for the old attribute names over app/, bin/, terraform/, .github/ returns only env-var strings, docstrings and the pin table.
7. Gates from app/: uv run ruff check .; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' (no new errors in touched files); uv run pytest tests --ignore=tests/smoke; make check-settings-key-ownership; make check-import-contracts.

AC traceability (S1): AC1 -> steps 2-5 + pin test (step 1); AC2 -> step 6 (existing tests pass with attribute renames only, plus the R1 test); AC3 -> step 7; AC4 (pin test) -> step 1; AC5 (post-deploy checklist in notes) -> final --notes at implementation time. Reverse: every step maps to an AC or R1.

Test matrix (S1): happy: each env name sets its field (pin table); default: unset env keeps default (existing tests); boundary: lower-case env name accepted, upper-case constructor kwarg accepted; failure: invalid value (int field given text) raises ValidationError (existing coordination validation tests); regression: build_conditional_write_store honours in_progress_ttl_seconds (R1). No authorization or idempotency cases apply.

Assumptions and doubts (verify):
- A1 Constructor kwargs stay case-insensitive under case_sensitive=False in the pinned pydantic-settings: probed once; re-verify in step 1 with an explicit test, and if it fails rename kwargs in tests (more test edits, no prod change).
- A2 Nothing reads these settings by string (getattr, model_dump consumers, jsonschema): verified by rg over app/ and bin/; recheck with rg -n 'getattr\(.*settings|model_dump|model_copy' at implementation start.
- A3 No CloudWatch metric filter or dashboard keys on configuration_loaded key names (R2): verify with rg over terraform/ before S2/S4 (S1 changes only coordination/audit/scheduler keys logged? no: lifespan logs app/server/security/directory/sre_ops only, so S1 logs unaffected except directory key names, which are already lower-case).
- A4 Production sets none of the hosting names: doc-14 inventory; verify with aws ecs describe-task-definition environment/secrets list before merge.
- A5 Dropping aliases does not change any env name: pinned by the table test.

Blast radius and rollback (S1): merging to main deploys. Production has no ECS deployment circuit breaker and runs the :latest image until TASK-111.16; there is no automatic rollback. If S1 ships wrong the realistic failure is a boot-time AttributeError in a hosting provider (audit/coordination/scheduler wiring in lifespan) or R1 (silently wrong lease TTL, not a crash). One git revert restores code, but redeploy needs the revert merged, or a manual retag of the previous <sha>-<date> image as latest. No environment or terraform change, so no ordering constraint. S4 (ENVIRONMENT required) and S2 (security) have the higher blast radius.

Post-deploy checklist (record in --notes for every slice):
1. build_and_deploy workflow posts its Slack success message.
2. aws ecs describe-services (cluster/service for sre-bot) shows exactly one PRIMARY deployment with rolloutState COMPLETED.
3. CloudWatch log group for sre-bot: no plugin_boot_failed and no ERROR level in the first minutes after the new task starts.
4. One Slack command in the test channel responds (e.g. the version command on S4, any registered command otherwise).
Rollback if any fails: manual retag of the previous <sha>-<date> image.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-21T20:05:00Z

---

Planning input (human-approved 2026-10-21): (1) a test that pins the production environment names per slice: for each touched slice, set every production name from the doc-14 inventory to a sentinel and assert the field receives it, so a rename that silently falls back to a default fails CI instead of production (static /health would not catch it). (2) A post-deploy checklist in the notes: the build_and_deploy Slack success message; aws ecs describe-services shows one PRIMARY deployment COMPLETED; no plugin_boot_failed or ERROR in the first minutes of CloudWatch logs; one Slack command in the test channel. Production has no deployment circuit breaker and runs :latest until TASK-111.16; rollback is the manual retag of the previous <sha>-<date> image.

---

created: 2026-10-21T20:18:00Z

---

Planning proposals (not applied): (1) The single-PR gate trips on files (~34 production files, ~80-100 LOC, 59 test files): proposed split S1 hosting infrastructure (9 files), S2 server+dev+security (8), S3 slack transport COMMAND_PREFIX (7), S4 app identity ENVIRONMENT/GIT_SHA/WEBHOOK_MAX_BODY_BYTES (~15 one-token edits); no subtasks created, awaiting approval. (2) AC2 "only attribute renames" needs two stated exceptions: the case_sensitive assertion in tests/unit/infrastructure/security/test_security_settings_load.py:127-132 flips to False, and one added regression test for coordination/factory.py:18 (model_copy string key). Suggest rewording AC2 rather than deleting it. (3) retry, directory, drive and spreadsheets fields are already lower-case; they need only the inherited case_sensitive=False.

---

created: 2026-10-21T20:24:00Z

---

Decision (human, 2026-10-21): no logic changes, all mechanical, so split in two PRs rather than four as a file-gate exception. TASK-111.5.1 hosting + security (gates 111.8, 111.13); TASK-111.5.2 server, dev, Slack COMMAND_PREFIX and app identity (gates 111.7, waits on 111.16 since ENVIRONMENT is required at boot). AC2 exceptions carried into the subtasks' ACs. The draft plan above is input for 111.5.1 slice 1; this task is the coordinator and closes when both merge.

---
<!-- COMMENTS:END -->
