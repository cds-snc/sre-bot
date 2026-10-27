---
status: Accepted
date: 2026-10-09
applies: now
scope: What the SRE bot is for, which product areas it holds, and when an area would leave for an app of its own.
---

# Product Scope

## Context

The bot was named for site reliability engineering and the root README described it that way, but its surfaces span four areas: incident response (incident, alerts through webhooks, on-call, the usergroup sync), cloud operations (AWS account health, spending, Lambda), platform access (access requests, IdP-to-platform sync and catalog, AWS Identity Center, Google Workspace provisioning) and workplace utilities (talent roles, ATIP requests, secret sharing, IP geolocation, rant). The last two areas are not SRE work, which raises the question of carving them out. The team is one to two people and one organisation runs the bot.

## Decision

**One codebase, one deployable, four named product areas.** The bot is the organisation's internal operations platform; incident response is its first-class area. Isolation between areas comes from the plugin architecture, not from repositories: import-linter keeps features independent ([plugin-architecture.md](plugin-architecture.md)), and per-environment enablement ([plugins.md](plugins.md)) switches an area off with a configuration change and no code change (the files ship in the image, so it still deploys).

**Built as a framework another organisation can adopt.** The bot runs for one organisation today, but nothing specific to that organisation belongs in its code: deployment values live in the configuration files ([configuration.md](configuration.md)), behaviour comes from plugins ([plugins.md](plugins.md)), and organisation content (webhook sender mappings and message templates, playbooks, the access catalogue, incident templates) is supplied as data in a way TASK-167's design session decides. The end state is two repositories: this one holds only the app code, and each organisation configures and deploys its instance from a deployment repository of its own, holding its environment configuration files, its organisation content (team playbooks included) and its deployment code. This organisation's values sit in this repository until then (`app/config/production.toml`, `terraform/`); the split is not scheduled and does not gate the app refactor, but new designs (TASK-167's content locations among them) do not assume the content lives in this repository.

| Area | Packages |
| --- | --- |
| Incident response | `incident`, `webhooks`, `oncall` capability, `oncall_sync`, `user_rotations` (an on-call schedule source, [oncall.md](oncall.md)) |
| Cloud operations | AWS account health, spending, Lambda surfaces |
| Platform access | `access` umbrella, AWS Identity Center, Google Workspace provisioning |
| Workplace utilities | `talent`, ATIP, `secret`, `geolocate`, `rant` |

**An area leaves for an app of its own only when one of three things is true**: a different team owns it, it needs a different release cadence, or it needs a different trust boundary that enablement, its own service account ([service-accounts.md](service-accounts.md)) and its own settings slice cannot provide. None holds today. Talent and ATIP handle personal information about candidates and requesters; their own service accounts, settings slices and enablement keys are the mitigation until an owner outside the team appears.

**Rejected: a second app now.** It would buy independent releases, blast radius and ownership that no one needs yet, and cost a second CI pipeline, deploy, Slack app and command prefix, secrets set, observability stack, dependency stream and decision corpus.

## Consequences

- A new package is assigned an area in this record before it merges, so the question "does this belong here" has a written answer.
- When per-environment enablement lands, keys are grouped by area, so a deployment holding only the first two areas is a configuration diff.
- The root README describes the bot as the operations platform with these areas, not as an SRE tool.
- Nothing a deploying organisation supplies (environment file values, organisation content, deployment code) needs a change to the app repository once the deployment repository exists; until then, such values added here are interim and move with it.

## Checks

- Review: this record's table and the root README name the same four areas (on every PR touching either).
- Review: every new top-level package under `features/` or `capabilities/` appears in the table in the same PR.

**Changes:**
- 2026-10-09: Accepted. One app with four areas and written carve-out criteria.
- 2026-10-23: `user_rotations` is in incident response; area enablement is a configuration change, not a change without a deploy (TASK-112).
- 2026-10-26: the bot is built as a framework another organisation can adopt; organisation-specific content stays out of the code, its pattern decided by TASK-167 (human).
- 2026-10-26: end state recorded: the app repository holds only app code; each organisation configures and deploys its instance from its own deployment repository (configuration files, organisation content, deployment code); not scheduled, the refactor comes first (human).
