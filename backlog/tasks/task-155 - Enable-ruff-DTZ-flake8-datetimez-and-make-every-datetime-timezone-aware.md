---
id: TASK-155
title: Enable ruff DTZ (flake8-datetimez) and make every datetime timezone-aware
status: To Do
assignee: []
created_date: '2026-10-15 19:39'
labels:
  - quality
  - lint
dependencies: []
priority: low
ordinal: 397000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stored and compared times must be instants independent of the host timezone, which varies by cloud provider and runtime. Naive calls (datetime.now() without tz, utcnow(), fromtimestamp without tz, strptime without %z, naive datetime(), today()) read or assume the process zone; utcnow and utcfromtimestamp are also deprecated. ruff check . --select DTZ finds 60 violations on 2026-10-15 (26 DTZ005, 18 DTZ001, 6 DTZ007, 4 DTZ006, 3 DTZ003, 2 DTZ002, 1 DTZ004), 4 of them in features/incident/scheduling/availability.py. Add DTZ to [tool.ruff.lint] select in app/pyproject.toml and fix each call with an aware UTC datetime; behaviour stays the same where the process zone was UTC. Split per package if the size gate trips.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 DTZ is in the ruff select list in app/pyproject.toml and ruff check . reports no DTZ violation
- [ ] #2 Every fixed call produces an aware datetime; no per-line DTZ ignore is added without a recorded reason
- [ ] #3 ruff, lint-imports, mypy (no errors in touched files) and pytest tests --ignore=tests/smoke pass, with commands and output recorded in notes
<!-- AC:END -->
