---
id: TASK-72
title: 'i18n: unbounded t() memoization causes continuous ECS memory growth'
status: To Do
assignee: []
created_date: '2026-08-05 19:48'
updated_date: '2026-08-05 21:00'
labels:
  - i18n
  - reliability
  - performance
milestone: m-3
dependencies: []
references:
  - decisions/i18n.md
  - app/infrastructure/i18n/factory.py
priority: high
ordinal: 123000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`infrastructure/i18n/factory.py::t(key, locale, fallback="", **variables)` is
decorated with plain `@cache` (== `functools.lru_cache(maxsize=None)`, never
evicts). It is called throughout `app/modules/{atip,incident,role,secret}` and
`packages/geolocate/platforms/slack.py` with dynamic, runtime-supplied keyword
arguments as part of the cache key, e.g. `i18n.t("atip.unknown_command",
action=action, command=command["command"])` and `i18n.t("role.unknown_command",
action=action, command=command["command"])`, where `action`/`command["command"]`
come from live Slack input. Every distinct value ever typed by any user creates
a new, permanently-retained cache entry for the life of the process - a
classic unbounded-memoization leak. This matches an observed production
symptom: the ECS task's memory grows continuously and never shrinks until a
new task is deployed (66% growth over 7 days with no redeploy).

Investigation found the underlying work `t()` wraps is already cheap and
already memoized at the correct layer: `get_translation_service()` (a proper
zero-arg `@cache` singleton) loads/parses the YAML catalogs exactly once at
startup; `Translator.translate_message()`'s per-call work is a plain dict
lookup (`catalog.get_message(key)`) plus string interpolation - not expensive
enough to justify memoization on its own, and certainly not on a key space
that includes arbitrary runtime variables. The safe, bounded part of `t()`'s
own key space (`key` x `locale`, excluding `**variables`) is small and
closed - the core `app/locales` catalog alone has 137 leaf keys x 2 locales
(en-US, fr-FR) confirmed via the loaded `TranslationCatalog`, so even
memoizing just that slice would need no more than a few hundred entries.

Outcome: stop caching on the unbounded `**variables` component. The leading
candidate is to remove `@cache` from `t()` entirely (the real expensive work
is already memoized one layer down via `get_translation_service()`); a bounded
`lru_cache(maxsize=...)` on the full `t()` signature is not a real fix since
the runtime-variable calls have near-zero repeat-hit rate anyway and would
just silently evict useful entries under load while adding complexity for no
measurable benefit. Exact approach (remove cache vs. split into a cached
template-lookup step + uncached interpolation step) is a planning decision,
not decided here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 infrastructure/i18n/factory.py::t() no longer memoizes on the unbounded **variables component; repeated calls with different dynamic variable values do not accumulate distinct process-wide cache entries.
- [ ] #2 A test exercises t() with many distinct dynamic variable values and asserts the process-wide cache size stays bounded (or that no cache exists) rather than growing unbounded.
- [ ] #3 Existing translation behavior (locale fallback, {{variable}} interpolation, fallback-on-missing-key) is unchanged for all current call sites (app/modules/{atip,incident,role,secret}, packages/geolocate/platforms/slack.py).
- [ ] #4 mypy and ruff clean; pytest for infrastructure/i18n passes.
<!-- AC:END -->
