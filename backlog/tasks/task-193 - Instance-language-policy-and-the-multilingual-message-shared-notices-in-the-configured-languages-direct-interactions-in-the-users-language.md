---
id: TASK-193
title: >-
  Instance language policy and the multilingual message: shared notices in the
  configured languages, direct interactions in the user's language
status: Done
assignee: []
created_date: '2026-11-25T18:51:00Z'
updated_date: '2026-11-25T19:46:00Z'
labels:
  - i18n
  - platform
  - slack
dependencies: []
references:
  - decisions/i18n.md
  - decisions/platform-transports.md
  - decisions/product-scope.md
  - decisions/configuration.md
priority: medium
ordinal: 540000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Human 2026-11-25 (TASK-145.8.9 OQ2, D1-D6 approved; D3 clarified): translation (i18n.md), the instance's language policy and a platform's layout of a message in several languages are three concerns. Today the pair ("en-US", "fr-FR") and its English-first order are hard-coded in server/slack/tenant_guard.py:35, features/incident/response/entrypoints/slack_archive.py:41 and slack_show.py:72, and features join the lines with a newline before IncidentConversation.post(text: str), against platform-transports.md (outbound messages are intents each platform renders). The order and set are organisation policy: TBS Directive on Official Languages for Communications and Services 6.1.1 puts French first when the issuing office is in Quebec (this organisation's department HQ is, and a department move is pending); product-scope.md: an adopter may want English first or one language. D1: an ordered language list in the instance configuration (one or more catalogue locales), not an office location in code. D2: deployment-wide now, resolved through a contract that takes the conversation, so a per-tenant or per-conversation override needs no caller change. D3 (human): generic notices in shared conversations use the instance's languages and order; direct interactions (private replies, direct messages, views) use the user's language of choice (TBS: the interface in the language of the user's choice), not bounded by the instance list, falling back to the first configured language when the app has no catalogue for it; a request whose payload names no locale is answered in the instance's languages. D4: features hand over one text per language; each platform adapter lays it out (Slack: one message, top to bottom, as today; Teams later: one card, a text block per language; email: language-tagged parts, WCAG 3.1.2). D5: the default reproduces today (en-US then fr-FR); the production value is a separate config PR (human). D6: a new ADR for the language policy; i18n.md keeps translation; platform-transports.md gains the layout rule. One PR with no visible change (combined dark slices, size exception if needed); the visible change is TASK-145.8.9. doc-11 row 18.L6c.0.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A new ADR records the instance language policy (ordered list for shared and generic messages; direct interactions in the user's language of choice, matched on the primary language subtag, with fallback to the first configured language; payload without a locale answered in the instance languages; resolved per conversation through a contract; text the bot does not author keeps its source language; TBS 6.1.1 and the Welsh Language Standards cited as jurisdiction examples); i18n.md keeps translation only and points to it; platform-transports.md states that a multilingual message is an intent each platform lays out
- [x] #2 A typed instance setting holds the ordered language list, default en-US then fr-FR in app/config/base.toml; boot fails on an empty list, a duplicate or a locale the app does not support
- [x] #3 A language-policy contract in app/contracts/ answers the languages of a shared post to a conversation and the reply language for a user's locale; features and server code reach it only through the contract
- [x] #4 A platform-neutral multilingual message (ordered locale and text pairs) is accepted by IncidentConversation.post alongside plain text; the Slack adapter and the in-memory fake lay it out; Slack output for the default setting is identical to today
- [x] #5 The update modal's field notice, the archive button's notices and replies, and the Slack tenant guard's notice read the policy and use the multilingual message; no locale tuple remains in features/ or server/
- [x] #6 With the default setting every existing pin and test passes unchanged; tests with a one-language setting and a French-first setting show the set and order follow configuration; a regional or unsupported user locale is answered in a matched or the first configured language, never a raw key
- [x] #7 ruff, mypy (no new errors in touched files), make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
APPROVED 2026-11-25 (human: as recommended, OQ4 and OQ10 included; OQ9 one PR). Planned against main 69be8f12. Human rulings D1-D6 (description) are inputs, not open questions.

Goal: the instance's language policy becomes configuration behind a contract, and a message in several languages becomes a platform-neutral value each platform lays out. Every surface that hard-codes ("en-US", "fr-FR") today moves onto it. With the default setting nothing a user sees changes except the OQ4 fix (regional or unsupported Slack languages get real text instead of raw keys); TASK-145.8.9 then makes the status, roles and close notices follow it.

Current state (survey, path:line)
- Hard-coded pair and order: server/slack/tenant_guard.py:35 NOTICE_LOCALES (private reply to response_url, :68-80, :117-121; one locale when the payload names a supported one, else both); features/incident/response/entrypoints/slack_show.py:72 _BOTH (field notice :297-303 posted to the channel through change_status / update_fields; private replies :347-409, _locales :402-405 falls back to both when the view carries no locale); slack_archive.py:41 _NO_LOCALE (button: notices :145-146 posted by service/archive.py:95; refusals and stage lines :123-129 private). Out of scope: integrations/slack/users.py:173 and provider.py:928 (supported-locale lists for the users.info lookup, TASK-118), modules/incident/incident_conversation.py:383 (legacy, deleted by TASK-145.13).
- Composition in features: lines joined with "\n" (slack_show.py:303, :409; slack_archive.py:195), then IncidentConversation.post(conversation, text: str, *, blocks=()) (core/api.py:242-249; Slack adapter core/adapters/slack.py:401-421 chat_postMessage; fake core/adapters/in_memory.py:663-680). Against platform-transports.md:42 (outbound messages are intents each platform renders).
- Host slice pattern: server/slack/settings.py:19-38 (ConfigurationSlice, toml_table_header, env_prefix, lru_cache provider); validated in server/configuration/host_configuration.py:221-266 _validate_slices, static only (configuration.md:71). Catalogues load later (server/lifespan.py:255).
- Host service pattern: contracts/workplace/configured_systems.py:15 Protocol -> server/configured_systems.py:22 -> server/services.py:57/:71 CoreService -> features resolve with services.get(...) inside scopes.create_scope() (features/incident/response/entrypoints/scope.py:14-23).
- Import rules (pyproject.toml importlinter): features may import contracts, never server/infrastructure (b) except listed ignores; entrypoints cannot import integrations (e); contracts import nothing from the app (c).

Steps
1. ADRs (ride with the code; AC #1)
   - New decisions/languages.md "Instance languages" (Accepted in the PR): context (three concerns; TBS Directive on Official Languages for Communications and Services 6.1.1 French first when the issuing office is in Quebec, otherwise English first; Welsh Language Standards: Welsh placed to be read first on signs, no order for social posts; GC Notify offers English-first and French-first bilingual templates; Django LANGUAGES / Rails available_locales keep the language list in deployment configuration). Decision: [languages] shared is an ordered list of supported locales, one or more; shared and generic messages (a post to a shared conversation, a notice for many readers) use it in its order; direct interactions (private replies, direct messages, views) use the user's language of choice, matched to a supported locale (RFC 4647 lookup, OQ4), else the first configured language; a request whose payload names no locale is answered in the instance languages; features ask through the LanguagePolicy contract, which takes the conversation so a per-tenant or per-conversation rule needs no caller change; a message in several languages is a MultilingualText each platform lays out. Checks: no locale tuple in features/ or server/; base.toml carries the default. Migration: plain-text post accepted until TASK-145.13 (OQ5).
   - decisions/i18n.md: Decision's Locale resolution keeps request locale resolution; its shared-conversation, no-locale and TBS sentences move to languages.md (one pointer line); Changes line.
   - decisions/platform-transports.md "Outbound messages are intents": a multilingual message is one intent; the platform lays it out (Slack: one message, top to bottom; Teams: a card with a text block per language; email: language-tagged parts, WCAG 3.1.2); plain_text() is the common fallback. Changes line.
   - decisions/configuration.md: [languages] in the host slices list (:41/:79 area); Changes line.
2. Contract (AC #3, #4): contracts/i18n/languages.py
   - @dataclass(frozen=True) MultilingualText: parts: tuple[tuple[str, str], ...] (locale, text), non-empty, no duplicate locale; classmethod of(languages: Sequence[str], line: Callable[[str], str]); plain_text() -> "\n".join of texts in order.
   - Protocol LanguagePolicy: shared_languages(*, system: WorkplaceSystem, tenant: str, conversation_id: str) -> tuple[str, ...]; reply_languages(user_locale: str | None) -> tuple[str, ...] (None or blank: the shared order; a supported or matched locale: that one; otherwise the first configured).
   - contracts/i18n/__init__.py exports.
3. Host (AC #2, #3): server/languages/settings.py LanguageSettings(ConfigurationSlice) table [languages], env LANGUAGES__, field shared: list[str] default ["en-US", "fr-FR"], validator: non-empty, no duplicates, each in the supported set (infrastructure.i18n Locale values; OQ3); get_language_settings() lru_cache. server/languages/policy.py ConfiguredLanguagePolicy (frozen, from the settings; RFC 4647 lookup on the primary subtag). host_configuration.py _validate_slices calls it; HostConfiguration carries it. server/services.py CoreService(LanguagePolicy, _build_language_policy). app/config/base.toml [languages] shared = ["en-US", "fr-FR"].
4. Tenant guard (AC #5): tenant_guard.py NOTICE_LOCALES deleted; _notice_text uses the policy's reply_languages(payload locale) and MultilingualText.plain_text(); the guard receives the policy where it is built (host code, no service scope).
5. Incident conversation (AC #4): core/api.py post(conversation, text: str | MultilingualText, *, blocks=()); Slack adapter sends text.plain_text() when given a MultilingualText; fake stores plain_text() (posts unchanged) and keeps the value for assertions; parity suite case. Services that pass notices through widen their parameter type only: response/service/status.py (notice), fields.py (notice), archive.py (status_notice, archived_notice), roles.py announce return type.
6. Response entry points (AC #5): entrypoints/scope.py gains language_policy(scopes) (services.get(LanguagePolicy)); slack_show.py: _BOTH deleted; the field notice is MultilingualText.of(policy.shared_languages(...), line); private replies use policy.reply_languages(metadata locale or payload.user_locale). slack_archive.py: _NO_LOCALE deleted; _archive takes the notice languages (button: policy.shared_languages; command: (payload.user_locale,) unchanged here, switched by TASK-145.8.9); button refusals and stage lines use policy.reply_languages(None).
7. Tests first (red), then steps 2-6:
   - tests/unit/server/languages/test_server_languages_settings_validate.py: default; empty, duplicate, unsupported locale each fail with a SettingError naming LANGUAGES__SHARED; one-language and French-first accepted.
   - tests/unit/server/languages/test_server_languages_policy_resolve.py: shared order as configured; reply: supported locale -> itself (fr-FR in an en-US-only instance gets fr-FR, D3); None/blank -> shared order; en-GB -> en-US, fr-CA -> fr-FR (OQ4); unsupported (es-ES) -> first configured.
   - tests/unit/contracts/test_contracts_multilingual_text_render.py: of() keeps order; plain_text joins lines; empty and duplicate locale rejected.
   - tests/unit/features/incident/core/ (Slack adapter and fake post parity): a MultilingualText is posted as its plain text.
   - test_incident_response_show_entrypoint.py, test_incident_response_archive_entrypoint.py, test_server_slack_tenant_guard_dispatch.py: new cases with a French-first and a one-language policy (order and set follow configuration); existing cases unchanged with the default (AC #6). Fixture edits only where a scope must now provide LanguagePolicy (a fake at the Protocol seam, testing.md).
   - Unchanged and must pass: legacy pins test_incident_field_update_surface.py, test_incident_channel_archive_surface.py; status/roles/close tests (single-locale until TASK-145.8.9).
8. Docs: features/incident/response/README.md (notices and no-locale replies follow the instance languages); server README if one lists host services.

AC -> step -> test
- #1 -> step 1 -> review (ADR Checks).
- #2 -> step 3 -> settings_validate tests; check-settings-key-ownership (new table in base.toml).
- #3 -> steps 2-3, 6 -> policy_resolve tests; import contracts (features import contracts.i18n only).
- #4 -> steps 2, 5 -> multilingual_text_render, adapter/fake parity, unchanged pins.
- #5 -> steps 4, 6 -> rg ("en-US", "fr-FR") in features/ and server/ returns nothing; tenant guard and entrypoint tests.
- #6 -> step 7 -> full pytest with the default; French-first and one-language cases.
- #7 -> gates (ruff, make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams, check-fake-coverage if it lists contract Protocols; mypy then pytest once each at the end).

Test matrix: happy (default reproduces today on every surface); configuration (French-first, one language); boundary (no locale, blank locale, region variant, unsupported locale); failure (invalid setting fails boot with the env name, no value echoed); authorization and idempotency not applicable (no new path).

Domain-model gate: no entity changes. MultilingualText is a value type at an outbound boundary (frozen dataclass, type-model-boundaries). Scenarios: an English-only adopter (one part, no French catalogue read for shared posts, French user still answered in French); this organisation French-first after the production config PR; a Teams adapter laying out the same value as a card; a per-conversation override (D2) added inside the policy without caller change; coordinated incidents (doc-15) posting to several conversations, each asking the policy.

Size: production ~270 LOC over ~17 files (contracts 2, server 6, config 1, incident core 3, response services 4, response entrypoints 3) plus 4 ADRs and ~10 test files. Over the ~10 file gate; two subsystems (host i18n/Slack and incident). No visible change (combined dark slices rule): one PR under a size exception (OQ9, human: one PR).

Blast radius and rollback: with the default, none visible. Risks: boot fails on an invalid [languages] value (configuration phase, before traffic; the deploy circuit breaker rolls back, TASK-111.16); a scope missing LanguagePolicy fails the show modal or the archive button at runtime (covered by dispatch tests). One git revert restores today. The production value is a separate config PR (human).

Open questions, re-assessed 2026-11-25 at program scope (human request): decisions/, doc-11, doc-15, doc-16, doc-17, prior and upcoming tasks. Most were already settled by the human rulings D1-D6 or by an ADR; they are listed as settled with their source, not asked again.

Settled (no human decision needed)
- OQ1 Contract inputs. Settled by D2 (the policy takes the conversation) and workplace-systems.md rule 4 (a reference carries system and tenant with the vendor id). contracts/ has no conversation type and may import nothing from features (plugin-architecture.md:48, importlinter (c)), so the keyword arguments (system, tenant, conversation_id) are the rule applied, not a choice. TASK-125 (notifications capability) will define its own target type in its api.py; a later shared reference type, if any, is that task's question.
- OQ2 Message value and layout. Settled by D4 and platform-transports.md:42 (an intent, each platform renders it). Entry points cannot import integrations (importlinter (e)), so plain_text() on the contract value is the only fallback they can reach; per-platform layouts stay with adapters. Upcoming intents compose it, no conflict: TASK-125 (notifications intent) and the webhooks intents TASK-168 re-cuts (TASK-37.3: NotificationRequested(title, summary, ...)) carry MultilingualText for the bot's own wording. Task edits: comments on 125 and 168.
- OQ3 Validating the list. Settled by configuration.md:71 (configuration phase, static checks only) and dependency-injection.md:26 (boot validation is construction plus static validation of the slice, no I/O): validate against the supported locale set, which the parity gate (i18n.md:29) keeps complete. AC #2 wording aligned: "a locale the app does not support".
- OQ5 Plain-text post kept until the contract step. Settled by the expand/migrate/contract rule (incident-management.md Migration; delivery-session skill). The contract owner is TASK-145.13, which already closes the incident umbrella; it gains the AC "IncidentConversation.post takes MultilingualText only".
- OQ6 How features reach the policy. Settled by dependency-injection.md:24 (the host registers one factory per contracts Protocol) and :32 (Slack handlers resolve in create_scope()); ConfiguredSystems is the precedent. The tenant guard is host code built at the transport phase and receives the policy at construction (construction lives in provider layers, CLAUDE.md).
- OQ7 Setting name. Settled by D1 as approved: [languages] shared.
- OQ8 Task edits. Follow from D1-D6 and the items above (list below).
- OQ9 Size. Decided by the human: one PR (size exception, ~17 files).

Still open (gap found; recommendation)
- OQ4 Matching a user's language to a supported one. ADR: i18n.md:31 takes the locale from the platform signal and has no matching rule; D3 says the user's language of choice. GAP, and a live bug: infrastructure/i18n/factory.py:94-115 t() calls Locale.from_string, which raises for anything but en-US and fr-FR, and returns the fallback, which the response entry points set to the key itself; so a user whose Slack language is English (UK) or Spanish sees raw keys such as incident_response.status.notice in replies today. Slack sends the client language as an IETF tag (https://docs.slack.dev/changelog/2017/09/01/locale-locale-locale, https://api.slack.com/start/localizing); Teams, which workplace-systems.md plans beside Slack, sends activity.locale as language plus region (for example en-CA, fr-CA; https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-connector-api-reference). Practice: RFC 4647 lookup truncates the tag to its primary language before falling back (https://www.rfc-editor.org/rfc/rfc4647#section-3.4); Django's get_supported_language_variant does the same (https://docs.djangoproject.com/en/5.2/ref/utils/#django.utils.translation.get_supported_language_variant). Recommend: the policy's reply_languages matches the primary subtag (en-GB, en-CA -> en-US; fr-CA -> fr-FR), else the first configured language; languages.md records it. Visible change, a fix: users with a regional or unsupported Slack language get real text instead of raw keys, listed in the PR body and the user announcement. Upcoming: TASK-118 keeps the translator's own fallback; the policy decides the language before the translator is called. Alternative: exact match only (keeps the raw-key bug for those users until TASK-118).
- OQ10 (new) Text the bot does not author. ADR: i18n.md:21 covers the bot's own strings; migration.md step 2 pins sender-supplied content forwarded unchanged; nothing says what language forwarded or generated text is in (gap). Cases: webhook alert content from AWS or other senders (TASK-168, 37.x), messages captured into the timeline (145.9.x), AI-written summaries and drafts (ai_writing, scribe; TASK-140.6 asks the human for EN and FR fields). Practice: localisation frameworks translate only the product's own resources; user and third-party content keeps its language, marked when known (W3C Internationalization, "Language tags in HTML and XML", https://www.w3.org/International/articles/language-tags/). Recommend: languages.md states that MultilingualText carries the bot's catalogue wording only; forwarded and generated content keeps its source language, placed once beside the bot's lines (not duplicated per language); AI-written text follows its own task's rule (140.6: the human edits both). Task edits: comments on 168 and 125. No code in this task.

Task edits applied after approval: 193 AC #2 wording (OQ3); 145.13 new AC (OQ5); comments on 145.8.9 (re-plan on the contract), 145.7.10 (DeclareTexts shared posts as MultilingualText; locale toggle drives views and private replies), 145.9.2 (stale notice and ignore reply through the policy), 145.10 (D6 "English first line" superseded by the instance order; M3/M4 posts through the contract; doc-17 noted at the next Stack M session), 192, 165 (doc-15 posts through the contract), 140.6 (copy-ready text ordered by the instance list), 118 (translator keeps translation; integrations/slack supported-locale lists move with it), 125 and 168 (intents carry MultilingualText for the bot's wording; forwarded content keeps its language, OQ10).

Human after merge: decide the production order (issuing office in Quebec today: TBS 6.1.1 French first; department move pending) and say so; the agent prepares the one-line app/config/production.toml PR. Visible to every bilingual notice once applied.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-11-25 against main 69be8f12 (working tree on stack-l/task-145.8.3-show-update, identical tree; the human moves it to task-193-instance-languages from main).

What changed
- contracts/languages.py: LanguagePolicy Protocol (shared_languages(system, tenant, conversation_id), reply_languages(user_locale)) and MultilingualText (ordered language/text parts, of(), plain_text()). Path differs from the plan's contracts/i18n/languages.py: tests/unit/contracts/i18n pins contracts.i18n to standard-library imports, and the policy needs WorkplaceSystem; a module of its own also matches D6 (policy is not translation).
- server/languages/: [languages] shared slice (default en-US then fr-FR; empty, repeated or unsupported entries fail with ConfigurationError, checked against infrastructure.i18n Locale), ConfiguredLanguagePolicy (exact match, then primary-subtag match per RFC 4647, else the first configured language; no locale: the instance languages). Validated in host_configuration._validate_slices; registered as a CoreService in server/services.py; app/config/base.toml [languages].
- server/slack/tenant_guard.py: NOTICE_LOCALES deleted; the notice uses reply_languages(payload locale) and MultilingualText; install_slack_tenant_guard takes languages= (defaults to the policy from the validated slice).
- features/incident/core: IncidentConversation.post accepts str | MultilingualText (plain string until TASK-145.13); Slack adapter and in-memory fake post plain_text().
- features/incident/response: service notice parameters widened; entrypoints/scope.py language_policy() and shared_languages(); slack_show.py (_BOTH deleted; field notice from shared_languages; replies via reply_languages); slack_archive.py (_NO_LOCALE deleted; button notices from shared_languages, button replies reply_languages(None); command notices still the invoker's language until TASK-145.8.9; command replies via reply_languages).
- ADRs: decisions/languages.md (new, Accepted, applies target); i18n.md (translation only, pointer); platform-transports.md (multilingual intent); configuration.md (host slice); transport-slack.md (tenant guard notice, cascade); decisions/README.md row. Response README wording.

No visible change with the default setting. Correction to the OQ4 assessment: the raw-key fallback is real in t(), but on today's Slack paths integrations/slack/provider.py get_user_locale (:915-971, called at :1138) already maps any Slack locale outside en-US/fr-FR to en-US before an entry point sees it, so no user saw raw keys, and a fr-CA user still gets English: the provider pre-empts the policy's primary-subtag match. Passing the raw locale through is recorded on TASK-118. No user announcement.

Verification
- New tests: tests/unit/contracts/test_contracts_multilingual_text_render.py; tests/unit/server/languages/test_server_languages_settings_load.py, test_server_languages_policy_resolve.py; cases added to test_incident_core_conversation_operations.py, test_incident_core_conversation_protocol_parity.py, test_incident_response_show_entrypoint.py (French-first, one language, fr-CA, es-ES), test_incident_response_archive_entrypoint.py (French-first, one language), test_server_slack_tenant_guard_dispatch.py (French-first, one language), test_server_services_registration.py (LanguagePolicy registered and resolving). Fixtures: tests/factories/incident.py incident_scopes(languages=), tests/fixtures/service_registry.py.
- Gates: ruff check . (All checks passed); make check-import-contracts (15 kept, 0 broken), check-settings-key-ownership, check-package-shape, check-test-seams, check-fake-coverage all OK; mypy . 33 errors in 11 files, all pre-existing (none in touched files); pytest tests --ignore=tests/smoke: 8067 passed.
- grep ("en-US", "fr-FR") in features/ and server/: only the slice default in server/languages/settings.py (the configured default, mirrors base.toml).

Human after merge: decide the production order (TBS 6.1.1: French first while the issuing office is in Quebec; department move pending); the agent prepares the app/config/production.toml PR.

Closed 2026-11-25: #1887 merged 2026-11-25T19:46Z (merge commit 87471ee9); ACs #1-#7 checked; no human post-deploy check (no visible change with the default setting). Open follow-on outside this task: production's [languages] shared order (human decision, then the agent prepares the app/config/production.toml PR); fr-CA raw-locale gap recorded on TASK-118.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Instance language policy as configuration behind contracts/languages.py (LanguagePolicy, MultilingualText); [languages] shared host slice (default en-US then fr-FR, validated at boot); IncidentConversation.post takes MultilingualText; tenant guard, show field notice and archive notices/replies moved onto the policy; ADR decisions/languages.md, with i18n.md, platform-transports.md and configuration.md updated. Merged in #1887 (87471ee9).
<!-- SECTION:FINAL_SUMMARY:END -->
