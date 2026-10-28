---
status: Accepted
date: 2026-10-28
applies: target
scope: What an adopting organisation supplies and how to choose its category (deployment configuration, code extension, organisation content), and for content, how to choose its source (provisioned files or managed records); the rules every content kind follows.
---

# Organisation Content

## Context

The bot is built as a framework another organisation can adopt ([product-scope.md](product-scope.md)): nothing specific to one organisation belongs in its code. Deployment configuration ([configuration.md](configuration.md)) and code extensions ([plugins.md](plugins.md)) are decided; the organisation's own data has no record, and the code holds four diverging patterns (inventory of 2026-10-28):
- Python modules per webhook sender in `modules/webhooks/patterns/`, found by an import-time directory walk ([webhooks.md](webhooks.md)), while the webhook instances are created from Slack and stored in the `webhooks` table;
- the access catalogue behind a four-way loader switch (`ACCESS_CONFIG_SOURCE`: `bundle`, `inline_json`, `file_json`, `env`), whose bundle is empty;
- this organisation's on-call data packaged inside the code: `packages/oncall_sync/rotations.json` maps Opsgenie schedule ids and rotation names to Slack user groups (pointers only; who is on call and every swap live in Opsgenie), and each file in `packages/user_rotations/rotations/` is a self-managed roster (members, weekly cadence, start date) from which the app computes who is on call, so changing a roster's members or order is a pull request and a deploy;
- the organisation's wording in the app's strings (`cyber.gc.ca` and `security@cds-snc.ca` in `locales/incident.*.yml`, "CDS Staff" in scribe, the ATIP letter) and a default admin group (`sre-ifs@cds-snc.ca`) in `infrastructure/configuration/features/aws_ops.py`.
TASK-165's team playbooks and TASK-166's entitlement catalogue are planned and need a home. The app already has a store (the records contract over DynamoDB, [cloud-portability.md](cloud-portability.md)); PostgreSQL is a gated option, not a precondition.

## Decision

**Choose the category first.**

| Category | What it is | Changes | Record |
| --- | --- | --- | --- |
| Deployment configuration | How this deployment connects and what it runs: endpoints, credentials, backing-resource names and resource ids, tuning, plugin enablement | per deploy; never reloaded | [configuration.md](configuration.md) |
| Runtime flag | A behaviour switched while the app runs: rollout, kill switch | in flight | [configuration.md](configuration.md) (OpenFeature) |
| Code extension | Behaviour | per deploy | [plugins.md](plugins.md) |
| Organisation content | Data the organisation's people curate for the app to act on: sender mappings and message templates, playbooks, incident types, the entitlement catalogue, rotations, the organisation's wording | per its source | this record |

The test for content: it varies with the organisation's people and practice rather than its infrastructure, and changing it should not need an engineer's review of how the app connects. A value that names a resource (a table, a Google document) is configuration, even when people chose it; what the app does with that resource may be content. Kubernetes draws the same lines: ConfigMaps for program configuration, custom resources for structured objects managed through the API, Secrets apart ([custom resources](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/)); and source-controlled, redeployed toggles are preferred, with a dynamic channel only for operational ones ([Feature toggles](https://martinfowler.com/articles/feature-toggles.html)). Rejected: reloading configuration at runtime (Spring Cloud Config's refresh): replicas would disagree about how they connect, and a bad value reaches all of them at once.

**Then choose the content's source.** Every kind is read through a port its consumer owns: the feature or capability that acts on the kind defines its model (a frozen dataclass built from a pydantic model at the file or API boundary) and a read port with an in-memory fake ([cloud-portability.md](cloud-portability.md)). Behind the port the kind has one or both sources, and the consumer never knows which answered.

| Choose | When | Record |
| --- | --- | --- |
| Provisioned (files) | changes are rare, need review before they apply, or must roll back with the code; the starting set an adopter copies | [provisioned-content.md](provisioned-content.md) |
| Managed (records) | its owners change it while processes run (a roster's members, a new entitlement, a team's playbook), or it is not reviewable as code | [managed-content.md](managed-content.md) |

A kind starts provisioned unless its owners need in-flight change, because managed content costs an admin surface, a permission, versioned records and an export. A kind may have both sources: provisioned items as the starting set, managed items added by people.

**An item has one source.** Each item records which source holds it, as Backstage's `managed-by-location` does ([entity providers](https://backstage.io/docs/features/software-catalog/external-integrations/entity-providers)); a managed item never shadows a provisioned one with the same id, and the admin surface shows provisioned items read-only, as incident.io locks a catalog type managed in GitHub and Grafana refuses to save a provisioned dashboard ([incident.io](https://docs.incident.io/catalog/github-managed-types), [Grafana](https://grafana.com/docs/grafana/latest/administration/provisioning/)). Moving an item between sources is an explicit step, never a merge: export the record to its file, merge the pull request, then delete the record; or import the file once and delete it, as Keycloak's realm import seeds and the database owns afterwards ([Keycloak import](https://www.keycloak.org/server/importExport)).

**Content is never executable.** Matching is declarative (field paths and comparisons), as PagerDuty's Event Orchestration conditions and GitHub Actions expressions are ([Event Orchestration](https://support.pagerduty.com/docs/event-orchestration), [expressions](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions)); a template is logic-light over a fixed data model, with an undefined name an error; every rule and template has size and count limits, as PagerDuty caps conditions and Kubernetes budgets CEL's cost ([CEL](https://kubernetes.io/docs/reference/using-api/cel/)). A sandbox is not a security boundary on its own ([Jinja sandbox](https://jinja.palletsprojects.com/en/stable/sandbox/)): the limits and who may edit are. A step that needs code is a plugin. TASK-168 chooses the template and matching engine for every kind.

**Non-public values.** A provisioned file in this public repository never holds a non-public value ([configuration.md](configuration.md)); it names a configured key instead. A managed record may hold one and never logs it in full.

**Each kind's own record states its rules**: its model, its source, its limits, its permission. The rules here and in the source's record apply to every kind.

| Kind | Source | Owner |
| --- | --- | --- |
| Webhook sender kinds (match, extract, template) | provisioned | TASK-168 |
| Webhook instances (a channel's endpoint and its sender kind) | managed | TASK-168 |
| Team playbooks, incident types, per-type document templates | managed, with a provisioned starting set | TASK-165 |
| Entitlement catalogue | managed | TASK-166 |
| On-call schedule mappings (a schedule source's schedule to a Slack user group) | provisioned | TASK-146 re-cut |
| Self-managed rosters (members and cadence) | managed | TASK-146 re-cut |
| Organisation wording (message overrides by key over the app's generic strings, [i18n.md](i18n.md)) | provisioned | each surface's rebuild |

## Consequences

- An adopter supplies content without forking; the app ships models, loaders and examples only.
- People change what they own without a pull request; what needs review still gets one.
- Cost: two sources to build, though a kind builds only the one it needs.

## Checks

- Review: a new kind names its category, its source and its owner in this record's table, in the PR that adds it.
- Review: no executable content (no Python, no `eval`, no unsandboxed template); no organisation-specific literal in app code or app strings.
- Test: a managed write to a provisioned item's id is refused.

## Migration

Tickets: TASK-165, TASK-166, TASK-168, the TASK-146 re-cut, the incident surface rebuilds (TASK-145) and TASK-39, TASK-88, TASK-170 (the deployment repository). Tolerated until closed:
- per-sender Python in `modules/webhooks/patterns/` and its import-time walk (TASK-168 slices);
- `ACCESS_CONFIG_SOURCE` and its four loaders (TASK-166);
- the schedule mappings in `oncall_sync/rotations.json` and the rosters in `user_rotations/rotations/` inside the code (TASK-146 re-cut);
- organisation wording in `locales/` and scribe, and the ATIP letter (the incident surface rebuilds, TASK-39);
- the `sre-ifs@cds-snc.ca` default in `aws_ops.py` (TASK-111.14 moves it to `production.toml` as `[cloud_operations] aws_admin_groups`; TASK-88 deletes it with `modules/permissions`).

**Changes:**
- 2026-10-28: Draft (TASK-167). Category and source chosen from two tables; content through a consumer-owned port; one source per item, explicit moves; never executable; each source and each kind has its own record (human: the store exists, so in-flight change is designed for, not ruled out; one record per content type).
- 2026-10-28: Accepted (human review, TASK-167).
