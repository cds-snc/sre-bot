---
id: TASK-25.10.3
title: >-
  Move generation parameters out of the OpenAI vendor slice: default model in
  the text-generation capability, output budget and temperature per call
status: To Do
assignee: []
created_date: '2026-11-09T13:41:00Z'
updated_date: '2026-11-09T15:09:00Z'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.10.2
references:
  - decisions/configuration.md
  - decisions/plugin-architecture.md
  - decisions/plugins.md
  - app/integrations/openai/settings.py
  - app/config/base.toml
  - app/config/production.toml
  - app/config/local.toml
  - app/features/incident/scribe/settings.py
  - app/server/configuration/host_configuration.py
parent_task_id: TASK-25.10
priority: medium
ordinal: 494000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Third slice of TASK-25.10 (contract): TASK-25.10's ACs #7 and #8. The vendor slice keeps only the connection (configuration.md: a vendor slice holds endpoint, credential and transport tuning). Plan at pickup against main after 25.10.2 merges.

TODAY: OpenAISettings carries max_output_tokens (3000, the fallback when a caller passes none), temperature (-1.0, omitted when negative) and the tenant's model (production.toml:37-39 and local.toml:20-22, gpt-5.6-luna). Scribe's catch-up summary passes no budget, so it uses the vendor's 3000. Scribe's draft passes 4000 and comms 2000. scribe declares Requirement('openai.tenant').

TARGET:
- integrations/openai/settings.py: [openai] timeout_seconds and connect_retries (25.10.1); [openai.tenant] base_url only; OPENAI__API_KEY unchanged. max_output_tokens, temperature and tenant.model are deleted.
- capabilities/text_generation/settings.py (settings-singleton skill; the generator's settings template): [text_generation] model. production.toml and local.toml move model from [openai.tenant] to [text_generation] in the same PR. Production sends the same model.
- The Protocol's generate takes max_output_tokens as required and temperature: float | None = None, omitted from the request when None. No caller sets one, so production sends no temperature, as today.
- scribe's catch-up summary gains its own budget, INCIDENT_SUMMARY__MAX_OUTPUT_TOKENS default 3000, in IncidentSummarySettings (the file's existing form), so production sends the same.
- Where an unset model fails, ruled 2026-11-09 (human, OQ6): the model is the organisation's value (configuration.md:33, :87), so base.toml has [text_generation] model = '' (unset) and production.toml and local.toml set it. Unset, the capability reports unavailable through 25.10.2's no-op implementation and logs text_generation_model_unset once at build. A required consumer adds Requirement('text_generation.model') beside 'openai.tenant', resolved through the built slice (host_configuration.py builds it, plugins.md 2026-11-05), so boot names the missing key. Today that is scribe only, while it exists; response and postmortem declare no text-generation requirement (145.9/145.11 ruling, 2026-11-09). comms falls back.
- decisions/configuration.md drops the generation-parameters tolerance (line 116); plugin-architecture.md's Changes gains the date.

Blast radius: production.toml changes the configuration production boots with. A model left in [openai.tenant] fails boot (extra=forbid on the tenant), so the move is atomic in one PR, and one revert restores it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 OpenAISettings holds timeout_seconds, connect_retries, the tenant's base_url and the key only; an [openai] max_output_tokens or temperature key, or a model in [openai.tenant], fails boot; base.toml, production.toml and local.toml match
- [ ] #2 capabilities/text_generation/settings.py reads [text_generation] model; base.toml leaves it empty (unset: the organisation's value, configuration.md:87); production.toml and local.toml set it to the model they set before; the OpenAI adapter sends it
- [ ] #3 generate requires max_output_tokens and takes an optional temperature that is omitted from the request when unset; scribe's draft (4000), scribe's catch-up summary (new INCIDENT_SUMMARY__MAX_OUTPUT_TOKENS, 3000) and comms (2000) each pass their own budget, so production sends the same parameters as before
- [ ] #4 With the tenant set and the model unset, the capability reports unavailable (the no-op implementation, text_generation_model_unset logged once at build); scribe declares Requirement('text_generation.model') beside 'openai.tenant' and aborts boot naming text_generation.model; comms falls back to the hand-written form
- [ ] #5 decisions/configuration.md no longer tolerates generation parameters in the vendor slice; full gates plus make check-import-contracts, check-settings-key-ownership, check-package-shape and check-test-seams pass, with output in notes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-09 (25.10 review), Q6, where an unset model fails. The ADRs cover it, no gap. configuration.md:33 puts a capability's defaults in its own slice. configuration.md:87 says production.toml holds the deploying organisation's values, while base.toml stays the framework's. The gateway's model name is this organisation's choice, so it stays out of base.toml: base.toml has [text_generation] model = '' (unset), and production.toml and local.toml set it, as AC #7 reads. Spring AI does ship a library default (spring.ai.openai.chat.model = gpt-5-mini, docs.spring.io/spring-ai/reference/api/chat/openai-chat.html). That fits a framework that knows its vendor's catalogue, not a deployment-specific gateway. Unset model: the capability reports unavailable, through 25.10.2's no-op implementation, and logs text_generation_model_unset once at build. Required consumers add Requirement('text_generation.model') beside 'openai.tenant', resolved through the built slice (host_configuration.py, plugins.md 2026-11-05), so boot names the missing key (plugins.md: requirement is the consumer's). Production safety: production.toml and local.toml move the same model in the same PR. A model left under [openai.tenant] fails boot (extra=forbid), so the move cannot half-apply, and one revert restores it. Note: which plugins are 'required consumers' after scribe dissolves is open on TASK-145.9 and TASK-145.11 (2026-11-09).

2026-11-09 (human): OQ6 ruled as recommended: [text_generation] model empty in base.toml, set in production.toml and local.toml; unset means unavailable, plus Requirement('text_generation.model') for required consumers (scribe while it exists). Description and ACs #2 and #4 updated; the 'or the alternative ruled at plan' clause is gone.
<!-- SECTION:NOTES:END -->
