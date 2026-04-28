# Decision Record Template

Use this template for new records and major updates.

```yaml
---
adr_id: ADR-0000
title: "Short decision title"
status: Draft
decision_type: Principle
tier: Tier-1
date_created: YYYY-MM-DD
last_updated: YYYY-MM-DD
last_reviewed: YYYY-MM-DD
next_review_due: YYYY-MM-DD
owners:
   - Platform Engineering
supersedes: []
superseded_by: []
related_records: []
related_packages: []
review_state: current
---
```

## Metadata Rules

- `adr_id`: canonical global ID (`ADR-0001`, `ADR-0002`, ...).
- `status`: `Draft | Proposed | Accepted | Superseded | Deprecated`.
- `decision_type`: `Principle | Standard | Feature | Migration`.
- `tier`: `Tier-1 | Tier-2 | Tier-3 | Tier-4 | Cross-tier`.
- `review_state`: `current | stale`.
- `supersedes` and `superseded_by` are mandatory arrays (possibly empty).
- If `status: Superseded`, `superseded_by` must include at least one ADR ID.
- Strict freshness policy: records are stale when `last_reviewed` is older than 120 days.

## Context

- Problem statement:
- Business/operational drivers:
- Constraints:
- Non-goals:

## Decision

- Chosen approach:
- Why this approach:
- Principles established:

## Alternatives Considered

1. Option name:
   - Pros:
   - Cons:
   - Why not chosen:
2. Option name:
   - Pros:
   - Cons:
   - Why not chosen:

## Consequences

- Positive impacts:
- Tradeoffs accepted:
- Risks introduced:
- Mitigations:

## Compliance and Boundaries

- Package/infrastructure boundary impact:
- Type boundary impact (Protocol/dataclass/BaseModel/TypedDict):
- Startup/plugin registration impact:
- Settings partitioning impact:

## Freshness Review

- Record age at review time (days):
- Is record older than 120 days: Yes | No
- If Yes, status set to stale: Yes | No
- Validation summary:
- Follow-up actions:

## Source References (Required)

List every source used for new or revised guidance.

1. Source title:
   - URL:
   - Publisher/maintainer:
   - Accessed date (YYYY-MM-DD):
   - Relevance summary:
2. Source title:
   - URL:
   - Publisher/maintainer:
   - Accessed date (YYYY-MM-DD):
   - Relevance summary:

## Implementation Guidance

- Required changes:
- Validation and quality gates:
- Test strategy and acceptance criteria impact:

## Change Log

- YYYY-MM-DD: Summary of changes and reason.