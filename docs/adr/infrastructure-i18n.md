---
title: "Infrastructure I18n"
status: Draft
type: Selection
tier: Tier-2
governance_domain: [application]
concerns: [architecture, configuration]
constrained_by: [layered-architecture.md, dependency-injection.md, configuration-ownership.md, application-lifecycle.md, type-boundaries.md, feature-package-structure.md, plugin-registration-discovery.md, multi-transport-architecture.md, package-management.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Infrastructure I18n

## Context and Problem Statement

The application speaks to users on multiple platforms (HTTP responses, Slack messages and modals, Microsoft Teams cards) and must produce localized text — at minimum English and French per the Government of Canada's Official Languages requirements. Every platform's outbound formatter (Slack Block Kit messages, Teams Adaptive Cards, HTTP error bodies) needs the same translation lookup primitive: given a translation key and a locale, return the rendered string for that locale, with deterministic fallback when a key or locale is missing.

The problem this record addresses: **which internationalization library does the application use, where does the translation catalogue live, how do features contribute their own translations, and how is the locale resolved per inbound unit of work?** The answer determines:

1. Whether the application uses a project-private translation mechanism that every platform's formatter has to learn, or a standard Python i18n library whose semantics are documented externally and recognized by tooling.
2. How translations are organized — one centralized catalogue, per-feature catalogues, or some other arrangement — and how they are loaded at boot.
3. How the locale is resolved per inbound unit of work (HTTP `Accept-Language`, Slack user preferences, Teams `clientInfo`, an explicit override) and how it is bound to the request context so formatters can read it without parameter threading.
4. What the fallback behaviour is when a key is missing in the requested locale, when the locale itself is unsupported, or when a translation is malformed.

**Constraints:**

- A custom translation system was prototyped in the application's earlier iterations. **That custom solution will be deprecated in favour of an established Python i18n library**; the library is to be confirmed at finalization. Candidates include `Babel` (the de-facto Python i18n toolkit), `python-gettext` (the standard `gettext` workflow), and `fluent.runtime` (Mozilla's Project Fluent for Python). The choice will weigh maturity, format ergonomics for translators, runtime overhead, and integration cost against the application's actual translation needs (short messages, parameterized strings, plurals/ICU support, locale fallback).
- Government of Canada bilingualism: English and French are both first-class. Neither is a fallback for the other in user-facing text; both must always be available for keys that are user-facing. Internal-only strings (operator logs, error tracebacks) are not localized.
- Translations live in the repository, version-controlled. They are not loaded from an external service at runtime.
- The locale binding must be async-safe and propagate through `asyncio.Task` boundaries, the same way the correlation identifier does. `contextvars` is the natural mechanism.
- Configuration follows the per-domain `BaseSettings` pattern; defaults (default locale, supported locale list) live in i18n's own settings.

**Non-goals:**

- This record does not pick the translation file format (gettext `.po`, Fluent `.ftl`, JSON) until the library is selected; format choice follows from the library.
- This record does not specify how translators receive, edit, or commit translation files — that is a workflow concern.
- This record does not localize log records, error tracebacks, or operator-facing diagnostics. Those remain in English (the project's working language) per the logging-observability decision.
- This record does not redefine HTTP `Accept-Language` semantics or platform-specific locale-source mechanisms; it defines how the application *resolves* locale from those sources, not the source mechanisms themselves.

## Considered Options

TODO: Options to be evaluated at finalization. Anticipated framing:

- **Option A — `Babel`** (the de-facto Python i18n toolkit, plus `gettext`-format catalogues). Mature, broad ecosystem, ICU MessageFormat support via `Babel`.
- **Option B — `python-gettext`** (stdlib `gettext` with `.po` / `.mo` files). Lowest dependency surface; well-known workflow; weaker plurals / ICU support than Babel.
- **Option C — `fluent.runtime`** (Project Fluent, `.ftl` files). Modern, expressive, designed for asymmetric translations across locales.
- **Option D — Continue with the project's custom solution.** Rejected up-front: custom i18n implementations rarely match the breadth of established tooling and impose a maintenance tax; the established libraries above are well-documented, well-tested, and well-supported.

## Decision Outcome

TODO: Library selection to be finalized.

Anticipated structure of the finalized record:

- **Library selection.** Pick one of A/B/C with rationale grounded in the specific translation needs (parameterized strings, plurals, asymmetric locale forms).
- **Translation catalogue location.** Anticipated: `app/locales/<lang>/<domain>.<ext>` where `<domain>` is either `core` for cross-cutting strings or `<feature>` for per-feature strings. Per-feature catalogues let each feature own its translations without a central registry.
- **Loading at boot.** Translations loaded once during the lifespan's configuration or feature-activation phase; the loaded catalogue is held by an `I18nService` Protocol exposed from `app/infrastructure/i18n/` and consumed by every platform's outbound formatter via dependency injection.
- **Locale resolution.** A small per-platform locale-source helper extracts the locale from each platform's native channel (HTTP `Accept-Language`, Slack user profile language, Teams `clientInfo.locale`); the resolved locale is bound via `contextvars` (alongside the correlation `request_id`) so formatters can read it without parameter threading.
- **Fallback behaviour.** Missing key in requested locale → fall back to the project's default locale (typically English); missing key in default locale → fall back to a developer-visible marker (the key name itself, prefixed) so that missing translations surface in tests and code review without hiding from users.
- **Feature-contributed translations.** Each feature ships its translation files inside its own package (per the feature-package-structure rule that features own their resources). Loading discovers feature-contributed catalogues either via a plugin hookspec (e.g., `register_i18n_resources`) or via a filesystem scan of `app/packages/*/locales/` — to be decided at finalization.
- **Migration from the custom solution.** The existing project-private translation utilities are deprecated; a one-time migration moves translation strings into the chosen library's format and removes the custom code. The migration is mechanical once the library is chosen.

## Consequences

TODO

## Confirmation

TODO

## Source References

1. TODO: Authoritative sources to be added at finalization. Anticipated:
   - The selected library's official documentation
   - GNU `gettext` manual (if Babel or stdlib `gettext` is selected)
   - Mozilla Project Fluent specification (if `fluent.runtime` is selected)
   - Government of Canada — Official Languages Act and bilingualism guidance for digital services
   - Unicode CLDR locale data (if pluralization rules are in scope)

## Change Log

- 2026-05-08: Created as placeholder. The application's existing custom translation utilities are flagged as **to be deprecated** in favour of an established Python i18n library (Babel, `python-gettext`, or `fluent.runtime`); selection is deferred to finalization. Pins the architectural shape: `I18nService` infrastructure Protocol consumed by every platform's outbound formatter via DI; `contextvars`-bound locale; per-feature catalogues contributed via plugin hookspec or filesystem scan; English and French as bilingual peers per the Government of Canada Official Languages requirements; no localization of operator-facing diagnostics. The constrained-by list expresses the corpus this record sits inside; the library selection itself will not change those upstream rules.
