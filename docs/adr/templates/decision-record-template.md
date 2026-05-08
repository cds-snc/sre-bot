# Decision Record Template

Copy this file to `docs/adr/kebab-case-title.md`. Records are identified by filename — no
numeric sequence. See [adr-metadata-reference.md](adr-metadata-reference.md) for allowed
field values, tier placement algorithm, and concern tag list.

Governance: [decision-record-governance.md](../decision-record-governance.md)

---
title: "Short decision-focused title"
status: Draft
type: Standard
tier: Tier-2
date: YYYY-MM-DD
governance_domain:

- application
concerns:
- architecture
decision_makers:
- SRE Team

# Conditional — include only when applicable

# constrained_by

# - decision-record-governance.md

# supersedes

# - old-record-name.md

# superseded_by

# - new-record-name.md

# retirement_date: YYYY-MM-DD          # Deprecation type only

# consulted: []                         # optional

# informed: []                          # optional

---

# {Title}

## Context and Problem Statement

{Describe the problem in two to three sentences. What specific concern does this decision
address?}

- {Decision driver / force / constraint}
- {Decision driver / force / constraint}

**Constraints:**

- {Hard constraint on the solution space}

**Non-goals:**

- {What this record deliberately does not decide}

## Considered Options

- {Option 1 title}
- {Option 2 title}
- {Option 3 title}

## Decision Outcome

Chosen option: **{Option title}**, because {justification}.

{State the rules or principles this decision establishes.}

### Consequences

- Good, because {positive consequence}
- Bad, because {accepted tradeoff or risk}
- {Mitigation for the above risk}

### Confirmation

{Optional. How will compliance with this decision be verified? E.g., code review checklist,
automated import check, architecture test.}

## Pros and Cons of the Options

### {Option 1 title}

- Good, because {argument}
- Good, because {argument}
- Bad, because {argument}

### {Option 2 title}

- Good, because {argument}
- Bad, because {argument}
- Bad, because {argument}

### {Option 3 title}

- Good, because {argument}
- Neutral, because {argument}
- Bad, because {argument}

## Source References

1. {Title}
   - URL: {URL}
   - Accessed: YYYY-MM-DD
   - Relevance: {One sentence explaining why this source informs this decision.}
2. {Title}
   - URL: {URL}
   - Accessed: YYYY-MM-DD
   - Relevance: {One sentence explaining why this source informs this decision.}

## Change Log

- YYYY-MM-DD: {Summary of change and reason.}
