---
id: TASK-111.11.2
title: Move the OpenAI slice onto the files; the key is OPENAI__API_KEY
status: To Do
assignee: []
created_date: '2026-10-26T22:21:00Z'
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
OpenAISettings (integrations/openai/settings.py) becomes the [openai] ConfigurationSlice (extra=forbid, no aliases): model, max_output_tokens, temperature, timeout_seconds and base_url come from base.toml (the code defaults, which production uses today: it sets none of them); api_key is the secret OPENAI__API_KEY, the SSM SecureString /sre-bot/OPENAI__API_KEY that TASK-111.4 already creates and injects (no terraform expand is needed; its value is set outside terraform from the OPENAI_API_KEY line of sre-bot-config-infrastructure). A missing or empty key still leaves text generation unavailable rather than failing boot. OPENAI_API_KEY and the OPENAI_* names are no longer read; the blob line stays inert until TASK-111.15. Split from TASK-111.11 on 2026-10-26.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The OpenAI slice reads model, max_output_tokens, temperature, timeout_seconds and base_url from [openai] and the key only as OPENAI__API_KEY (hidden in repr and logs); an empty key counts as unset; an unknown key in [openai] fails the slice naming the key
- [ ] #2 /sre-bot/OPENAI__API_KEY equals the OPENAI_API_KEY line it replaces (pre openai: MATCH, compared by hash, never printed)
- [ ] #3 With no key, incident text generation is reported unavailable exactly as today and no message or log line carries a key value
- [ ] #4 OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MAX_OUTPUT_TOKENS, OPENAI_TEMPERATURE, OPENAI_TIMEOUT_SECONDS and OPENAI_BASE_URL are no longer read from the environment or .env
- [ ] #5 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass; make check-import-contracts and make check-settings-key-ownership pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Deployed; zsh bin/deploy-checks.zsh post openai PASS and the manual check recorded
<!-- DOD:END -->
