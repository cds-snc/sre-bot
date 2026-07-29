---
status: Accepted
date: 2026-07-29
applies: target
scope: How a hookspec is deprecated and later removed.
---

# Hookspec Deprecation Lifecycle

## Context

[plugins.md](plugins.md) makes hookspecs host-owned and reviewed but has no rule for retiring one. The gap is not hypothetical: `app/infrastructure/plugins/specs.py`'s `register_slack_commands` already carries an ad hoc docstring — "(DEPRECATED: will be removed in favor of register_slack_listeners for direct Bolt app registration)" — with no minimum lifetime, no announcement mechanism, and no removal checklist. Four hookimpls still implement it today (`app/modules/dev`, `app/modules/sre`, `app/packages/access/sync`, `app/packages/geolocate`), plus one pending in `app/packages/access/request`. Without a rule, nothing stops a removal PR from deleting the spec the same day it's marked deprecated, breaking any implementer a quick grep misses.

## Decision

**Marker format.** A deprecated hookspec's docstring leads with: `DEPRECATED (since <milestone>, replacement: <hookspec name>).` — anchored to the backlog milestone it was marked in (`m-0`…`m-6`), not a calendar date. Repo work is milestone-tracked, not sprint/date-tracked ([migration.md](migration.md), [toolchain.md](toolchain.md) both phase things this way); a milestone anchor stays meaningful, a hardcoded date silently rots.

**Minimum lifetime.** Not removed before the milestone *after* the one that introduces its replacement. That is at least one full milestone boundary of coexistence — enough for in-flight migrations to land without a forced same-cycle rewrite, short enough that "deprecated" doesn't mean "permanent."

**Removal checklist**, all required in the removal PR (this is [governance.md](governance.md)'s cascade rule applied to code, not just decision records):
1. Repo-wide grep for `@hookimpl` implementers of the deprecated spec name — zero remaining callers required.
2. Every implementer found is migrated or deleted before the spec is removed (a removal PR with live implementers is rejected, not merged with a TODO).
3. The hookspec is deleted from `specs.py`.
4. Any decision record naming the removed spec (starting with [plugins.md](plugins.md)) is updated in the same PR.
5. `app/tests/unit/infrastructure/plugins/test_plugins_hookspecs.py` (the boot-test spec inventory) drops the removed spec, proving nothing still expects it.

## Consequences

- A deprecated hookspec can outlive a single migration PR series by design — that is the compatibility window working as intended, not scope creep.
- Removal becomes a reviewed, checklisted change, not a quiet deletion that breaks an unmigrated implementer.
- Honest `applies: target`: `register_slack_commands`'s current docstring predates this rule and uses neither the milestone-anchored marker nor names a removal gate — bringing it into compliance is this record's own Migration item, not a retroactive claim that it already complies.

## Checks

- Every hookspec docstring containing `DEPRECATED` names a replacement and an origin milestone in the `DEPRECATED (since <milestone>, replacement: <name>)` format.
- A removal PR's description states the repo-wide grep result for the removed spec's implementers (must be zero).
- `test_plugins_hookspecs.py` contains no reference to a removed spec.

## Migration

Ticket: TASK-67 — reformat `register_slack_commands`'s docstring to the new marker format (`DEPRECATED (since m-1, replacement: register_slack_listeners).`); once every current implementer (`dev`, `sre`, `access/sync`, `geolocate`, `access/request`) has migrated to `register_slack_listeners` and at least one milestone boundary has passed since `m-1`, remove the hookspec per the checklist above. Tolerated until closed: the current ad hoc docstring wording; four hookimpls still on the deprecated spec.
