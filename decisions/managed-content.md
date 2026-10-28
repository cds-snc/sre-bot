---
status: Accepted
date: 2026-10-28
applies: target
scope: Organisation content stored as records and changed while the app runs: the write path (validation, limits, permission, approval), versions and restore, audit, the read path and its blast-radius controls, schema evolution, export.
---

# Managed Content

## Context

[organisation-content.md](organisation-content.md) sends a content kind to records when its owners change it while processes run. The app already does this once, without rules: legacy webhooks are created from a Slack command and stored in the `webhooks` table, unversioned and unaudited. TASK-165 (team playbooks, incident types), TASK-166 (entitlement catalogue) and the TASK-146 re-cut (self-managed rosters) need it. Records go through the records contract ([cloud-portability.md](cloud-portability.md)), over DynamoDB today. Runtime changes are how large configuration outages start: Cloudflare's of 2025-11-18 came from a generated file that broke a size limit and spread fleet-wide, and its fix treats internally generated configuration as untrusted input ([Cloudflare](https://blog.cloudflare.com/18-november-2025-outage/)); Google Cloud's of 2025-06-12 from a policy with blank fields replicated globally in seconds, with no flag in front of it ([Google Cloud](https://status.cloud.google.com/incidents/ow5i3PPK96RduMcb1SsW)).

## Decision

**One admin surface per kind, one write path.** A managed kind is changed through its admin surface (Slack, the API, or both), and every change, whatever the surface, goes through the kind's one write service. Nothing writes the kind's records directly.

**A write is validated before it is stored.**
- The item against the kind's model, the same model the provisioned files use, as Kubernetes validates every custom-resource write against its schema whatever the client ([CRD validation](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/));
- the kind's effective set with the change applied: unique ids, references that resolve, and the kind's limits on item size, item count and rule and template size. A change that would break the set is refused, so no reader ever sees it.

**A write is authorised.** Each kind declares a permission to change it, deny by default ([authorization.md](authorization.md)); a per-team kind scopes it to the team. A kind may require a second person's approval before a change applies ([approvals.md](approvals.md)), as LaunchDarkly gates flag changes per environment ([approvals](https://launchdarkly.com/docs/home/releases/approvals)); the kind's record says which changes need one.

**A write appends a version.** Records are never updated in place: each change stores the item's next version, and restoring is a new version copying an old one, as Grafana restores a dashboard ([version history](https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/manage-version-history/)). Each kind sets how many versions it keeps. A deletion is a version too (a tombstone), so it can be restored.

**A write is audited.** Each change is an audit event naming who, what (kind, id, version), when, where (the surface), the outcome (applied, refused and why, awaiting approval) and the reason given ([NIST SP 800-53 AU-3](https://csrc.nist.gov/projects/cprt/catalog#/cprt/framework/version/SP_800_53_5_1_1/home?element=AU-03)). A non-public value is never logged in full.

**Readers treat stored content as untrusted input.** Consumers read through the kind's port on every use or behind a short cache, so replicas agree without coordinating. A stored item that does not validate under the running model is skipped and reported (a log event and a metric), never served. Each kind's managed source has a runtime flag (OpenFeature, [configuration.md](configuration.md)) that switches it off; readers then get only the kind's provisioned items. That is the kill switch Cloudflare and Google added after their outages.

**Schemas evolve expand, then contract, in both directions.** An image rollback does not roll records back, so each record carries its schema version, and a kind's model is compatible both ways across every stored version: the current image reads old records, and the previous image reads what the current one writes (Confluent's `FULL_TRANSITIVE`: [compatibility](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html)). A field is added optional or defaulted; a field is removed only after a migration has rewritten the stored records and the previous image no longer needs it ([Parallel change](https://martinfowler.com/bliki/ParallelChange.html), [storage version migration](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/storage-version-migration/)).

**Export.** A kind exports its items in its provisioned file format: to seed another deployment, to move an item to files ([organisation-content.md](organisation-content.md)), to review the set, and as a backup readable without the app.

**Not adopted for now: writing changes back to git as pull requests** (Grafana Git Sync). Versions, audit and export cover history and review; revisited when a kind's changes need code-style review.

## Consequences

- People change what they own in flight, and every change is checked, attributable and reversible.
- A bad change is refused at write; a bad stored item is skipped at read; a kind gone wrong is switched off by a flag.
- Cost: each managed kind needs an admin surface, a permission, a version store, an export and a compatibility test.
- Cost: managed content is outside the image's rollback, so schema changes take two deploys to contract.

## Checks

- Test: a write the model or the set check rejects stores nothing and audits the refusal; a write without the permission is refused; a write needing approval does not apply before it.
- Test: every applied write appends a version and an audit event with the AU-3 fields; a restore appends a version; a deletion is restorable.
- Test: a stored item that fails validation is skipped and reported; with the kind's flag off, readers get only provisioned items.
- Test: the model reads every schema version in its fixtures, and the previous release's model reads the current one's output.
- Review: no code writes a managed kind's records outside its write service.

## Migration

Tickets: the first managed kind (TASK-166, TASK-165 or the TASK-146 re-cut, whichever lands first) builds the version store and audit pattern the others reuse; TASK-168 moves the legacy webhook instances onto it. Tolerated until closed: the `webhooks` table's unversioned, unaudited create and delete from Slack (TASK-168).

**Changes:**
- 2026-10-28: Draft (TASK-167). One write path per kind with model and whole-set validation and limits, a declared permission and optional approval; append-only versions with restore and retention; AU-3 audit; readers skip invalid items and a per-kind flag switches the managed source off (Cloudflare 2025-11-18, Google Cloud 2025-06-12); schema version per record, compatible both ways; export; Git Sync not adopted for now (human).
- 2026-10-28: Accepted (human review, TASK-167).
