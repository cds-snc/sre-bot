---
name: Tests Python Rules
description: Rules for app/tests — layout, naming, determinism, dependency overrides, and docstring hygiene.
applyTo: app/tests/**/*.py
---

- **All tests live under `app/tests/`**, mirroring `app/`: `unit/` (isolated, <50ms,
  Protocol fakes), `integration/` (feature + infrastructure with externals stubbed,
  <500ms), `smoke/` (live systems, on-demand only).
- **Name files `test_<domain>_<entity>_<action>.py`.** Generic names like
  `test_routes.py` collide as the suite grows and make failures unattributable.
- **API tests cover both success and failure mapping.** A status-code-only
  assertion passes against a handler returning the wrong body; assert the response
  schema and the RFC 9457 error shape too.
- **Use `app.dependency_overrides` and Protocol-conformant fakes** for determinism,
  and always clear them (fixture teardown or `finally`) — a leaked override
  silently corrupts every later test in the session.
- **Clear `@lru_cache` providers between tests**, otherwise a cached singleton
  built with one fixture's settings leaks into the next test.
- **Assert on behavior, not implementation details.** Assert
  `result.status == SUCCESS`, not which provider method was called.
- **Do not run `app/tests/smoke/*`** unless explicitly requested with the required
  env vars configured.
- **Docstrings describe observable behavior, stub strategy and assertion rationale
  — nothing else.** Never reference external documents, task or ticket ids, sprint
  labels, plan step numbers, implementation phases, or transitory state ("before
  implementation", "AC#2 of TASK-X"). A docstring must stay accurate regardless of
  project state.
