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

**Format.** YAML, read with `yaml.safe_load` (no tags, no anchors across files), one item per file under `<content root>/<owner>/<kind>/[<folder>/...]<id>.yaml`, the file name the item's id, `.yaml` only. `<owner>` is the registering plugin's name, a namespace as a Kubernetes API group or a Backstage plugin id is, so two plugins cannot collide; `<kind>` is the kind's plural kebab name (webhook sender kinds: `webhooks/sender-kinds/<id>.yaml`). Folders under a kind carry no meaning to the model and exist for ownership (a team's folder); ids are unique per kind across folders. `schemas` and `examples` are reserved top-level names. Every file is self-describing: a top-level `kind: <owner>/<kind>` and an integer `version`, as Kubernetes and Backstage files carry `apiVersion` and `kind`; a file whose kind differs from its directory fails boot. A duplicate mapping key fails boot naming the file: YAML 1.2 requires unique keys, PyYAML silently keeps the last, yamllint's `key-duplicates` rule is on by default ([yamllint](https://dyn.manpages.debian.org/testing/yamllint/yamllint.1), [PyYAML behaviour](https://github.com/eth-cscs/stackinator/issues/272)) and Kubernetes' strict field validation rejects duplicates ([KEP-2885](https://www.kubernetes.dev/resources/keps/2885/)). YAML because content holds multi-line templates and nested rules, and the catalogues it resembles are YAML (Backstage's `catalog-info.yaml`, Grafana's provisioning files, Alertmanager's templates); TOML stays for configuration.

**Schema.** The kind's model, owned by its consumer, validates every file. Schemas belong to the app, never to a content root: each kind's JSON Schema is generated into `app/content/schemas/<owner>/<kind>.json` and shipped in the image. The validator is a command over any root, `python -m bin.check_content_schemas [--root PATH ...] [--write] [--export DIR]`: it fails on schema drift or an invalid file, `--write` regenerates the schemas and `--export` writes them for another repository. `make check-content-schemas` runs it in CI over `app/content/` and `app/content/examples/`, and the deployment repository (TASK-170) runs the same command from the pinned image, as Backstage ships `backstage-cli catalog validate` ([catalog](https://backstage.io/docs/features/software-catalog/configuration)) and Kubernetes ships CRD schemas with the controller. Editors map globs to the schemas through `yaml.schemas` or a `# yaml-language-server: $schema=` modeline ([yaml-language-server](https://github.com/redhat-developer/yaml-language-server)). The model reads every `version` the files may hold.

**Location.** The content root is one host configuration key. Interim: `app/content/` in this repository, holding this organisation's content until TASK-170. End state: the organisation's deployment repository builds its image `FROM` the app image pinned by digest, copies its content root in and runs the app's validator in its CI; the app repository keeps only the example set. A production deployment pins a digest, never a moving tag, as Argo CD pins a commit ([tracking strategies](https://argo-cd.readthedocs.io/en/stable/user-guide/tracking_strategies/)). Rejected: fetching content at runtime (S3, an OCI artifact, a git-sync sidecar): it adds a startup dependency and IAM, lets tasks run different content, and splits content's rollback from the code's.

**Loading.** Content loads once in lifespan phase 3 (plugin loading, [lifecycle.md](lifecycle.md)), after the enabled plugins' settings slices, as a plugin's slice validates in plugin boot ([configuration.md](configuration.md)), and only for enabled plugins: a plugin registers its kinds through the `register_content_kinds(registrar)` hookspec, so a disabled plugin's content is never read. The contract is `app/contracts/content/` (`ContentKind`, `ContentKindRegistrar`, `ContentCatalogue`), the implementation `app/infrastructure/content/`, and the loaded catalogue is registered in the service registry. An invalid item fails boot naming the file and the field; a duplicate id, a dangling reference or a kind over its size or count limit fails boot naming the kind. The content root and the limits are the `[content]` settings `root`, `max_file_bytes` (default 16384) and `max_items_per_kind` (default 200); a kind may lower the limits, never raise them. Content is never reloaded: a change is a pull request and a deploy.

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

- CI (`make check-content-schemas`): every file under `app/content/` and `app/content/examples/` validates against its kind's model, and the schemas in `app/content/schemas/` match the models.
- Boot test: an invalid item fails boot naming the file and field; a duplicate mapping key, a `kind` that differs from the file's directory, a file name that differs from the id or an unknown `version` fails boot naming the file; a duplicate id across folders or a kind over its limit fails boot naming the kind; a disabled plugin's content is never read.
- Boot test: an enabled plugin that requires a kind with no items fails boot naming the kind.
- Review: each content directory has a CODEOWNERS entry.

## Migration

Tickets: the loader, the `[content]` settings and the validator landed with TASK-37.1, with no kind registered. The first kind, webhook sender kinds, is registered in TASK-37.2.1 and its content and examples land with TASK-37.3, which adds a CODEOWNERS entry per `app/content/<owner>/` folder when the first content lands; there is no CODEOWNERS file yet. TASK-170 moves the content root to the deployment repository and runs the validator there from the pinned image.

**Changes:**
- 2026-10-28: Draft (TASK-167). YAML per item validated by the consumer's model with exported JSON Schema; one content-root key; loaded once at startup for enabled plugins; CODEOWNERS; the image is the version; examples for adopters; Git Sync not adopted for now (human).
- 2026-10-28: Accepted (human review, TASK-167).
- 2026-11-25: layout `<content root>/<owner>/<kind>/[<folder>/...]<id>.yaml` with self-describing files (`kind`, `version`) and duplicate mapping keys failing boot; schemas owned by the app in `app/content/schemas/` with a validator command over any root; loading moves to lifecycle phase 3 through `register_content_kinds` (the "configuration phase" sentence was wrong); the loader landed (TASK-37.1).
