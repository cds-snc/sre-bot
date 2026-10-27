---
id: TASK-111.11.2
title: Move the OpenAI slice onto the files; the key is OPENAI__API_KEY
status: In Progress
assignee: []
created_date: '2026-10-26T22:21:00Z'
updated_date: '2026-10-27T18:28:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.11.1
  - TASK-111.4
references:
  - decisions/configuration.md
parent_task_id: TASK-111.11
type: feature
ordinal: 450000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
OpenAISettings (integrations/openai/settings.py) becomes the [openai] ConfigurationSlice with the one vendor shape (decisions/configuration.md 2026-10-27): [openai] holds the tuning (max_output_tokens, temperature, timeout_seconds) in base.toml; the optional [openai.tenant] entry (base_url, model: the model endpoint, since OpenAI has no tenant id) enables the vendor and lives in production.toml and local.toml; api_key is the secret OPENAI__API_KEY, the SSM SecureString /sre-bot/OPENAI__API_KEY that TASK-111.4 already creates and injects (no terraform expand; its value is set outside terraform from the OPENAI_API_KEY line of sre-bot-config). The slice is validated at boot; an entry without the key, or the key without an entry, fails boot. With no entry, OpenAI is not configured: comms reports text generation unavailable as today, and the summarizer returns not configured without an API call. Whether a consumer requires OpenAI (scribe) is TASK-172. OPENAI_API_KEY and the OPENAI_* names are no longer read; the blob line stays inert until TASK-111.15. Split from TASK-111.11 on 2026-10-26.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The OpenAI slice reads max_output_tokens, temperature and timeout_seconds from [openai], base_url and model from the optional [openai.tenant] entry (both required in an entry), and the key only as OPENAI__API_KEY (hidden in repr and logs; empty counts as unset); the slice is validated at boot and an unknown key in [openai] or [openai.tenant] fails boot naming it
- [ ] #2 /sre-bot/OPENAI__API_KEY equals the OPENAI_API_KEY line it replaces (pre openai: MATCH, compared by hash, never printed)
- [x] #3 A tenant entry without the key, or the key without a tenant entry, fails boot naming the key; with neither the app boots, incident text generation is reported unavailable exactly as today, the summarizer returns not configured without an API call, and no message or log line carries a key value
- [x] #4 OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MAX_OUTPUT_TOKENS, OPENAI_TEMPERATURE, OPENAI_TIMEOUT_SECONDS and OPENAI_BASE_URL are no longer read from the environment or .env
- [x] #5 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass; make check-import-contracts and make check-settings-key-ownership pass
- [x] #6 zsh bin/deploy-checks.zsh has an openai check (pre: key by hash and no tuning blob lines; post: no configuration or unconfigured lines, no 401/403 lines); env-checks classifies the six old OPENAI_* names with their destination
- [x] #7 production.toml and local.toml carry [openai.tenant] with today's gateway URL and model; base.toml and ci.toml carry no tenant entry and no organisation value
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Deployed; zsh bin/deploy-checks.zsh post openai PASS and the manual check recorded
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN FOR TASK-111.11.2 (OpenAI slice onto the configuration files). Rewritten 2026-10-27 against main 903eed3f after the human's ruling on vendor shape and requirements (decisions/configuration.md, plugins.md, lifecycle.md 2026-10-27). Modelled on 111.10.2 and 111.11.1 (secret from the environment, boot-validated vendor slice, helpers, pins). Re-run every rg below first.

== Decisions (human, 2026-10-27) ==
D1 Every vendor slice has one shape: [openai] holds tuning; the optional [openai.tenant] entry enables the vendor; the slice is validated at boot like every vendor slice (an invalid one fails boot). This supersedes the TASK-111.11 Q2/Q4 answer (key required in the slice, not boot-validated).
D2 OpenAI has no tenant id, so the entry is the endpoint it reaches: [openai.tenant] base_url and model (both required in an entry; the model names what that endpoint serves). Values are the deploying organisation's (CDS's gateway), so they go in production.toml and local.toml, never in code defaults or base.toml (configuration.md :77).
D3 OPENAI__API_KEY is a field of the slice (as Slack's tokens), SecretStr | None, empty counts as unset. A tenant entry without the key, or the key without a tenant entry, fails boot naming the key, so OpenAI is never half configured.
D4 Requirement is the consumers', not the slice's. comms' AI drafting is the designed optional use (incident-management.md :111): no tenant means unavailable. scribe requires text generation, but stating that (boot fails when scribe is enabled with no tenant) is TASK-172, with ci.toml switching scribe off; here, with no tenant the summarizer returns a not-configured result without an API call.
D5 No terraform expand: /sre-bot/OPENAI__API_KEY exists and is injected since 111.4 (terraform/ssm.tf:32).

== Size ==
Production files 10: integrations/openai/settings.py, integrations/openai/summarizer.py, features/incident/comms/adapters/text_generation.py, server/configuration/host_configuration.py, config/base.toml, config/production.toml, config/local.toml, app/pyproject.toml, app/bin/audit_env_names.py, bin/deploy-checks.zsh. Docs 3: decisions/configuration.md, doc-14, features/incident/scribe/README.md. ~160 production LOC, one subsystem (the OpenAI vendor slice) plus the shared helpers. Gate: at the ~10-file limit, no refactor mixed in: PASS. client.py needs no edit (base_url and timeout_seconds stay readable on the slice, below). If a further file is needed, stop and ask.

== Context (verified 2026-10-27, main 903eed3f) ==
- integrations/openai/settings.py:20-41 OpenAISettings(BaseSettings, env_file=.env, extra=ignore, aliases OPENAI_*); api_key required today; get_openai_settings() lru_cache :44-47; `from __future__ import annotations` :12 deleted (3.14 baseline).
- Readers: client.py:21-34 build_openai_client (settings.base_url, settings.api_key.get_secret_value(), settings.timeout_seconds); summarizer.py:51-52 OpenAISummarizer (model, max_output_tokens, temperature), get_summarizer() :176; features/incident/comms/adapters/text_generation.py:41-49 catches ValidationError from get_summarizer() -> UnavailableTextGenerator, logs field names only; features/incident/scribe/service.py:334,975 call get_summarizer() unguarded. All reads at use; none at import.
- Boot validation list: server/configuration/host_configuration.py:153-155 (get_aws_settings, get_google_workspace_settings, get_notify_api_key_leak_settings).
- Pattern for a present/absent entry with a secret on the slice: integrations/slack/settings.py:29,71-73,109-116 (a token without a tenant fails; a tenant requires the bot token).
- Production: sets only OPENAI_API_KEY (doc-14 row 83, blob line); none of the tuning names (pins test :116-124, :314-336).
- Tests on old names: tests/unit/integrations/openai/{conftest.py,test_openai_settings.py}, test_configuration_settings_production_names.py (OPENAI rows), tests/unit/bin/test_bin_audit_env_names_classify.py; the comms adapter and availability tests patch get_summarizer.

== Steps (TDD, red first) ==
B1 Tests red: T-1..T-7.
B2 integrations/openai/settings.py: OpenAITenant(BaseModel, frozen, extra=forbid): base_url (str, min_length=1, https or loopback http), model (str, min_length=1). OpenAISettings(ConfigurationSlice) toml_table_header=("openai",), env_prefix="OPENAI__", no aliases: tenant: OpenAITenant | None = None; api_key: SecretStr | None = Field(default=None, repr=False) with empty -> None (as Slack's mode="before" validator); max_output_tokens=3000, temperature=-1.0, timeout_seconds=180.0 (both existing comments kept). model_validator: tenant without api_key fails naming OPENAI__API_KEY; api_key without tenant fails naming [openai.tenant]. Read-only properties base_url and model return the tenant's values (client.py and summarizer.py keep reading settings.base_url / settings.model). Docstring: keys of [openai] and [openai.tenant]; environment only OPENAI__API_KEY; validated at boot; whether OpenAI is required is each consumer's.
B3 summarizer.py: OpenAISummarizer.summarize returns OperationResult.permanent_error(error_code="TEXT_GENERATION_NOT_CONFIGURED" or the registry member that exists; check contracts error-code registry) without building a client when settings.tenant is None. `from __future__` removed.
B4 text_generation.py: build_status_update_text_generator returns UnavailableTextGenerator when get_openai_settings().tenant is None (logs incident_status_update_text_generation_unconfigured with no fields), else get_summarizer(); the ValidationError branch is deleted (the slice is validated at boot); docstring updated.
B5 host_configuration.py: get_openai_settings() beside get_google_workspace_settings() (+import).
B6 config/base.toml: [openai] after [access_permission_sets], the three tuning keys, comment: the key is a secret from OPENAI__API_KEY; [openai.tenant] (base_url, model) names the deployment's model endpoint and lives in its environment file; no entry means OpenAI is not configured. production.toml and local.toml: [openai.tenant] base_url = "https://ai.cdssandbox.xyz", model = "gpt-5.6-luna". ci.toml: nothing.
B7 app/pyproject.toml pytest env: "OPENAI__API_KEY=" beside the AWS blanks (comment: "Likewise OpenAI").
B8 Existing tests moved off the old names (conftest installs tmp files, clears OPENAI_* and OPENAI__*; the openai_settings fixture builds a slice with a tenant and a key).
B9 app/bin/audit_env_names.py HINTS: OPENAI_API_KEY -> "secret OPENAI__API_KEY"; OPENAI_MODEL -> "[openai.tenant] model"; OPENAI_BASE_URL -> "[openai.tenant] base_url"; OPENAI_MAX_OUTPUT_TOKENS, OPENAI_TEMPERATURE, OPENAI_TIMEOUT_SECONDS -> "[openai] <key>". app/bin/audit_env_coverage.py: expected no change (doc-14 row 83 names the destination and ssm.tf creates it); verify, add a rule only if needed (it would be an 11th file: ask first).
B10 bin/deploy-checks.zsh: check openai; TASK_CHECKS=(google aws openai), PRE_CHECKS=(google aws openai); header comment.
  pre: /sre-bot/OPENAI__API_KEY vs the OPENAI_API_KEY blob line by hash (the aws compare/line_hash pattern; MATCH/DIFFER/MISSING, never printed); blob_where for the five tuning names (expected none; a present line blocks: its value needs a key in production.toml first); openai_pre PASS only on MATCH and no tuning line.
  post: since the deploy, zero configuration_invalid lines naming openai, zero incident_status_update_text_generation_unconfigured lines, openai_summarize_failed with 401/403 counted (masked samples); openai_summarize_usage count informational; openai PASS/FAIL.
B11 Docs: decisions/configuration.md: Changes line (OpenAI reads [openai] and [openai.tenant]; key OPENAI__API_KEY; old names unread) and the tolerated-list example at :104 drops OPENAI_API_KEY; doc-14 row 83 (destination kept; "no longer read (TASK-111.11.2); blob line inert until 111.15") and rows for the five tuning names if listed; scribe README :398-400, :426, :495 to the new keys.

== Tests ==
T-1 tests/unit/integrations/openai/test_openai_settings_load.py (replaces test_openai_settings.py): [openai] tuning from installed files; [openai.tenant] fills base_url and model; OPENAI__API_KEY sets the key; repr, str and model_dump() never show the key; no tenant and no key loads with tenant None; the six old OPENAI_* names in env and .env are ignored (AC 1, 4).
T-2 tests/unit/integrations/openai/test_openai_settings_tenant_validate.py: tenant without key fails naming OPENAI__API_KEY; key without tenant fails; empty key counts as unset; tenant missing base_url or model fails naming it; a non-https base_url fails; unknown key in [openai] or [openai.tenant] fails naming it (AC 1, 3).
T-3 tests/unit/integrations/openai/test_openai_summarizer_unconfigured.py: no tenant -> permanent error, no client built (build_openai_client spied), no log line carries a key value (AC 3).
T-4 tests/unit/features/incident/comms/test_incident_comms_text_generation_adapter.py (cases replaced): no tenant -> UnavailableTextGenerator reporting TEXT_GENERATION_UNAVAILABLE; with a tenant and key -> the process summarizer (AC 3).
T-5 tests/unit/infrastructure/configuration/test_configuration_files_openai.py: base + each environment file validates against OpenAISettings (with a key where a tenant exists); production.toml and local.toml carry [openai.tenant], base.toml and ci.toml none; no file has an api_key or secret-shaped value (AC 1, 7).
T-6 tests/integration/server/test_lifespan_vendor_slice_validation.py: an unknown [openai] key, a tenant without a key, and a key without a tenant each fail load_host_configuration naming the key; no tenant and no key boots (AC 1, 3).
T-7 pins test_configuration_settings_production_names.py: OPENAI rows move to the new keys; the six old names asserted unread; tests/unit/bin/test_bin_audit_env_names_classify.py: the six HINTS classify with their destination (AC 4, 6).
AC -> step -> test: #1 B2,B5,B6 / T-1,T-2,T-5,T-6 ; #2 B10 / G1 ; #3 B2,B3,B4 / T-2,T-3,T-4,T-6 ; #4 B2,B8,B9 / T-1,T-7 ; #5 gates ; #6 B9,B10 / T-7 + G1 ; #7 B6 / T-5.

== Assumptions and doubts ==
(a) The OPENAI_API_KEY blob line is in sre-bot-config and /sre-bot/OPENAI__API_KEY holds its value: pre openai decides; put-parameter first if DIFFER or MISSING.
(b) The dotenv source with env_prefix OPENAI__ ignores OPENAI_API_KEY in .env under extra=forbid (as AWS): T-1.
(c) local.toml names the tenant, so every development boot needs OPENAI__API_KEY: the Codespaces secret must exist before merge (H1); a developer off Codespaces sets it in app/.env.
(d) An error-code registry member fits "not configured" (B3); otherwise reuse the one comms uses (TEXT_GENERATION_UNAVAILABLE) through the registry, no new string literal.
(e) Production uses no OPENAI_* tuning value: pins and pre's blob_where confirm.

== Blast radius and rollback ==
Boot: a malformed [openai] or a half-configured tenant now fails boot; the circuit breaker rolls back and the old tasks keep serving. pre openai MATCH and the files test guard it. Runtime: only incident text generation (comms drafts fall back to hand-written; scribe reports not configured). One git revert plus build_and_deploy with the pre image_tag restores; the previous image reads the unchanged OPENAI_API_KEY blob line (kept until 111.15).

== Merge gates (human) ==
G1 zsh bin/deploy-checks.zsh pre openai from this branch: MATCH, no tuning lines; rerun pre at merge for the rollback image_tag.
G2 Gates from app/: ruff, mypy (no new errors in touched files), pytest tests --ignore=tests/smoke, make check-import-contracts, make check-settings-key-ownership.
H1 Codespaces secret OPENAI__API_KEY (the current OPENAI_API_KEY value); app/.env.example OpenAI lines to OPENAI__API_KEY (agents are denied app/.env*); zsh bin/env-checks.zsh OPENAI_.

== Post-deploy ==
zsh bin/deploy-checks.zsh post openai PASS. Manual: in a test incident channel, draft a status update with AI (or run the scribe summary) and confirm a draft comes back; post's openai_summarize_usage count then rises. Rollback on FAIL: build_and_deploy with image_tag=<pre tag> (docs/runbooks/roll-back-a-deployment.md), then revert.

== Cleanup (after PASS) ==
Codespaces: gh secret delete OPENAI_API_KEY --app codespaces -R cds-snc/sre-bot (and any OPENAI_* tuning secret env-checks lists); Actions: none expected (ci_code.yml reads none; env-checks confirms). SSM: the blob line goes with the blobs in 111.15.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Plan approved 2026-10-27 (human). Implemented 2026-10-27 in the working tree from main 903eed3f: [openai] tuning in base.toml; optional [openai.tenant] (base_url https or loopback http, model) in production.toml and local.toml; OPENAI__API_KEY on the slice (SecretStr, empty = unset); a tenant without the key or the key without a tenant fails boot naming OPENAI__API_KEY; get_openai_settings() in the boot validation list; summarizer returns CONFIG_NOT_CONFIGURED without a client when no tenant; comms adapter keys its fallback on the tenant (ValidationError branch removed); HINTS for the six old names; deploy-checks openai pre and post; doc-14, configuration.md, scribe README. Shipped with this PR: the 2026-10-27 ADR amendments (one vendor shape; required dependencies abort boot) and the TASK-172, TASK-173, TASK-126, TASK-25.10 and TASK-145.7 task changes. Gates: ruff clean; mypy 47 errors = baseline, none in touched files; pytest 5917 passed; contracts 13 kept; key ownership OK; env coverage lists OPENAI__API_KEY supplied everywhere (no rule change). The OPENAI_API_KEY line sits in sre-bot-config-infrastructure per doc-14, not sre-bot-config; pre openai searches both blobs. ACs 1, 3-7 checked; AC 2 waits on pre openai.
<!-- SECTION:NOTES:END -->
