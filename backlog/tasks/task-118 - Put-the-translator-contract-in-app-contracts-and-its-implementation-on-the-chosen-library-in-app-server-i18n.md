---
id: TASK-118
title: >-
  Put the translator contract in app/contracts/ and its implementation, on the
  chosen library, in app/server/i18n/
status: To Do
assignee: []
created_date: 2026-09-24 20:00
updated_date: '2026-11-25T19:25:00Z'
labels:
  - plugin-architecture
  - i18n
milestone: m-7
dependencies:
  - TASK-117
  - TASK-107
  - TASK-109
  - TASK-72
references:
  - decisions/i18n.md
  - decisions/plugin-architecture.md
  - https://github.com/cds-snc/sre-bot/issues/1661
priority: medium
type: feature
ordinal: 260000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/i18n.md: i18n is a framework service. The translator contract lives in app/contracts/, its implementation is host code in app/server/, and features and capabilities depend only on the contract. Catalogues stay in each feature's locales/ and register at startup through the register_i18n_resources hookspec in contracts (contracts/plugins/hookspecs.py).

Today packages/access/sync, packages/geolocate and features/incident/core/adapters/i18n.py import from app/infrastructure/i18n/ (t, TranslationService, Translator, TranslationKey, Locale), as do integrations/slack (provider.py, formatter.py) and server/lifespan.py.

Scope:
- define the translator contract;
- implement it in app/server/i18n/ on the library chosen by the decision ticket (TASK-117);
- register it in the service registry;
- repoint every importer;
- delete app/infrastructure/i18n/ with no re-export.
Legacy modules on python-i18n and app/locales/ are untouched; they retire with their surfaces (TASK-41). Depends on TASK-72 so the live memory bug is fixed in the current stack rather than waiting for the rewrite.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The translator contract lives in app/contracts/; no feature, capability or integration imports server.i18n or infrastructure.i18n
- [ ] #2 The implementation in app/server/i18n/ uses the library chosen by the decision ticket; app/infrastructure/i18n/ is deleted with no re-export
- [ ] #3 Every existing feature catalogue loads unchanged and renders the same EN and FR strings (tests)
- [ ] #4 Locale resolves per request from contextvars at the inbound boundary
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-25T18:51:00Z

---

2026-11-25 (human, TASK-145.8.9 D6): the instance language policy (which languages and in what order a shared message uses, the reply language for a user) is a separate contract and ADR, TASK-193; the translator contract stays translation only (key and locale to text).

---

created: 2026-11-25T19:10:00Z

---

2026-11-25 (human, TASK-193 approved): the translator contract stays translation only; the supported-locale lists in integrations/slack (users.py:173, provider.py:928) and the Locale set move with the translator; LanguagePolicy (contracts/i18n/languages.py) decides the language before the translator is called.

---

created: 2026-11-25T19:24:00Z

---

2026-11-25 (TASK-193 implemented): the language policy contract is contracts/languages.py (not contracts/i18n/languages.py as the earlier comment said: contracts.i18n stays standard-library only).

---

created: 2026-11-25T19:25:00Z

---

2026-11-25 (TASK-193 finding, D3 gap): integrations/slack/provider.py get_user_locale (:915-971, enrichment at :1138) maps any Slack locale outside en-US/fr-FR to en-US before an entry point sees it, so a fr-CA user is answered in English and the LanguagePolicy's primary-subtag match (decisions/languages.md) never runs for slash commands. When the provider's supported-locale list moves here, pass the raw Slack locale through and let reply_languages decide; that change is user-visible (named change, announcement).

---
<!-- COMMENTS:END -->
