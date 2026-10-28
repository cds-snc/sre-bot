---
status: Accepted
date: 2026-10-28
applies: target
scope: Organisation content supplied as files: format, location, loading and validation, ownership, versioning and rollback, the adopter's starting set.
---

# Provisioned Content

## Context

[organisation-content.md](organisation-content.md) sends a content kind to files when its changes are rare, need review before they apply, or must roll back with the code. Today such data is scattered: JSON inside packages (`oncall_sync/rotations.json`, `user_rotations/rotations/`, the access development sample `access.local.json`), YAML locale files carrying the organisation's wording, and Python modules per webhook sender. None is validated as a set before deploy, and all of it sits in this public repository. The end state is the organisation's own deployment repository holding its content ([product-scope.md](product-scope.md)); the app is promoted as one image and rolled back to the previous task-definition revision ([deployment.md](deployment.md)).

## Decision

**Format.** YAML, read with `yaml.safe_load` (no tags, no anchors across files), one item per file under `<content root>/<kind>/<id>.yaml`, the file name the item's id. YAML because content holds multi-line templates and nested rules, and the catalogues it resembles are YAML (Backstage's `catalog-info.yaml`, Grafana's provisioning files, Alertmanager's templates); TOML stays for configuration.

**Schema.** The kind's model, owned by its consumer, validates every file; its JSON Schema is exported to `<content root>/schemas/<kind>.json` and checked in CI against the model, so an editor and the content repository's CI run the same check the app runs. Backstage ships the same check as `backstage-cli catalog validate` ([catalog](https://backstage.io/docs/features/software-catalog/configuration)). Each file names its schema version (`version: 1`); the model reads every version the files may hold.

**Location.** The content root is one host configuration key. Interim: `app/content/` in this repository, holding this organisation's content until TASK-170. End state: the organisation's deployment repository builds its image `FROM` the app image pinned by digest, copies its content root in and runs the app's validator in its CI; the app repository keeps only the example set. A production deployment pins a digest, never a moving tag, as Argo CD pins a commit ([tracking strategies](https://argo-cd.readthedocs.io/en/stable/user-guide/tracking_strategies/)). Rejected: fetching content at runtime (S3, an OCI artifact, a git-sync sidecar): it adds a startup dependency and IAM, lets tasks run different content, and splits content's rollback from the code's.

**Loading.** Content loads once in lifespan's configuration phase, after the configuration files, and only for enabled plugins ([lifecycle.md](lifecycle.md)); a disabled plugin's content is never read. An invalid item fails boot naming the file and the field; a duplicate id, a dangling reference or a kind over its size or count limit fails boot naming the kind. Content is never reloaded: a change is a pull request and a deploy.

**Blast radius.** A bad file fails the validator in CI before merge and fails boot if it gets through; a task that fails boot never takes traffic, and the ECS circuit breaker rolls the deploy back to the previous revision ([deployment.md](deployment.md)). A content change therefore reaches production only through the same gates as code.

**Ownership.** CODEOWNERS per directory: each kind's directory has its owner, and a team owns its own folder where a kind is per team (playbooks), so a team's change needs that team's review.

**Versioning and rollback.** Git history is the content's history; the image is its version. A rollback runs the previous content with the previous code, so provisioned content needs no compatibility across versions beyond its own file schema versions.

**A new organisation starts from examples.** Each kind ships example items under `app/content/examples/` (example.com, no organisation's data), which `local.toml` and `ci.toml` point at. A plugin that requires a kind and finds none fails boot naming the kind, as a missing required setting does.

**Not adopted for now: edits in the admin surface written back as pull requests** (Grafana Git Sync: [provisioned dashboards](https://grafana.com/docs/grafana/latest/as-code/observability-as-code/git-sync/provisioned-dashboards/)). Provisioned items stay read-only outside their files; a kind that needs in-flight edits is managed instead. Revisited when a provisioned kind's owners cannot work through pull requests.

## Consequences

- A content change is reviewed, validated and rolled back like code, at the cost of a deploy.
- Example content documents each kind for an adopter and drives the local and CI runs.
- Cost: until TASK-170, this organisation's content sits in the public repository, so it holds no non-public value ([organisation-content.md](organisation-content.md)).

## Checks

- CI: every file under the content root validates against its kind's model; the exported JSON Schemas match the models; example content validates.
- Boot test: an invalid item fails boot naming the file and field; a duplicate id or a kind over its limit fails boot naming the kind; a disabled plugin's content is never read.
- Boot test: an enabled plugin that requires a kind with no items fails boot naming the kind.
- Review: each content directory has a CODEOWNERS entry.

## Migration

Tickets: the first provisioned kind lands with TASK-168 (webhook sender kinds) or the first surface rebuild that moves organisation wording, whichever comes first; it adds the content-root key and the loader. TASK-170 moves the content root to the deployment repository.

**Changes:**
- 2026-10-28: Draft (TASK-167). YAML per item validated by the consumer's model with exported JSON Schema; one content-root key; loaded once at startup for enabled plugins; CODEOWNERS; the image is the version; examples for adopters; Git Sync not adopted for now (human).
- 2026-10-28: Accepted (human review, TASK-167).
