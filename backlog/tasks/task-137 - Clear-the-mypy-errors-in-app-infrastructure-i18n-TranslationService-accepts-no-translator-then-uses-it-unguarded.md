---
id: TASK-137
title: >-
  Clear the mypy errors in app/infrastructure/i18n (TranslationService accepts
  no translator, then uses it unguarded)
status: To Do
assignee: []
created_date: '2026-10-02 13:48'
labels:
  - i18n
  - cleanup
milestone: m-7
dependencies: []
references:
  - app/infrastructure/i18n/service.py
  - app/infrastructure/i18n/resolvers.py
  - app/infrastructure/i18n/factory.py
  - app/tests/unit/infrastructure/i18n/test_service_startup.py
priority: low
ordinal: 301000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found during Stack A (TASK-107.2 moved the i18n resource spec and surfaced it); recorded in the Stack A handoff and moved here when that doc was retired (2026-10-02).

TODAY (verified 2026-10-02 on main at f182ecd2: cd app && uv run mypy infrastructure/i18n reports 15 errors in 2 files)
- infrastructure/i18n/service.py, 11 errors. TranslationService.__init__ (:56) takes 'translator: Translator | None = None' and stores it, and every method then uses self._translator as if it were set: 10 union-attr errors (:110, :113, :115, :123, :156, :187, :199, :207, :218, :222) and one return-value error (:234, a property declared to return Translator). A service built without a translator fails with AttributeError on first use instead of at construction.
- infrastructure/i18n/resolvers.py, 4 errors: no-any-return at :75, :83, :182, :187.
- Production builds the service in one place, infrastructure/i18n/factory.py:90, and always passes a translator. The bare form TranslationService() appears only in tests: 12 call sites in tests/unit/infrastructure/i18n/test_service_startup.py.
- Every mypy run that follows an import into infrastructure.i18n repeats these errors, so each task since has had to compare error lists before and after to show it added none.

WHAT IS WANTED
mypy reports no error in app/infrastructure/i18n, and a TranslationService cannot exist without a translator (or handles its absence explicitly). The shape of the fix is the planner's to propose: making the constructor argument required changes the 12 bare test constructions; guarding each use keeps them but leaves the half-built state possible.

RELATION TO OTHER TASKS
- TASK-118 replaces app/infrastructure/i18n with a translator contract in app/contracts/ and an implementation in app/server/i18n/, and deletes this package. If TASK-118 is about to start when this task is picked up, close this one as superseded and carry the 'no half-built service' requirement into TASK-118 instead.
- TASK-72 (unbounded t() memoization) edits the same package; whichever lands second rebases.

OUT OF SCOPE
Any change to translation behaviour, catalogue loading or the public API beyond the constructor signature.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 cd app && uv run mypy infrastructure/i18n reports no error (15 today: 11 in service.py, 4 in resolvers.py), with no type: ignore added
- [ ] #2 A TranslationService cannot be used without a translator: either construction requires one, or its absence is handled explicitly and tested; no method reaches an unguarded None
- [ ] #3 The tests in tests/unit/infrastructure/i18n are updated in place to the chosen construction and keep their behaviour assertions; no translation behaviour changes
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
