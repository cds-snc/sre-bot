---
id: TASK-145.9.3
title: Move summarize from scribe into incident.response
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-19T17:29:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.9.2
  - TASK-25.10.3
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.9
priority: medium
type: task
ordinal: 518000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L10c (size exception approved 2026-11-09: pure move). summary and its prompt move into response/service/summary.py and prompt.py; scribe loses its summary path, catalogue and test; behaviour unchanged; an optional text-generation use with no requirement in response.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 summarize lives in response/service/; scribe holds no summary path, catalogue or test; make check-package-shape passes with no new baseline entry (checks parent ACs #3, #11)
- [ ] #2 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-19 (human, #1877 review of TASK-25.10.2): the text-generation capability is named ai_writing: capabilities/ai_writing, Protocol AIWriter with is_available() and write(source, *, instructions, max_output_tokens=None), get_ai_writer(), error code AI_WRITING_UNAVAILABLE, log events openai_write_*. Its purpose is AI-written text only; any other AI use is a separate capability named for its purpose (plugin-architecture.md). Read 'text generation', TextGenerator and generate in this task as AI writing, AIWriter and write.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-19T14:28:00Z

---

2026-11-19 (TASK-25.10.2 Q4, human): scribe keeps its summarizer= keyword (typed against the text-generation capability's TextGenerator) through 25.10.2 to avoid churning ~52 test sites; when this task moves the function, name the parameter for its role (text_generator=).

---
<!-- COMMENTS:END -->
