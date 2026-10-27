---
id: TASK-111.10.3
title: Give each Google document id its own key; GOOGLE_RESOURCES is no longer read
status: To Do
assignee: []
created_date: '2026-10-26T18:55:00Z'
updated_date: '2026-10-27T14:45:00Z'
labels:
  - configuration
  - security
milestone: m-7
dependencies:
  - TASK-111.10.2
  - TASK-167
references:
  - decisions/configuration.md
parent_task_id: TASK-111.10
type: feature
ordinal: 448000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
GOOGLE_RESOURCES packs the incident, talent, AWS spending and calendar ids into one JSON value, a workaround for the SSM parameter size limit that no longer applies. Each id becomes its own key, never one JSON again. The ids are Drive and calendar item ids: non-public values (decisions/configuration.md, 2026-10-26), never in the public configuration files. Where each id's key lives and how its value is supplied follow TASK-167's ruling on document ids (deployment configuration through the secret pipe, or organisation content with its own source), so the incident, talent and AWS carriers (TASK-145.6, 145.7, 145.10, 145.12, 39, 88) and TASK-158 inherit it without a second move where possible. incident_drive_id and the blob's rep.g are unread and not carried. The GOOGLE_RESOURCES blob line stays for the rollback image until TASK-111.15.2. Plan written after TASK-167 rules. Split from TASK-111.10 on 2026-10-26.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GoogleResourcesConfig (or its replacement per TASK-167) reads one key per id, supplied as TASK-167 rules; GOOGLE_RESOURCES is no longer read; incident_drive_id is deleted and rep.g is not carried
- [ ] #2 No configuration file holds a Drive, document, sheet or calendar id
- [ ] #3 Each production value equals the id in the sre-bot-config GOOGLE_RESOURCES line it replaces (compared without printing it)
- [ ] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [ ] #5 /sre incident product list opens a loading modal before the Drive read and fills it with views.update, so a cold Google call no longer outlasts Slack's 3-second trigger_id (expired_trigger_id seen after the 111.10.1 deploy)
- [ ] #6 A present Google tenant entry's GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY is shape-checked at boot with no network call (decisions/configuration.md: a present entry requires its secrets and is shape-checked at boot): it parses as strict JSON with type service_account, and google.oauth2.service_account.Credentials.from_service_account_info builds the credentials, which validates client_email, token_uri and the private key locally. Malformed JSON (a private_key with literal newlines, seen in a Codespaces secret 2026-10-27), a missing field or an unreadable key fails boot naming the variable, never its value. The parsed credentials are built once and reused by the client, not re-parsed per call; a test runs the check with sockets disabled
- [ ] #7 No token is fetched and no Google API is called at boot: a revoked key, a key whose project was deleted, or a missing domain-wide delegation still surfaces at first use, as a logged error naming the cause (the token endpoint's error code) and a stable user-facing message, never the raw exception text or a credential
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-27T14:45:00Z

---

2026-10-27 (human: avoid the invalid-credentials error at first use without network calls for no reason). Added AC #6 and #7. Validation is split at the network boundary. Offline checks (JSON shape, required fields, the RSA key loading into a signer, all local in google-auth's _service_account_info.from_dict) run at boot and fail fast. Checks that need Google (token exchange, delegation, API enablement) stay lazy at first use, so boot and the health checks stay static (decisions/health-checks.md: every health check is static; decisions/configuration.md: shape-checked at boot with no network call). Found when /dev-sre incident product list failed with 'Invalid control character at line 5 col 48': the development secret had real newlines inside private_key.

---
<!-- COMMENTS:END -->
