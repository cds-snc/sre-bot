---
id: TASK-157
title: >-
  Slack inbound tenant guard: check every request's enterprise and team against
  the configured Slack tenant; optional [slack.tenant] enterprise_id
status: Done
assignee: []
created_date: 2026-10-20 18:35
updated_date: '2026-11-04T18:46:00Z'
labels:
  - security
  - slack
  - phase-4
dependencies:
  - TASK-111.9
references:
  - decisions/workplace-systems.md
  - decisions/transport-slack.md
  - decisions/configuration.md
  - https://docs.slack.dev/enterprise/developing-for-enterprise-orgs
  - https://openid.net/specs/openid-connect-core-1_0.html
  - https://github.com/cds-snc/sre-bot/issues/1758
ordinal: 406000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Standalone PR from main (doc-2: a security behaviour change merges and deploys alone), after TASK-111.9. Rules: decisions/workplace-systems.md rules 3 and 4, transport-slack.md (Verification), configuration.md.

WHY. The [slack.tenant] entry is the expected tenant, the single-tenant pattern of an OpenID Connect client that configures its issuer and rejects tokens from any other (OIDC Core 5.7). Nothing checks it yet: no Bolt middleware compares a request's team or enterprise with it (server/configured_systems.py:45 only reads the entry; integrations/slack/settings.py:10 leaves the per-request check to this task), so a wrong value is stamped onto references and makes IncidentStore.find_by_conversation miss silently. Nothing persists a tenant yet, so the check must land before the first persisting writers: TASK-145.5.7 (upgrade job, apply) and TASK-145.7 (declare writers).

WHAT
- integrations/slack/settings.py SlackTenant: an optional enterprise_id beside team_id in [slack.tenant] (env SLACK__TENANT__ENTERPRISE_ID), Slack's Enterprise org id; team_id becomes optional and the entry needs team_id or enterprise_id (an org-wide install has no workspace); same blank and opaque-id rules as team_id. tenant_id is the enterprise id when set, otherwise the team id (Slack advises keying org data by enterprise_id); server/configured_systems.py slack_tenant reads tenant_id and does not change. Docstrings and field descriptions say the ids are verified per request.
- The transport switched on ([slack_transport] enabled, TASK-112) requires the tenant entry through the cross-slice Slack rule in server/configuration/host_configuration.py; that rule accepts team_id, enterprise_id or both.
- Slack runtime (host code, after request verification): a global Bolt middleware compares the request's enterprise_id and team_id (Bolt context) with the configured ids. A configured id must match; a request naming an Enterprise org the settings do not name is refused. A mismatch acks where Slack requires an ack, answers a short ephemeral notice where a response URL exists, runs no listener, and logs slack_tenant_mismatch (error) with the expected and received ids. Boot makes no network call.
- No change to stored data: TASK-145.5.7 checks auth.test before apply.

OUT OF SCOPE. Re-stamping stored tenants after a Grid migration (a job planned when it happens; the guard refusing every request is its signal). Deriving the tenant from auth.test at boot (rejected: boot stays free of network calls, TASK-112).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 With [slack_transport] enabled, boot succeeds with [slack.tenant] team_id, enterprise_id, or both, and fails naming the keys with neither; blank values are rejected and no format is checked
- [x] #2 The configured Slack tenant (ConfiguredSystems.tenants()[SLACK]) is the enterprise id when [slack.tenant] enterprise_id is set, otherwise the team id
- [x] #3 Every inbound Slack request (command, action, view, event) whose enterprise_id or team_id does not match a configured id, or that names an Enterprise org the settings do not name, runs no listener, is acked where required, gets an ephemeral notice where a response URL exists, and logs slack_tenant_mismatch at error with the expected and received ids; a matching request passes unchanged
- [x] #4 decisions/transport-slack.md, workplace-systems.md and configuration.md match the shipped behaviour; the settings docstring states the per-request check
- [x] #5 ruff, lint-imports, mypy (no errors in touched files) and pytest tests --ignore=tests/smoke pass, with commands and output recorded in notes
- [x] #6 The guard compares Bolt's installation-scoped context ids (events: authorizations[0]; views: app_installed_team_id; interactions and commands: the payload team and enterprise), never user, actor, user_team or source_team ids: a Slack Connect event or interaction from an external user whose installation ids match passes; a configured team_id is compared only when set; a request with team null from an org-wide install passes when only enterprise_id is configured
- [x] #7 The refusal returns an explicit ack on every request type (commands, block actions, view submissions and closes, shortcuts, events; options requests get an empty options ack), a failing or slow ephemeral notice (2 s cap) never blocks the ack, the notice never names the expected ids, and url_verification and ssl_check are unaffected
- [x] #8 Readers of the now-optional team_id work with an enterprise-only tenant: modules/incident/core.py channel_url omits the team parameter, and the incident comms registration-skipped event names [slack.tenant]
- [x] #9 make check-import-contracts, make check-settings-key-ownership and python3 -m bin.generate_env_example --check pass, with commands and output recorded in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN APPROVED 2026-11-03 (human): OQ1 enforce, no flag; OQ2 no Slack Connect in production now or expected; OQ3 files key only; OQ4 generic pre/post plus smoke; OQ5 the notice is translated: catalogue keys in the core catalogue (app/locales/transport.en-US.yml and transport.fr-FR.yml, i18n.md: every user-facing string through a key), sent AFTER the ack on a guard-owned background executor so it can never delay the ack; the user's locale is used when the payload carries one, otherwise both languages are shown (Slack command and interaction payloads carry no locale, and the bot cannot look up a user of another tenant); OQ6 kept (absent id against a configured id is refused; an unconfigured team_id is not compared).

PLAN (planned 2026-11-03 against main 023aa1e5; one PR from main, security behaviour, merges and deploys alone; no terraform, SSM, task-definition or CI change)

SIZE AND GATE. Production: 6 code files + 1 TOML comment, about 150 LOC (settings.py ~25, new server/slack/tenant_guard.py ~100, lifespan ~4, host_configuration ~4, modules/incident/core.py ~2, comms entrypoint ~3, base.toml comment). Docs: 3 ADRs. One subsystem (Slack settings + Slack runtime). No mechanical refactor mixed in. Gate passes; no decomposition.

DESIGN DECISIONS (each assessed against the ADRs and doc-11/doc-15; none is reverted by a later row)
D1 Compare INSTALLATION-scoped ids, never the actor's. The "received" ids are Bolt's context.team_id / context.enterprise_id (Bolt 1.30.0 request/internals.py extract_team_id / extract_enterprise_id): events use authorizations[0] (Bolt comment: "to make Events API handling functioning also for shared channels"), view payloads use view.app_installed_team_id, interactions use payload team / enterprise ("the workspace the app is installed on. Null if the app is org-installed"), commands carry the executing workspace (only installing-workspace users can invoke them: Slack Connect doc). Never user.team_id, actor_team_id, actor_enterprise_id, event.user_team, source_team: those name an external Slack Connect user's org and would falsely refuse legitimate shared-channel traffic.
D2 Rule: a configured enterprise_id must equal the request's enterprise id; with no enterprise_id configured, a request naming an Enterprise org is refused; a configured team_id must equal the request's team id; an unconfigured team_id is not compared (org-wide installs carry team null / vary by workspace). An absent claim against a configured id is a mismatch. url_verification and ssl_check never reach the guard (Bolt answers them in built-in middleware ahead of custom middleware).
D3 Enforce, no log-only flag (see open question 1). Pure decision function + thin sync Bolt adapter so TASK-26.2 (runtime move) and any async port reuse the decision unchanged.
D4 [slack.tenant] enterprise_id is a files key (configuration.md 2026-10-22: [slack.tenant] holds ids only). production.toml and local.toml are NOT changed (enterprise_id absent = production's fact). No env-only field, so no .env.example, pyproject pytest-env blank, SSM, terraform or task-definition change. SLACK__TENANT__ENTERPRISE_ID works only as pydantic-settings' derived nested override, exactly like the existing SLACK__TENANT__TEAM_ID (test_configuration_settings_production_names.py:137); this PR does not declare it anywhere.

STEPS (TDD: failing tests first per step; ruff + targeted tests only while working)
1. integrations/slack/settings.py (:32-51 SlackTenant, :56-63 and :1-14 docstrings, :116-124 validator). team_id: str | None = None; add enterprise_id: str | None = None; one field_validator over both (strip, reject blank when provided, no format check); model_validator(after) requiring team_id or enterprise_id with a message naming both keys; tenant_id returns enterprise_id when set else team_id (return type str); field descriptions and module docstring say each id is verified against every inbound request (replace "are TASK-157's"). SlackSettings._tenant_and_secrets_go_together message (:123): "is set but [slack.tenant] is not". AC 1, 2.
2. server/configuration/host_configuration.py (:60 SlackKey.TEAM_ID, :126 rule). Rename the key value to "[slack.tenant] team_id or enterprise_id" (tests match the prefix r"\[slack.tenant\] team_id"); the rule itself stays "tenant is None" because an empty table already fails inside the slice. AC 1.
3. server/configured_systems.py:41-44: NO change (reads tenant_id). Add the enterprise-precedence test only. AC 2.
4. Other readers of the now-optional team_id (mypy would flag): modules/incident/core.py:29-31 channel_url builds app_redirect with tenant.team_id -> add the team param only when tenant.team_id is set (legacy file, one-line, behaviour unchanged for production). features/incident/comms/entrypoints/slack.py:23 and :134 name setting "[slack.tenant] team_id" in a startup event -> "[slack.tenant]"; tests/unit/features/incident/comms/test_incident_comms_status_update_slack.py:113 follows. jobs/scheduled_tasks.py:115 only tests tenant is not None: no change.
5. NEW server/slack/tenant_guard.py (host code; slack_bolt allowed under import contract (j); integrations.slack.settings import already used by server/configured_systems.py):
   - @dataclass(frozen=True) TenantMismatch(expected_team_id, expected_enterprise_id, received_team_id, received_enterprise_id, is_enterprise_install).
   - check_slack_tenant(tenant, *, team_id, enterprise_id) -> TenantMismatch | None (pure, D2).
   - build_slack_tenant_guard(tenant) -> sync Bolt middleware taking (body, context, ack, respond-free): on match return next(); on mismatch (a) log slack_tenant_mismatch at ERROR with expected and received ids, payload_type, command / event_type / callback_id / action_id, never the payload, tokens or user text; (b) if a response_url exists, submit the ephemeral notice to a guard-owned single-worker executor after the ack is built: text from the catalogue key transport.slack.tenant_mismatch (user locale when the payload has one, else en-US then fr-FR), posted through slack_sdk WebhookClient(response_url, timeout=2); a failing post is logged at warning (slack_tenant_notice_failed) and never touches the ack; (c) return the ack without calling next(): context.ack() for commands, actions, views, view_closed, shortcuts, events; context.ack(options=[]) for block_suggestion. Returning None without next() would make Bolt answer 404 and Socket Mode would send no envelope ack (adapter/socket_mode/internals.py send_response), so the explicit ack is mandatory. The notice never names the expected ids.
   - install_slack_tenant_guard(app, tenant) -> app.use(guard); raises if tenant is None (the transport on guarantees it via step 2).
   AC 3.
6. server/lifespan.py after :273 (slack_app = cast(App, ...)) and before the Socket Mode handler starts (:293): install_slack_tenant_guard(slack_app, get_slack_settings().tenant). Custom middleware appended after Bolt's built-ins (SslCheck, RequestVerification in HTTP mode, authorization, IgnoringSelfEvents, UrlVerification) so it runs after request verification and before listener matching, for every request type. Boot makes no network call (auth.test happens already in Bolt's App(...) construction, unchanged). AC 3.
7. app/config/base.toml:27 comment: name enterprise_id beside team_id. No key added. NEW app/locales/transport.en-US.yml and transport.fr-FR.yml (the notice key, same key set).
8. Docs: decisions/transport-slack.md (Verification, :31; Changes line at :81: add the installation-scoped rule, the Slack Connect reason, enforce-no-flag, translated notice after the ack, and the Sources read 2026-11-03), decisions/workplace-systems.md (rule 3, :45, and Changes), decisions/configuration.md (:63 / :131 line: enterprise_id is a files key in [slack.tenant]; the 2026-10-20 line names SLACK_ENTERPRISE_ID, now superseded). Do not edit archived doc-14. AC 4.
9. Row bookkeeping for the human: doc-11 row 10a (deploy outcome), 145.5.7 AC #7 and 145.7 need no change (they already read tenant_id / enterprise_id); no doc-15 row touches Slack tenants (grep clean), so no program-level conflict.

TEST MATRIX (app/tests only; docstrings state behaviour only)
- tests/unit/integrations/slack/test_slack_settings.py (extend) + new tests/unit/integrations/slack/test_slack_settings_tenant_entry.py: team only / enterprise only / both build the frozen entry; neither (empty [slack.tenant]) fails naming both keys; blank team_id or enterprise_id rejected; whitespace stripped; unknown key still forbidden; tenant_id is the enterprise id when both set, else the team id; SLACK__TENANT__ENTERPRISE_ID env override builds the entry (mirrors the team test); secret set without tenant message. (AC 1, 2)
- tests/unit/server/configuration/test_server_configuration_slack_transport_rules.py (extend): transport on with enterprise only passes; with neither fails naming "team_id or enterprise_id". (AC 1)
- tests/unit/server/test_server_configured_systems_read.py (extend): enterprise id wins; team only unchanged (this is the "enterprise-id tenant test" row 9.9b.1 deferred to 157). (AC 2)
- NEW tests/unit/server/slack/test_server_slack_tenant_guard_verdict.py: pure rule table (match team, match enterprise, both, team mismatch, enterprise mismatch, enterprise unconfigured but named, org-wide request with team null and enterprise-only config passes, absent claim against configured id refused, unconfigured team not compared). (AC 3)
- NEW tests/unit/server/slack/test_server_slack_tenant_guard_dispatch.py on a real Bolt App (tests/factories/slack_bolt.py: unpatched_app_init, authorize_single_workspace, InlineExecutor; extend the factory only if it lacks a command/event/options dispatch): per request type command, block_actions, view_submission, view_closed, message shortcut, block_suggestion, event_callback: mismatch runs no listener, returns HTTP 200 ack (options body for block_suggestion), one slack_tenant_mismatch ERROR with expected and received ids and no token or text; notice posted to response_url when present (WebhookClient stubbed) and none when absent; notice raising still acks; match passes to the listener with unchanged args; event whose user_team / source_team is an external org but authorizations[0] matches the installation PASSES (Slack Connect case); url_verification and ssl_check unaffected. (AC 3, 6, 7)
- tests/modules/incident/test_incident_core.py (extend): channel_url with an enterprise-only tenant omits the team parameter; with team_id unchanged. (AC 8)
- tests/unit/features/incident/comms/test_incident_comms_status_update_slack.py:113 update. 
- Wiring: a test that install_slack_tenant_guard on the app built through LegacySlackBootstrap.create_app refuses a mismatching request (tests/unit/integrations/slack/test_slack_bootstrap.py pattern), and a lifespan-level assertion in the nearest existing lifespan Slack test that the guard is installed before the handler starts. (AC 3)

AC TRACEABILITY. 1: steps 1,2 / settings, transport-rules tests. 2: step 1,3 / settings, configured-systems tests. 3: steps 5,6 / verdict + dispatch + wiring tests. 4: step 8 / review of the three ADRs. 5 and 9: verification step. 6, 7, 8: steps 5, 4. Every step maps to an AC or is enabling (4, 7, 9).

ASSUMPTIONS AND DOUBTS (verify before or during implementation)
A1 Slack interaction payload `team` / `enterprise` are installation-scoped (docs block_actions-payload) and not the external user's in Slack Connect channels; one third-party guide (Medium, raidboss) claims the initiating workspace's team id is sent. Verify: read Slack's current payload reference at implementation; the actor ids are excluded either way; the dispatch test pins the chosen fields. Residual risk is external users clicking buttons in a Slack Connect channel; mitigation is a documented, loud, single-revert failure.
A2 Production has no Slack Connect channels with the bot, or any other tenant: confirmed team T2G2S06PM, enterprise null, is_enterprise_install false (2026-10-20, G2 2026-10-23, production.toml:6, local.toml:7). Human can confirm with Slack admin before merge.
A3 Bolt 1.30.0 (uv.lock) semantics: a custom global middleware is appended after built-ins and may return context.ack() without next() (IgnoringSelfEvents is the precedent, middleware/ignoring_self_events). Verified in installed source; the dispatch test proves it on every request type.
A4 `ack` and `context` are injectable arguments of a function middleware (kwargs_injection/utils.py:51). Verified.
A5 `[slack.tenant]` unknown-key and ownership checks accept a new field without a TOML key: run make check-settings-key-ownership.
A6 generate_env_example lists env-only names only, so no .env.example change: run `cd app && python3 -m bin.generate_env_example --check`.

BLAST RADIUS AND ROLLBACK
Wrong guard = every Slack command, button, modal and event silently refused (health stays green, so the ECS circuit breaker does NOT trip); the signal is error-level slack_tenant_mismatch lines and users seeing the notice. One `git revert` restores service (no data, schema, config or infrastructure change). No ordering constraint: nothing to deploy first. Production values are already in production.toml and unchanged.
Deploy checks: run the standard `zsh bin/deploy-checks.zsh pre` at merge (rollback image tag, as for every merge) and `post` after deploy. No named task check and no new check is warranted: no terraform, task-definition, IAM, SSM or declared env name changes (enterprise_id is a files key; production.toml is untouched), and the generic post "runtime errors" section already FAILs on any level=error line, which includes slack_tenant_mismatch. Human smoke after deploy: run one slash command and one button/modal in the SRE test channel, and query Logs Insights for event = "slack_tenant_mismatch" (expect 0).
Blocks: TASK-145.5.7 and TASK-145.7 stay blocked until this is deployed and the smoke is clean.

VERIFICATION (end of work, once each, sequential, never parallel)
Targeted tests and `cd app && uv run ruff check .` during work. At the end: `cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'` (fix findings), then `cd app && uv run pytest tests --ignore=tests/smoke`, then `make check-import-contracts`, `make check-settings-key-ownership`, `cd app && python3 -m bin.generate_env_example --check`. Record commands and output in notes. Do not run tests/smoke.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-20 (TASK-24.5): the Slack tenant entry is SlackTenant (integrations/slack/settings.py), read through SlackSettings.tenant, with team_id and a tenant_id read. Add the optional enterprise_id inside it, make team_id optional, and make tenant_id the enterprise id when set; server/configured_systems.py already reads tenant_id and does not change. Production (2026-10-20): team T2G2S06PM, enterprise_id null, is_enterprise_install false, no SLACK_ENTERPRISE_ID set.

2026-11-03 (human) on the plan's open questions: OQ1 approved (enforce in this PR, no log-only flag); OQ2 no Slack Connect channel in production and none expected for now (assumption A1 stands; the installation-scoped rule stays as the safeguard); OQ3 approved (enterprise_id is a files key only, no new env name); OQ4 OK (no named deploy check; generic pre and post plus the manual Slack smoke test). Open: OQ5 (human: notices are translated whenever possible), OQ6 (context requested). Plan not yet approved.

Implemented 2026-11-03 on task-157-slack-tenant-guard (from main 023aa1e5), In Progress.
- integrations/slack/settings.py: SlackTenant team_id and enterprise_id both optional, at least one ('[slack.tenant] needs team_id or enterprise_id'), blank rejected, no format check; tenant_id = enterprise id when set, else team id; docstrings state the per-request check; secret-without-tenant message is '[slack.tenant] is not'. server/configured_systems.py unchanged. (AC #1, #2)
- server/configuration/host_configuration.py: SlackKey.TENANT '[slack.tenant] team_id or enterprise_id'. (AC #1)
- server/slack/tenant_guard.py (new): check_slack_tenant (pure), TenantMismatch, SlackTenantGuard (Bolt Middleware on context.team_id / context.enterprise_id, the installation-scoped ids), slack_tenant_mismatch at error with expected and received ids, is_enterprise_install, payload_type, command, event_type, callback_id, action_id (no text, no response URL); explicit ack (options=[] for block_suggestion); notice from the core catalogue key transport.slack.tenant_mismatch (app/locales/transport.en-US.yml, transport.fr-FR.yml), user locale when the payload has one, else both, posted through WebhookClient(timeout=2) on a single-worker executor, failure logged slack_tenant_notice_failed (warning); install_slack_tenant_guard fails closed without a tenant. server/lifespan.py installs it on the provider's App right after the app is available. (AC #3, #6, #7)
- Readers: modules/incident/core.py channel_url adds team only when team_id is set; incident comms skip event names '[slack.tenant]'. (AC #8)
- Docs: transport-slack.md Verification + Changes (installation-scoped ids, ack, translated notice off the ack path, no flag, sources 2026-11-03), workplace-systems.md rule 3 + Changes, configuration.md Slack credentials paragraph + Changes; base.toml [slack] comment. (AC #4)
- Tests: tests/unit/server/slack/test_server_slack_tenant_guard_verdict.py (10 rule cases), test_server_slack_tenant_guard_dispatch.py (real Bolt App; command, block_actions, view_submission, view_closed, message_action, block_suggestion, event: match passes, mismatch acked with no listener, one mismatch log without text, notice only with a response URL, failing notice still acks, Slack Connect event passes, url_verification unaffected, install without tenant fails), tests/integration/server/test_lifespan_slack_tenant_guard_install.py, settings/rule/configured-systems/channel_url tests extended; three lifespan tests stub the install, one regex follows the message. Mutation: guard always passing fails 19 dispatch tests.
- Gates (sequential): cd app && uv run ruff check . -> All checks passed!; ruff format --check -> 1097 files already formatted; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 41 errors in 14 files (pre-existing legacy files, none touched: same baseline as TASK-163); uv run pytest tests --ignore=tests/smoke -> 6106 passed; make check-import-contracts -> Contracts: 13 kept, 0 broken; make check-settings-key-ownership -> OK; uv run python -m bin.generate_env_example --check -> OK (39 names). (AC #5, #9)
After merge (human): zsh bin/deploy-checks.zsh pre at merge for the rollback tag, post after the deploy (runtime errors section fails on any slack_tenant_mismatch); smoke: one slash command and one button or modal in the SRE test channel; Logs Insights event = slack_tenant_mismatch expects 0.
Smoke test, spelled out (2026-11-03): in Slack, not curl (Socket Mode has no inbound HTTP endpoint). After the production deploy, in the SRE test channel: /sre help (production prefix is empty) answers as before, and one interactive element (a button or a modal) works; then Logs Insights on the sre-bot log group since the deploy: filter event = "slack_tenant_mismatch" returns 0 lines. Optional before merge: run the branch locally (local.toml names the same workspace T2G2S06PM, prefix dev-) and /dev-sre help answers.

2026-11-04 deploy (human report): #1817 merged 13:28 UTC as dc79aa33; build_and_deploy run 41838429008 success (build, sbom, deploy). bin/deploy-checks.zsh post, run 2026-11-04T17:54:49Z (tmp/deploy-checks/post-20261104T175449Z.txt): task-definition sre-bot-task:78, rolloutState COMPLETED 2/2, image tag dc79aa33b3779fc52e05a7a2cbf3172cf28bf3ee-2026-11-04 (digest sha256:75c724d8...); rollout PASS; boot_errors PASS; slack_up PASS (slack_app_initialized 2, socket session established 2); version PASS (/version = dc79aa33), health 200, root 200; non_json_lines WARN (4 known import-time lines: built_conditional_write_store debug, starlette TestClient noqa); runtime_errors FAIL (other=1 lost=0): one aws_identity_store_group_memberships_error at 17:31:36Z, an AWS Identity Store call, not the Slack guard, outside this task; Socket Mode reconnects 0. Task-definition names unchanged by this task (no new env name, OQ3). Slack smoke (human, 2026-11-04): clean: /sre help answered, a button or modal worked, slack_tenant_mismatch = 0 since the deploy. That settles TASK-145.5.7's D10: with the team_id-only [slack.tenant] entry, inbound requests carry no enterprise id that the guard refuses. All ACs were already checked; task stays In Progress for the human to close.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-03T21:27:00Z

---

Planning 2026-11-03 proposals for the human (no AC reworded or removed):
1. AC #3 says 'a request's enterprise_id or team_id'. Proposed reading, now AC #6: Bolt's installation-scoped context ids, not the acting user's (Slack Connect risk). Reword AC #3 only if you want the two merged.
2. AC #5 omits make check-import-contracts and make check-settings-key-ownership; AC #9 adds them instead of editing #5.
3. Description says env SLACK__TENANT__ENTERPRISE_ID. configuration.md (2026-10-22) puts [slack.tenant] ids in the files; the plan adds a files key only. The env name works only as pydantic-settings' derived nested override, like SLACK__TENANT__TEAM_ID today. Say so if you want it declared/blanked in pytest-env.
4. Enforce in one PR with no log-only flag (open question in the plan summary); the human decides.

---
<!-- COMMENTS:END -->
