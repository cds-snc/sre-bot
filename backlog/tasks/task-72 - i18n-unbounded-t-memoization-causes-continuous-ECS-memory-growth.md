---
id: TASK-72
title: 'i18n: unbounded t() memoization causes continuous ECS memory growth'
status: To Do
assignee: []
created_date: 2026-08-05 19:48
updated_date: '2026-10-23T17:08:00Z'
labels:
  - i18n
  - reliability
  - performance
milestone: m-3
dependencies: []
references:
  - decisions/i18n.md
  - app/infrastructure/i18n/factory.py
  - https://github.com/cds-snc/sre-bot/issues/1615
priority: high
ordinal: 123000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
infrastructure/i18n/factory.py::t(key, locale, fallback="", **variables) (factory.py:93-94) is decorated with plain @cache (functools.lru_cache(maxsize=None), never evicts), so every argument is part of a permanently retained cache key. Its callers pass runtime values both as **variables and inside f-string fallbacks:
- packages/geolocate/platforms/slack.py: ip_address from the user's command (variable and fallback);
- packages/access/sync/interactions/slack.py and presenters.py: user_email, platform, job_id, started_at and result.message in fallbacks and variables;
- features/incident/core/adapters/i18n.py, which forwards key, locale, fallback and variables to t().
Every distinct value creates a new cache entry for the life of the process, an unbounded-memoization leak matching the observed production symptom: the ECS task's memory grows continuously and never shrinks until a new task is deployed (66% growth over 7 days with no redeploy). The legacy modules (app/modules/{atip,incident,role,secret}) call the python-i18n library (import i18n), not this t(), and are out of scope.

The work t() wraps is already cheap and memoized at the right layer: get_translation_service() (a zero-arg @cache singleton, factory.py:81) loads the YAML catalogues once; per-call work is a dict lookup plus interpolation, not worth memoizing on a key space that includes runtime values.

Outcome: t() stops caching on its unbounded components (fallback and **variables). The leading candidate is removing @cache from t(); a bounded lru_cache on the full signature is not a fix (near-zero repeat hits, silent eviction). Removing the cache vs. a cached template lookup plus uncached interpolation is a planning decision.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 infrastructure/i18n/factory.py::t() no longer memoizes on its unbounded components (fallback and **variables); repeated calls with different runtime values do not accumulate process-wide cache entries
- [ ] #2 A test calls t() with many distinct variable and fallback values and asserts the process-wide cache stays bounded (or that no cache exists)
- [ ] #3 Existing translation behaviour (locale fallback, {{variable}} interpolation, fallback on a missing key) is unchanged for the current callers: packages/geolocate, packages/access/sync and features/incident/core/adapters/i18n.py
- [ ] #4 mypy and ruff clean; pytest tests --ignore=tests/smoke passes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
A fargate_memory (or fargate_cpu) change reaches production only at the next deploy: terraform registers a new task-definition revision, but the service ignores task_definition (decisions/deployment.md, TASK-111.16). After tf apply, redeploy the current image per docs/runbooks/roll-back-a-deployment.md.
<!-- SECTION:NOTES:END -->
