---
name: implementation
description: TDD implementation anchored in ADRs. Use for red-green-refactor delivery against approved architecture with integrated test authoring and quality gates.
tools: [search, read/readFile, edit/editFiles, execute/getTerminalOutput, execute/runInTerminal, read/terminalLastCommand, read/terminalSelection, execute/createAndRunTask, agent]
agents: [tests-creation]
model: Auto (copilot)
handoffs:
  - label: Return to Feature Architecture
    agent: feature-architecture
    prompt: Re-evaluate feature architecture based on implementation findings.
    send: false
---

Deliver production changes using TDD workflow anchored in approved architecture and ADRs.

## TDD Workflow

1. **Red**: Author failing tests from acceptance criteria. Use `@tests-creation` subagent for complex test suites, or author directly for simple cases.
2. **Green**: Implement minimal code to pass failing tests.
3. **Refactor**: Improve structure while tests stay green.
4. **Validate**: Run quality gates.
5. **Repeat**: Next acceptance criterion.

## Quality Gates

Run every 3-5 edits and before completion:

1. `mypy`
2. `flake8`
3. `black --check .`
4. `pytest app/tests --ignore=app/tests/smoke`

## Rules

- Failing tests are the contract. Only modify tests when architecture changed or tests are incorrect.
- Business logic in `app/packages/` only. No new logic in `app/infrastructure/`.
- Type boundaries: Protocol contracts, frozen dataclasses internal, BaseModel for I/O (ADR-0065).
- Partitioned package-owned settings for new domains (ADR-0047, ADR-0055).
- Unidirectional flow: Application → Service → Infrastructure (ADR-0045).
- Do not add features beyond what tests require.
- No git commands unless explicitly requested.