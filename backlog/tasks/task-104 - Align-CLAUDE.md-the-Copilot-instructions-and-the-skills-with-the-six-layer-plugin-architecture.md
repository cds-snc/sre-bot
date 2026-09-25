---
id: TASK-104
title: >-
  Align CLAUDE.md, the Copilot instructions and the skills with the six-layer
  plugin architecture
status: To Do
assignee: []
created_date: '2026-09-24 19:57'
labels:
  - plugin-architecture
  - docs
milestone: m-7
dependencies: []
references:
  - decisions/plugin-architecture.md
  - decisions/dependency-injection.md
  - decisions/plugins.md
  - CLAUDE.md
priority: high
type: docs
ordinal: 244000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugin-architecture.md (Accepted 2026-09-24) replaced the three-tier model with six layers: server, features, capabilities, infrastructure, integrations and contracts. Its Migration section asks for this ticket first: every agent reads CLAUDE.md on every session, so a stale contract there steers new code into the old shape.

Verified drift (2026-09-24):
- CLAUDE.md "Architecture Boundaries" and "Import boundaries" describe packages -> infrastructure -> integrations and tell agents to resolve services through app/infrastructure/services/providers.py and consume them through Depends aliases in app/infrastructure/services/dependencies.py. That directory does not exist. The target is the svcs registry in app/server/ (decisions/dependency-injection.md).
- CLAUDE.md "Plugins and startup" does not mention per-environment enablement or extension points (decisions/plugins.md).
- .github/copilot-instructions.md, .github/instructions/*.instructions.md, .github/agents/*.agent.md, .claude/agents/*.md and the skills that restate architecture (plugin-registration-lifespan, settings-singleton, fastapi-api-patterns, testing-standards, type-model-boundaries, implementation-planning, architecture-review, feature-architecture, groom-backlog, plan-task) may cite the deleted records layers.md, capability-packages.md or events.md, or the old provider pattern.

Scope: documentation only. State the target rules and say plainly what is still tolerated today, by linking the record's Migration section rather than copying its table. No code changes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 CLAUDE.md states the six layers and their import rules and cites decisions/plugin-architecture.md; it no longer references app/infrastructure/services/ or the deleted records layers.md, capability-packages.md and events.md
- [ ] #2 grep over CLAUDE.md, .github/ and .claude/ finds no reference to the deleted records or to infrastructure/services/providers.py or dependencies.py
- [ ] #3 Each skill or agent file that restates an architecture rule distinguishes the target from what is tolerated today and links the owning decision record instead of copying its table
- [ ] #4 CLAUDE.md and .github/copilot-instructions.md stay disjoint, per CLAUDE.md's own rule
<!-- AC:END -->
