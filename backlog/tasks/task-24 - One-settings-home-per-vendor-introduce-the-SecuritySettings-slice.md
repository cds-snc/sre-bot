---
id: TASK-24
title: One settings home per vendor; introduce the SecuritySettings slice
status: Done
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-10-20 21:43'
labels:
  - clients
  - phase-3
  - configuration
milestone: m-3
dependencies: []
references:
  - decisions/configuration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1278'
  - decisions/plugin-architecture.md
priority: medium
ordinal: 24000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/configuration.md (Ownership). Today each vendor has two settings homes - integrations/<vendor>/settings.py (new) and infrastructure/configuration/integrations/<vendor>.py (old) - and no SecuritySettings slice exists; security config is split across AppSettings and ServerSettings.

Steps:
1. Per vendor: keep app/integrations/<vendor>/settings.py as the single home (credentials live with the client); migrate any fields only present in the old file; delete infrastructure/configuration/integrations/<vendor>.py; update consumers. Slack gets one slice: SLACK_ENABLED is defined once (it is the interim transport switch until TASK-112; SLACK_TEAM_ID is required when it is on) and the vendor-workspace meaning moves to the tenant entry. Google's customer id keeps no default: GOOGLE_WORKSPACE_CUSTOMER_ID no longer defaults to the my_customer alias, and a present tenant entry carries the real id (decisions/configuration.md, workplace-systems.md rule 3). No new <VENDOR>_ENABLED key.
2. Build app/infrastructure/security/settings.py as the SecuritySettings slice (allowed issuers/JWKS, CORS allow-list, dev-bypass flag and token) and move those fields off AppSettings and ServerSettings. No rate-limit backend field until a second backend exists (human, 2026-10-19).
3. Environment names: decisions/configuration.md records the rule (<SLICE>__<FIELD>, 2026-10-19, in TASK-24.1); the renames move to TASK-111, done once for the variables that remain after values move into files. One env var has exactly one owning class.
4. Fail fast: settings validate in lifespan's configuration phase (decisions/configuration.md, lifecycle.md phase 1), statically: presence and shape only, never a call to test a credential. A missing credential fails validation naming the variable; decisions/plugins.md decides the effect (a feature's slice skips that feature, a host or capability slice aborts boot).

Decomposed 2026-10-19 (size gate), one PR each:
- TASK-24.1 small vendors (Trello, MaxMind, Notify, OpsGenie, Sentinel), pure move, plus the ADR naming rule.
- TASK-24.2 SecuritySettings slice.
- TASK-24.3 Slack: delete the two dead Slack homes.
- TASK-24.4 Google move: after Stack K #1722, #1723 and #1728 merge (server/configured_systems.py imports the old path).
- TASK-24.5 Google and Slack tenant entries; delete the old package: after TASK-145.5.5 (Stack K layer 9) has deployed and been checked.
- TASK-24.6 single-owner CI check and the boot test.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 infrastructure/configuration/integrations/ no longer exists; each vendor has exactly one settings class
- [x] #2 A boot test shows a missing required credential fails with a message naming the env var
- [x] #3 CI/grep check: no env var read by two BaseSettings classes
- [x] #4 SecuritySettings owns issuers/JWKS, CORS and dev-bypass config and is consumed by the security stack
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 PR references decisions/configuration.md
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: task-planner
created: 2026-07-24 13:35
---
Cross-task note from TASK-2 planning (2026-07-24): TASK-2 lands CORS_ALLOWED_ORIGINS, CORS_ALLOWED_METHODS, CORS_ALLOWED_HEADERS plus a boot-time model_validator (rejects '*' with allow_credentials=True) on AppSettings (app/infrastructure/configuration/app.py) as an interim home, since this task (TASK-24 / SecuritySettings) had not landed yet. When this task is implemented, migrate those three fields and their boot validator from AppSettings into SecuritySettings (app/infrastructure/security/settings.py) rather than re-deriving the CORS policy/validator from scratch - this satisfies this task's existing AC #2 ('SecuritySettings owns issuers/JWKS, CORS, rate-limit, dev-bypass config...'). Update app/server/server.py's CORSMiddleware wiring and the corresponding tests (app/tests/unit/infrastructure/configuration/test_app_settings.py TestAppSettingsCors, app/tests/unit/server/test_server.py) to read from the new SecuritySettings location at that time.
---

created: 2026-09-24 20:10
---
2026-09-24 alignment with decisions/plugin-architecture.md and configuration.md: the SecuritySettings slice belongs to the security framework service, which moves to app/server/security/ (TASK-116, which depends on this task). Build the slice where security lives today, and TASK-116 carries it. Feature slices in app/infrastructure/configuration/features/ (atip, aws_ops, groups, incident, sre_ops) are not moved by this task: they move with their surface rebuilds (TASK-38, TASK-39, TASK-40, TASK-88; configuration.md: migration rides with the work). Moving them into frozen modules/ would widen legacy code. Values move into TOML files later (TASK-111, which depends on this task).
---

created: 2026-10-19 16:29
---
2026-10-19 (Stack K, TASK-145.5.9): app/server/configured_systems.py is a new consumer of both vendor slices. google_tenant reads GCP_SRE_SERVICE_ACCOUNT_KEY_FILE and GOOGLE_WORKSPACE_CUSTOMER_ID from infrastructure.configuration.integrations.google; slack_tenant reads TEAM_ID from integrations.slack.settings. It is wired through one TenantSource row per vendor. When the Google slice moves to integrations/<vendor>/settings.py and gains its tenant entry, update that row and its tests. Merge the Google and Slack slice after #1728 (Stack K layer 7), or rebase it onto main once #1728 has merged. The task trips the size gate (every vendor, SecuritySettings, namespaced env renames, a CI check): split it at planning.
---

created: 2026-10-19 17:19
---
2026-10-19 planning (human decisions): split into TASK-24.1 to 24.6 (option 1). Step 3 environment renames move to TASK-111 with DoD #1 (deployment env files updated for renamed variables); TASK-24.1 records the naming rule in decisions/configuration.md. AC #2 drops the rate-limit backend: the limiter is in-process with one backend. TASK-24.5 merges only after the Stack K layer 9 cutover (TASK-145.5.5) has deployed.
---
<!-- COMMENTS:END -->
