---
status: Accepted
date: 2026-11-25
applies: target
scope: Which languages a message uses on an instance: shared and generic messages, direct interactions, and how a message in several languages reaches a platform.
---

# Instance Languages

## Context

Three concerns were mixed. **Translation** turns a key and a language into a text ([i18n.md](i18n.md)). **Language policy** decides which languages a message uses. **Layout** decides how a platform shows a message in several languages. Until TASK-193 the policy was code: the pair `("en-US", "fr-FR")`, English first, sat in `server/slack/tenant_guard.py` and two incident entry points, and features joined the lines with a newline before posting a string, against [platform-transports.md](platform-transports.md) (outbound messages are intents).

The set and the order are an organisation's policy, set by its jurisdiction. The TBS Directive on Official Languages for Communications and Services, 6.1.1, puts French first when the issuing office is in Quebec and English first elsewhere ([TBS](https://www.tbs-sct.canada.ca/pol/doc-eng.aspx?id=26164)); the Directive on Official Languages for People Management requires regularly used electronic systems in both languages, and the interface in the language of the user's choice ([TBS](https://tbs-sct.gc.ca/pol/doc-eng.aspx?id=26168)). The Welsh Language Standards place Welsh to be read first on signs but set no order for social posts ([Welsh Government](https://www.gov.wales/welsh-language-standards-communication-and-marketing-guidelines)). GC Notify offers English-first and French-first bilingual templates ([GC Notify](https://notification.canada.ca/features)). Frameworks keep the language list in deployment configuration (Django `LANGUAGES`, Rails `available_locales`). This project is built for other organisations to adopt ([product-scope.md](product-scope.md)), some with one language.

Current state: `[languages] shared` (`server/languages/settings.py`), `LanguagePolicy` and `MultilingualText` (`contracts/languages.py`), the host policy registered as a core service (`server/services.py`). The update modal's field notice, the archive button and the Slack tenant guard use it. `/sre incident status update`, the roles announcement and `/sre incident close` still post their channel notices in the invoker's language (TASK-145.8.9).

## Decision

**The instance configures its languages.** `[languages] shared` is an ordered list of one or more languages the app supports (has catalogues for). It is validated statically in the configuration phase: empty, repeated or unsupported entries fail boot. The default is English then French; each deployment sets its own order in its environment file. The jurisdiction's reasoning (for example TBS 6.1.1) lives in that file's comment, never in code.

**Shared and generic messages use the instance's languages, in order.** A post to a shared conversation, a notice to many readers, and the answer to a request whose payload names no language (a legacy button, a block action, an event) are in every configured language, one line per language, each from its own catalogue.

**Direct interactions use the user's language of choice.** A private reply, a direct message and a view follow the language the platform names for the user, matched to a supported language exactly, then on its primary language subtag ([RFC 4647 lookup](https://www.rfc-editor.org/rfc/rfc4647#section-3.4): `fr-CA` to `fr-FR`, `en-GB` to `en-US`), else the instance's first language. The user's choice is not limited to the instance list: a French-speaking user of an English-only instance is answered in French. A view carries its opener's language in its private metadata.

**Features ask the policy through `LanguagePolicy`** (`contracts/languages.py`), resolved from the service registry ([dependency-injection.md](dependency-injection.md)). `shared_languages` takes the conversation (system, tenant and id, [workplace-systems.md](workplace-systems.md) rule 4), so a per-tenant or per-conversation rule changes the host policy and no caller.

**A message in several languages is one value, laid out by the platform.** Features hand `MultilingualText` (ordered language and text pairs) to the platform; `plain_text()` (a line per language, in order) is the layout every platform can show. Slack posts one message, top to bottom; a Teams adapter lays it out as one card with a text block per language; email marks each part's language ([WCAG 3.1.2](https://www.w3.org/WAI/WCAG22/Understanding/language-of-parts)).

**Only the bot's own wording is multilingual.** Text the bot forwards (a webhook sender's alert, a captured message) or that a model writes keeps its source language and appears once, beside the bot's lines ([W3C language tags](https://www.w3.org/International/articles/language-tags/)); AI-written text follows its own feature's rule.

## Consequences

- An organisation changes its order or drops a language with a one-line configuration change; this one's production order is its own decision, recorded in `app/config/production.toml`.
- A user whose platform language has no catalogue reads the instance's first language instead of a raw key.
- Cost: a third language needs catalogues and the supported set (a product change), and the parity check grows with it ([i18n.md](i18n.md)).

## Checks

- grep: no tuple or list of language tags in `app/features/` or `app/server/` outside `server/languages/settings.py`.
- `make check-settings-key-ownership`: `[languages]` is in `app/config/base.toml` and owned by `server/languages/settings.py`.
- Review: a new post to a shared conversation passes `MultilingualText` built from `shared_languages`.

## Migration

Tickets: TASK-145.8.9 (status, roles and close notices), TASK-145.13 (`IncidentConversation.post` takes `MultilingualText` only), TASK-118 (the supported-language lists in `integrations/slack` move with the translator).

Tolerated until then:
- `IncidentConversation.post` accepts a plain string;
- three incident channel notices in the invoker's language (TASK-145.8.9);
- `integrations/slack/users.py` and `provider.py` keep their own supported-language lists, and the provider maps a command's Slack locale outside them to `en-US` before the policy sees it, so a `fr-CA` user is answered in English (TASK-118 passes the raw locale through).

**Changes:**
- 2026-11-25: Accepted. Instance languages configured; shared messages in the instance order, direct interactions in the user's language of choice; `LanguagePolicy` and `MultilingualText` (TASK-193; TASK-145.8.9 OQ2, human D1-D6).
