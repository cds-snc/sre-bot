---
id: TASK-37.1
title: >-
  Webhooks slice 1 (Stack W, W1): provisioned-content loader, dark, with the
  webhooks.md rewrite and the task re-cut
status: Done
assignee: []
created_date: 2026-07-28 18:39
updated_date: '2026-11-27T15:57:00Z'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-168
  - TASK-114.2
references:
  - decisions/provisioned-content.md
  - decisions/organisation-content.md
  - decisions/managed-content.md
  - decisions/webhooks.md
  - decisions/plugins.md
  - decisions/configuration.md
  - decisions/plugin-architecture.md
  - decisions/security.md
  - decisions/reliability.md
  - decisions/migration.md
parent_task_id: TASK-37
priority: high
ordinal: 96000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rescoped 2026-11-25 (TASK-168 direction approved). This slice builds the shared provisioned-content loader that decisions/provisioned-content.md describes and lands the decision records and task edits the TASK-168 design session produced, in one PR (planning rides with code). No content kind is registered yet, so nothing reads the content root and production behaviour does not change.

Loader: YAML per item under <content root>/<kind>/<id>.yaml, read with yaml.safe_load; each file validated by the kind's model (a pydantic model at the file boundary, owned by the kind's consumer); items handed to consumers as frozen values through a read port with an in-memory fake. A kind is registered by an enabled plugin through a registration Protocol in app/contracts/content/ and a register_content_kinds hookspec; a disabled plugin's content is never read. Boot fails, naming the file and field or the kind, on invalid YAML, a YAML tag, a file name that differs from the item id, an unknown schema version, a duplicate id, a kind over its file-size or item-count limit, or a required kind with no items. The content root and the limits are typed [content] settings with defaults. Each kind's JSON Schema is exported to <content root>/schemas/<kind>.json and a CI check fails when a file, an example or an exported schema disagrees with the model. app/content/examples/ is the starting-set root that local.toml and ci.toml point at.

Carried in the same PR: the rewritten decisions/webhooks.md (data plane and control plane, the three layers, the pipeline, the inbox, the canonical event model, the linear-processing rule in interpret and render, responses, authenticity, observability, caller migration) and the ADR touches in security.md, reliability.md, provisioned-content.md, organisation-content.md, managed-content.md, plugins.md and migration.md; the task re-cut and dependency edits of TASK-37 and its follow-ons; TASK-168 ACs 1 to 4 checked (AC 5 moves to TASK-37.5); the TASK-190 hand-offs from the delivery map row 21; the delivery-session change-notice skill file; a short contributor change notice.

Out of scope: any sender kind, any webhook model or engine (TASK-37.2.1), the inbox and ingest (TASK-37.2.2), the instance store and any route change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The loader reads <content root>/<owner>/<kind>/[<folder>/...]<id>.yaml with yaml.safe_load, validates each self-describing file (kind and integer version fields) against the kind's model, and returns frozen items by id through a ContentCatalogue read port in app/contracts/content/ that has an in-memory fake; kinds register through a ContentKindRegistrar Protocol and a register_content_kinds hookspec in lifecycle phase 3, and with no kind registered nothing is read and boot is unchanged (test)
- [x] #2 Boot fails with one CRITICAL log per problem, naming the file and field (or the kind), for invalid YAML, a YAML tag, a duplicate mapping key, a kind field that differs from the file's directory, a file name that differs from the item id, an unknown schema version, a duplicate id across folders, a file over the size limit, a kind over the item limit, and a required kind with no items; a disabled plugin's content is never read (test per case)
- [x] #3 The content root and the limits (file size, items per kind) are typed [content] settings with defaults, set in base, local, ci and production configuration files; no policy value is a module constant; make check-settings-key-ownership is green (test + check)
- [x] #4 Each kind's JSON Schema is generated into app/content/schemas/<owner>/<kind>.json (owned by the app, never by a content root); python -m bin.check_content_schemas validates any --root and fails on schema drift or an invalid file, --write regenerates and --export writes the schemas elsewhere; make check-content-schemas runs it over app/content/ and app/content/examples/ as a blocking CI step; app/content/examples/ exists (test + CI)
- [x] #5 The slice is dark and adds no dependency: no kind is registered, no route or startup behaviour changes, make check-import-contracts is green with no new ignore entry, and make check-package-shape, make check-fake-coverage and make check-test-seams are green (checks)
- [x] #6 decisions/webhooks.md is rewritten (both planes, the three layers, the pipeline and inbox, the canonical event model, the linear-processing rule carried into interpret and render, responses, authenticity, observability including acknowledged_count as approximate and the incident interim adapter tolerated until 37.6.2, caller migration, rejected options, checks, migration), and the ADR touches are applied to security.md, reliability.md, provisioned-content.md (layout, self-describing files, schemas owned by the app, duplicate keys, phase 3 loading), organisation-content.md, managed-content.md, plugins.md and migration.md (review)
- [x] #7 The task re-cut and dependency edits are applied through the backlog CLI per the plan and corrections C6-C10; the TASK-190 hand-offs are placed (the padding AC on TASK-37.4.3 and the two TASK-168 comments); TASK-168 ACs 1 to 4 are checked and AC 5 is moved to TASK-37.5; doc-2 line 121 names Stack W (review)
- [x] #8 The delivery-session change-notice file and End step 5 are in .claude/skills/delivery-session/, and the PR body carries a short contributor change notice: the content layout, the schema check, how to add a content kind (review)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN (2026-11-25). APPROVED 2026-11-25 by the human, with the corrections below, which supersede the decisions and steps they name. Stack W layer W1. Dark: no kind is registered.

CORRECTIONS (approved 2026-11-25; aligned with current framework practice rather than the prior ADR text)
C1 (supersedes D7 layout): <root>/<owner>/<kind>/[<folder>/...]<id>.yaml. <owner> is the registering plugin's name, a namespace like a Kubernetes API group or a Backstage plugin id, so two plugins cannot collide; <kind> is the kind's plural kebab name (webhook sender kinds: app/content/webhooks/sender-kinds/<id>.yaml). Nested folders under a kind carry no meaning to the model; they exist for CODEOWNERS (a team folder). Ids are unique per kind across folders.
C2 (new): every file is self-describing: a top-level 'kind: <owner>/<kind>' and an integer 'version', as Kubernetes (apiVersion/kind), Backstage (apiVersion/kind) and Grafana provisioning (apiVersion) files are. The loader fails a file whose kind differs from its directory's kind.
C3 (supersedes D9 location and OQ1): schemas belong to the app, never to a content root: one generated set at app/content/schemas/<owner>/<kind>.json, shipped in the image. The validator is a command over any root: python -m bin.check_content_schemas [--root PATH ...] [--write] [--export DIR]; CI runs it over app/content/ and app/content/examples/; TASK-170's deployment repository runs the same command from the pinned image (Backstage's catalog validate CLI; Kubernetes ships CRD schemas with the controller). Editors map globs to the schemas (yaml.schemas or a $schema modeline).
C4 (resolves OQ6, ADR gap): duplicate mapping keys fail boot naming the file (YAML 1.2 requires unique keys; PyYAML keeps the last silently; yamllint key-duplicates on by default; Kubernetes Strict field validation rejects duplicates). provisioned-content.md Format and Checks gain the rule.
C5 (resolves the loading-phase conflict): content loads in lifecycle phase 3 (plugin loading), after the enabled plugins' slices, as configuration.md:71 validates a plugin's slice in plugin boot; provisioned-content.md Loading is corrected.
C6 (resolves OQ3): coordinators carry their first child's dependencies (TASK-145.5, 145.10 precedent): 37.2 -> 37.1; 37.4 -> 37.3; 37.6 -> 37.2.2, 37.4.1. Commands l, n and f use these sets.
C7 (resolves OQ2, packet OQ14 corrected): TASK-88 depends on 37.6.2, not 37.4 or 37.5: modules/slack/webhooks.py is on the aws_platform seam baseline TASK-88 retires and is deleted by 37.6.2 (its incident caller incident_alert.py:67 goes with Lane A's 145.7.10, transitively before 37.6.2). Command r for 88 uses --dep TASK-25.2,TASK-36.1.3,TASK-36.3,TASK-37.6.2,TASK-109,TASK-114.2,TASK-145.9. doc-11 C7 and C9 Waits-on edited (human-approved).
C8 (resolves OQ4): TASK-168 AC 5 moves to 37.5 and is removed from 168 (human, 2026-11-25 session prompt).
C9 (cross-lane): no edit to Lane A task files in flight (145.7.11): its note becomes a 37.4.3 AC (the button value carries instance_ref and the inbox item id, coordinated with the incident feature) and a doc-11 open decision. decisions/webhooks.md Observability states that acknowledged_count is approximate and the incident interim adapter is tolerated until 37.6.2, which is what Lane A's 145.7.10 AC #3 asks for.
C10 (CODEOWNERS gap): 37.3 gains an AC: a CODEOWNERS entry per app/content/<owner>/ folder when the first content lands, with a check; TASK-170 gets a note (the validator command and the CODEOWNERS entries move with the content).
C11: doc-2 line 121 is edited in this session (step 10).

REFERENCES CONSULTED: decisions/provisioned-content.md, organisation-content.md, managed-content.md, webhooks.md (current), plugins.md, plugin-architecture.md; the approved TASK-168 research outline (held outside the repo, untracked) for the webhooks.md rewrite, the ADR touches and the task operations.

GROUNDING (path:line, verified 2026-11-25)
- PyYAML is a direct dependency (app/pyproject.toml:22, uv.lock 6.0.3); the only production yaml.safe_load is app/infrastructure/i18n/loader.py:10,112. jsonschema is NOT in uv.lock: no new dependency, the schema check compares pydantic model_json_schema() output to the checked-in file. model_json_schema has no production use yet (tests only: tests/unit/packages/access/request/test_access_request_schemas.py:10,29).
- Registry: contracts are resolved by Protocol from the svcs registry (app/server/services.py:35 CoreService, :98 register_core_services). A service that needs plugin input cannot be a CORE_SERVICES builder (build takes no arguments), so the loaded catalogue is registered as a value the way HostInfo is (app/server/lifespan.py:230 registry.register_value).
- Boot sequence: app/server/lifespan.py:247-253 get_plugin_manager, load_plugins (a plugin load failure stops startup), resolve_plugin_requirements. The content step goes directly after :253 and before translation and registration hooks (:255+). call_hook_per_plugin (app/server/plugins/boot.py:50) skips blocked (disabled) plugins and logs plugin_boot_failed then re-raises: the disabled-plugin rule needs no new code.
- Hookspec precedent: register_i18n_resources(registry: I18nResourceRegistrar) at app/contracts/plugins/hookspecs.py:35-41; registrar Protocol at app/contracts/i18n/resources.py:35. Hookspecs are public API (plugins.md:28).
- Boot-failure precedent: PluginRequirementsUnmetError (app/server/plugins/requirements.py:57) collects every unmet requirement, logs one CRITICAL each, then aborts. The loader mirrors it.
- Settings: a slice is a ConfigurationSlice with toml_table_header and env_prefix (app/server/configuration/server_settings.py:10-23; app/server/languages/settings.py). Every table in config/*.toml must be owned by exactly one slice and present in config/base.toml (app/bin/check_settings_key_ownership.py:2-20). There is no directory-path host key today; app/config/{base,local,ci,production}.toml exist.
- Import-linter: the infrastructure-siblings contract lists the families whose direct import is forbidden to packages/features/etc. (app/pyproject.toml:416-419, forbidden_modules = records, coordination); the new family infrastructure.content joins forbidden_modules. This adds no ignore entry (nothing imports it yet). contracts-leaf (:312-316) allows contracts importing pydantic (ConfigurationSlice already does).
- Make and CI: app/Makefile:110-124 check-* targets (each runs uv run python -m bin.<name>); .github/workflows/ci_code.yml:61-77 runs them as blocking steps in job "tests" (:10). No generated-file check exists; this slice adds the first.
- Tests: app/tests/unit/infrastructure/<service>/test_<service>_<thing>.py (e.g. i18n/test_loader.py); service_registry fixture at app/tests/conftest.py:136.

DESIGN DECISIONS (each with its reason)
D1 Registration Protocol and read port live in app/contracts/content/ (kinds.py): ContentKind[T] (frozen dataclass: name, model: type[BaseModel], build: Callable[[model], T], versions: frozenset[int] = {1}, required: bool = False, optional max_file_bytes and max_items), ContentKindRegistrar (Protocol: register(kind)), ContentCatalogue (Protocol: items(kind) -> Mapping[str, T]), ContentProblem (frozen dataclass: kind, file, field, message) and ContentLoadError. Reason: contract in contracts/, implementation in infrastructure/content/, consumers see the Protocol only (dependency-injection.md; mirrors contracts/i18n). The pydantic model type in the contract is the file-boundary model the ADRs assign to the kind's owner.
D2 Hookspec register_content_kinds(self, registrar: ContentKindRegistrar) -> None on FeatureLifecycleSpecs. Reason: "only for enabled plugins" is the existing per-plugin hook mechanism; a kind is therefore registered by its consumer's plugin and a disabled plugin is skipped by call_hook_per_plugin.
D3 Wire into lifespan this slice, with zero kinds. Reason: boot failure and enablement are the behaviour under test, and an unwired loader rots; with no kind it reads nothing, so it is dark and one revert removes it. Rejected: tests-only construction (nothing proves the boot path). Placement is after plugin loading and requirements, because kinds are only known once plugins are loaded; provisioned-content.md says "configuration phase": this PR corrects that sentence.
D4 Loaded catalogue is registered with registry.register_value(ContentCatalogue, ...) in lifespan. An InMemoryContentCatalogue fake (infrastructure/content/in_memory.py) serves consumer tests (organisation-content.md: a read port with an in-memory fake).
D5 Types: files are untrusted input, so pydantic at the boundary (the kind owner's model); the loader's own results are frozen dataclasses (ContentProblem, and the Mapping of built frozen items). No Pydantic inside the loader's internals. No domain entity is introduced, so the domain-model-evolution gate is not applicable: the loader holds no persisted entity, no record, no cardinality; an item's domain shape belongs to each kind's owner (TASK-37.2.1 for sender kinds) and takes the gate there.
D6 Settings: a new [content] slice, ContentSettings in app/infrastructure/content/settings.py (table "content", env CONTENT__): root: Path (host key), max_file_bytes: int = 16384, max_items_per_kind: int = 200 (the generic ceilings; a kind may lower them through ContentKind but never raise them, effective = min). Values: base.toml root = "content" (the interim organisation content, app/content/, no kinds yet so nothing is read); local.toml and ci.toml root = "content/examples"; production.toml inherits base. Relative paths resolve against the app directory the configuration files resolve against (verify at implementation: server/configuration/loader.py:33). Policy and bounds are settings, not constants (the standing rule); the only literals are the reserved directory names "schemas" and "examples", which must never change, and the item-id pattern ^[a-z0-9][a-z0-9_-]{0,63}$. Webhook-specific limits ([webhooks]) arrive in TASK-37.2.1 and are passed in through ContentKind.
D7 Layout: <root>/<kind>/**/<id>.yaml, nested folders allowed (a team may own a folder, provisioned-content.md Ownership), id unique per kind across folders; the file stem must equal the id field; only .yaml; symlinks and paths resolving outside the root are rejected; "schemas" and "examples" are reserved kind names refused at registration so app/content/examples/ and app/content/schemas/ never read as kinds.
D8 Safe YAML: yaml.safe_load through a SafeLoader subclass that rejects duplicate mapping keys (PyYAML silently keeps the last), file size checked by stat before reading, pydantic errors reported by location and message with input values excluded (no content value in a log). Python tags are rejected by safe_load itself. A top-level integer "version" is required and checked against ContentKind.versions before model validation.
D9 Schema export and check: bin/check_content_schemas.py (python -m bin.check_content_schemas [--write]); builds the plugin manager the way the lifespan does, collects kinds through register_content_kinds, and compares model_json_schema() (sorted keys, indented, trailing newline) with app/content/schemas/<kind>.json; also validates every item under app/content/ and app/content/examples/ with the same loader code. Make targets check-content-schemas and export-content-schemas; CI step "Content schema check" after the test-seam step in ci_code.yml. One schemas directory (app/content/schemas/, beside the interim content root) rather than a copy per root: OQ1. With no kind registered the check passes with nothing to compare, and the unit tests prove the mechanism with a test-only kind.
D10 app/content/examples/ ships a README.md only (what the examples are, example.com and no organisation data, how to add one) and no items: no kind exists. The first kinds' examples arrive with TASK-37.3 (sender kinds). The test-only kind used by tests lives in app/tests/ fixtures, never in app/content/.
D11 Dependencies: none added (no jsonschema, no new YAML library).
D12 NEW-A (machine principals) gets a pointer only: a short "Machine callers" paragraph in security.md Webhooks naming the three caller classes and stating that trusted issuers and claim mapping are decided in a separate record by the new task; no decision text here. Reason: the direction makes NEW-A an independent infrastructure-owned decision that depends only on TASK-168 and must be reviewed on its own.

SIZE ESTIMATE AND GATE
Production Python: ~330 LOC, 9 files: contracts/content/__init__.py, kinds.py; infrastructure/content/__init__.py, loader.py, settings.py, in_memory.py, schema.py; bin/check_content_schemas.py; plus edits to contracts/plugins/hookspecs.py (+8), server/lifespan.py (+14). Config/CI one-liners: config base/local/ci toml, app/Makefile, ci_code.yml, pyproject.toml (one forbidden_modules entry). Not production code: ADRs (8 files), task files, the skill files, app/content/examples/README.md, tests (~9 files).
Verdict: LOC and subsystem gates pass for the code (one subsystem, plus a CI step). The raw file count (production Python 9, plus 6 config or CI one-liners, plus ADR and task-file edits) exceeds ~10 only when counting those. Exception requested, not a split: the ADR rewrite, ADR touches, task re-cut, skill file and contributor note are assigned to this slice by the human-approved TASK-168 direction under "planning rides with code" (no standalone planning or docs PRs); they are reviewed as prose, not behaviour, and are separable by commit (commit 1 loader and tests, commit 2 ADRs, commit 3 task and skill files) so the code review stays under 30 minutes. A dark slice with no consumer, one revert. Expand/contract does not apply (nothing is replaced); no mechanical refactor is mixed in.

ORDERED STEPS
Phase A: loader (TDD, tests first)
1. Write the failing tests of the matrix below.
2. contracts/content/kinds.py and __init__.py: D1 types. Add register_content_kinds to contracts/plugins/hookspecs.py (after register_i18n_resources, :41) with docstring; update the FeatureLifecycleSpecs docstring list.
3. infrastructure/content/settings.py (D6) and the [content] table in app/config/base.toml, local.toml, ci.toml (production inherits base; add an explicit production.toml line only if the ownership check demands it).
4. infrastructure/content/loader.py: ContentLoader (implements ContentKindRegistrar and builds a catalogue), D7 and D8; collects every problem and raises ContentLoadError once. in_memory.py: InMemoryContentCatalogue. schema.py: schema_text(kind) shared by the export and the check.
5. server/lifespan.py after :253: build ContentLoader, call_hook_per_plugin(pm, "register_content_kinds", ...), load(), on ContentLoadError log one CRITICAL content_load_failed per problem (file, field, kind) and re-raise, then register_value(ContentCatalogue, catalogue). Add infrastructure.content to forbidden_modules at app/pyproject.toml:419.
6. bin/check_content_schemas.py, Makefile targets check-content-schemas and export-content-schemas, CI step after the test-seam step (.github/workflows/ci_code.yml:77), app/content/examples/README.md.
Phase B: decisions (after the loader is green)
7. Rewrite decisions/webhooks.md to the approved outline: front matter, banner removed, Context (today's surface and antipatterns compressed, why reassessed), Decision 1-10 (placement; three layers; pipeline with the linear-processing rule binding interpret and render (security.md linear-processing, singular JSONPath only, no regex in content, linear decoders, cap-sized adversarial tests, linear token-bounded email matcher with a Slack lookup cap, TASK-190 hand-off); content rules; responses; canonical model; two planes and three caller classes; authenticity pointer; URLs; observability including counters as metrics; security additions; caller migration), Rejected, Consequences (legacy no-dedupe exception and its end), Checks, Migration, Changes. Cite sources already in the research outline.
8. ADR touches in the same PR: security.md (Webhooks: caller classes, SNS v1 and v2, 403, TopicArn allowlist, SubscribeURL host rule, Standard Webhooks tier, secret storage, output encoding, passthrough rule, instance_ref, two-layer rate limit; NEW-A pointer only, D12); reliability.md (webhook inbox as a use of the conditional write and its item state machine; the delivery-id key form; the legacy no-dedupe exception; whether it triggers TASK-34 left as an open decision); provisioned-content.md (Migration: loader landed; the loading-phase sentence corrected per D3; reserved names and nested folders per D7; Changes line); organisation-content.md (kinds table names the engines; non-public value in a managed record encrypted at application level and never exported); managed-content.md (webhook-instance kind's write path is the control plane); plugins.md (hookspec list gains register_content_kinds and names the webhooks extension point); migration.md (caller-migration phases; URL decision rides with TASK-37.4.3 AC 6). Each gets a dated Changes line.
Phase C: skill and task files (after human approval of this plan)
9. Copy /workspace/.claude/skills/delivery-session/change-notice.md and SKILL.md into .claude/skills/delivery-session/ (file copy, no design) and confirm the change-notice PR rule is present.
10. doc-2 line 121 (Wave 5, Webhooks): rewrite the row to Stack W (TASK-37.1 -> TASK-37.2.1 -> TASK-37.2.2 -> TASK-37.3, handoff doc-18 at backlog/docs/stacks/doc-18 - Stack-W-handoff.md, already created) followed by the single PRs from main per the re-cut. Done by the human or the implementing session on instruction; this planning session does not edit doc-2 or doc-18.
11. Task operations with the backlog CLI, in this order (commands below).
12. TASK-168: comments, check ACs 1-4 (--check-ac 1 --check-ac 2 --check-ac 3 --check-ac 4), move AC 5 to TASK-37.5. 168 stays To Do until 37.1 merges, then Done (agent closes it).
Phase D: gates and PR (Verification section).

TASK OPERATIONS (run only after approval; `--dep` on edit REPLACES the whole list, so each command lists the full target set; labels migration,webhooks,phase-4 and milestone m-4 copied from TASK-37.x; run from the worktree root; verify every id printed by create before the next command depends on it)
Create the children first (so edits can point at them):
 a. backlog task create "Webhooks slice 2.1: event model and engines (dark)" --parent TASK-37.2 --dep TASK-37.1 -l migration,webhooks,phase-4 -m m-4 --priority high -d "<packet row 37.2a: generator skeleton; InboundEvent (CloudEvents names), event types alert, notification, slack.passthrough; SenderKind; WebhookInstance with instance_ref, owner, auth_tier, destinations; condition matcher; python-jsonpath extraction; python-liquid renderer with limits and boot name check; Slack poster adapter with escaping; event-consumer hookspec; linear token-bounded email matcher with a lookup cap (F-I); [webhooks] settings. Dark, one revert. Registers the first content kind through register_content_kinds.>" --ac "<engines and model per row; adversarial cap-sized body through interpret and render runs well under 1 s; matcher is linear with a Slack lookup cap; import-linter green, no new ignore entry; core imports no slack_sdk>" --ref decisions/webhooks.md,decisions/organisation-content.md,decisions/provisioned-content.md
 b. backlog task create "Webhooks slice 2.2: async ingest and inbox (dark)" --parent TASK-37.2 --dep TASK-37.2.1,TASK-58.2 ... -d "<row 37.2b: protocols aws_sns (v1 and v2, 403, TopicArn, SubscribeURL host rule, async certificate fetch) and legacy_slack_json; body cap per protocol; WebhookStore port; inbox store with conditional insert, item state machine and ownership tokens; inline processor with deadline; lease-guarded sweeper; async route not mounted; KMS secret helper; two-layer rate-limit settings>" --ac "...; includes the old TASK-37.2 AC 7 (SignatureVersion 1 and 2 accepted)" 
 c. backlog task create "Webhooks slice 4.1: instance backfill" --parent TASK-37.4 --dep TASK-37.3 ...; d. "Webhooks slice 4.2: shadow" --parent TASK-37.4 --dep TASK-37.4.1; e. "Webhooks slice 4.3: cutover" --parent TASK-37.4 --dep TASK-37.4.2,TASK-145.7.11 with ACs: old 37.4 AC 6 (WAF scope-down and /api/v1/hook decision), AC 7 (pin harness rewired, F-G kept), and the TASK-190 AC "before cutover, the just-under-cap pin pads text and a blocks string, and the route serves it well within the integration budget"; plus the 500 and 503 pin update with its reason.
 f. backlog task create "Webhooks: management plane coordinator" --parent TASK-37 (becomes TASK-37.6, confirm the id) then g. "Management service and API" --parent TASK-37.6 --dep TASK-37.2.2,TASK-37.4.1 (37.6.1) and h. "Slack binding; delete the legacy admin" --parent TASK-37.6 --dep TASK-37.5,TASK-37.6.1,TASK-36.1.4 (37.6.2).
 i. backlog task create "Webhooks slice 7: inbox on QueueService" --parent TASK-37 --dep TASK-37.5,TASK-34,TASK-113 (37.7; carries the old 37.5 text); j. "Webhooks slice 8: instances onto managed content" --parent TASK-37 --dep TASK-37.6.1 (37.8; notes name the first of TASK-166, 165, 146 re-cut as a dependency to add when one lands).
 k. backlog task create "Machine principals for inbound API callers" --dep TASK-168 -l security,webhooks (next free top-level id, expected TASK-194; confirm) with a description pointing at the security.md Machine callers paragraph.
Rewrite existing tasks (title, description, acs replaced with --acceptance-criteria so surviving text keeps its checks):
 l. backlog task edit 37.2 -t "Webhooks slice 2: event model, engines, async ingest and inbox (coordinator of 37.2.1 and 37.2.2)" -d ... --dep TASK-37.1 ; ACs: all children done. Old ACs 1-6 intent now in 37.2.1 and 37.2.2 and 37.3 (add --comment first, as for 37.1; F-E and F-F comments become tests in 37.3).
 m. backlog task edit 37.3 -t "Webhooks slice 3: sender kinds as content, the Notify revocation handler and the incident alert consumer (dark)" --dep TASK-37.2.2,TASK-25.8 (comment first recording old ACs; old text was intent and renderer).
 n. backlog task edit 37.4 -t "Webhooks slice 4: shadow and cutover (coordinator of 37.4.1, 37.4.2, 37.4.3)" --dep TASK-37.3 ; its old ACs 6 and 7 and the padding AC are on 37.4.3 (comment first).
 o. backlog task edit 37.5 -t "Webhooks slice 5: contract, delete legacy processing and enforce passthrough hardening" --dep TASK-37.4.3 with --acceptance-criteria including AC "bin/deploy-checks.zsh post: the Non-JSON section's webhook pattern exclusion (added by TASK-28.2) is removed and any non-JSON line FAILs once import-time pattern discovery is gone" (moved from TASK-168 AC 5); the old fan-out text moves to 37.7 (comment first).
 p. backlog task edit 37 -d ... (two planes, inbox, event model; slices list 37.1 to 37.8) with the ACs rewritten (--comment first); dependency stays TASK-168.
 q. backlog task edit 47 --dep TASK-37.6.1 (drops 37.4, 46) with the narrowed scope (standard_webhooks protocol, native protocol, issuance through 37.6.1); 48 --dep TASK-47,TASK-37.6.1,<NEW-A id> (caller-migration programme); 49 --dep TASK-37.4.3,TASK-3 (drops 47; two-layer limit).
 r. Outside the programme: backlog task edit 147.5 --dep TASK-147.4,TASK-37.4.3,TASK-37.2.1 plus description addition (github protocol; fetch state through the GitHub App, not payload fields); backlog task edit 40 --dep TASK-37.5,TASK-37.6.2,TASK-145,TASK-39,TASK-35,TASK-26.1,TASK-114.2,TASK-118 and remove "webhook CRUD and admin views" from its scope (task-40:35); backlog task edit 88 --dep TASK-25.2,TASK-36.1.3,TASK-36.3,TASK-37.5,TASK-109,TASK-114.2,TASK-145.9 (OQ2 below); --comment only on 25.8 (37.3 consumes it), 34 (the webhook inbox is a candidate first consumer), 145.7.11 (button value switches to instance_ref plus the inbox item id in 37.4.3; scope unchanged) and the incident re-cut task (authenticated alert-intake endpoint after the machine-principal task).
 s. backlog task edit 37.1 --dep TASK-168,TASK-114.2 and --notes naming why TASK-7, 36.2, 27.2, 27.5, 108 and 109 were dropped (completed).
 t. TASK-190 hand-offs (delivery-map row 21): the 37.4.3 padding AC (in e) and, on TASK-168, backlog task edit 168 --comment "<the rebuilt address matcher is linear and token-bounded and bounds Slack lookups (F-I: one users_lookupByEmail per match, unbounded)>" and --comment "<the rewritten decisions/webhooks.md carries security.md's linear-processing rule into the interpret and render stages; the re-cut keeps the 37.4 padding AC>".
 u. backlog task edit 168 --remove-ac 5 is NOT used (never delete an AC); instead --comment "AC 5 moves to TASK-37.5 (human-approved)" and the human decides whether AC 5 is removed (OQ4).

TEST MATRIX (intended files under app/tests/; each docstring states behaviour and stub strategy only)
- unit/infrastructure/content/test_content_loader_loads_items.py: happy path (two kinds, nested folder, frozen result, items by id), only registered kinds' directories are read, zero kinds reads nothing even when the root is missing.
- unit/infrastructure/content/test_content_loader_rejects_files.py: duplicate id across folders; file name differs from id; invalid YAML; YAML Python tag rejected by safe_load; duplicate mapping key; unknown version; .yml and symlink outside the root; model field error names file and field with no input value in the message; every problem is reported in one error.
- unit/infrastructure/content/test_content_loader_limits.py: file over max_file_bytes (kind lowering works, kind raising does not), items over max_items_per_kind names the kind, required-but-empty names the kind, optional-empty passes, boundary at exactly the limit.
- unit/infrastructure/content/test_content_settings_defaults.py: defaults, env override, toml table owned once.
- unit/infrastructure/content/test_content_schema_export_matches_model.py: exported text equals the file; drift fails; --write regenerates; a file that fails its model fails the check.
- unit/infrastructure/content/test_content_examples_validate.py: every example under app/content/examples/ for every registered kind validates; a test-only kind with a fixture example proves the path.
- unit/infrastructure/content/test_content_catalogue_in_memory.py: the fake honours the ContentCatalogue contract.
- unit/server/test_server_lifespan_content_boot.py: with a stub plugin registering a kind the catalogue is registered and resolvable; an invalid file aborts startup with one CRITICAL naming the file and field; a disabled plugin's hook and directory are never called or read; zero kinds boots unchanged.
- unit/contracts/test_content_kind_contract.py: reserved names, id pattern and version rules refused at registration.

AC TRACEABILITY
AC1 -> steps 2,4,5 -> loads_items, catalogue_in_memory, lifespan_content_boot. AC2 -> steps 4,5 -> rejects_files, limits, lifespan_content_boot. AC3 -> step 3 -> settings_defaults + make check-settings-key-ownership. AC4 -> step 6 -> schema_export_matches_model, examples_validate + the CI step. AC5 -> steps 5,6 -> check-import-contracts, check-package-shape, check-fake-coverage, check-test-seams, and a diff showing no registered kind and no pyproject dependency change. AC6 -> steps 7,8. AC7 -> steps 11,12 (task operations) and 10 (doc-2). AC8 -> step 9 and the PR body.

ASSUMPTIONS AND DOUBTS (with verification)
- Contracts may import pydantic (ConfigurationSlice does): verify with make check-import-contracts at step 2.
- Relative [content] root resolves from the app directory in image and CI: verify server/configuration/loader.py:33 and the Dockerfile WORKDIR; if not, resolve against the configuration directory.
- The mypy config accepts yaml without stubs (i18n/loader.py already imports it): verify in the full mypy run.
- Adding a hookspec to FeatureLifecycleSpecs needs no hookspec-deprecation step (an addition, not a change): verify decisions/hookspec-deprecation.md.
- check_fake_coverage may require the in-memory fake to be registered in its baseline logic: verify by running it at step 4.
- A new top-level id is TASK-194 and child ids follow creation order (37.6, 37.7, 37.8 and .1/.2 children): confirm from each create output; stop if they differ.
- backlog task edit --dep replaces the list (confirmed from the CLI help): every command above gives the full set.

BLAST RADIUS AND ROLLBACK
The loader is wired into lifespan but registers no kind, so boot reads no directory and behaviour is unchanged. Failure modes if wrong: the lifespan edit raises at startup (caught by CI app-boot tests; the ECS circuit breaker rolls back); the new [content] table breaks configuration load if a toml key is mistyped (the ownership check and config tests catch it); the new CI step could block unrelated PRs if flaky (it is deterministic). One git revert restores everything; the task-file and ADR edits revert with it. Ordering constraints: none for deploy (no env var, terraform or IAM change). Task operations are applied before merge but after approval; they touch only backlog files.

GATES
During: uv run ruff check . and the targeted tests above, from app/. At the end, once each and sequentially: uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)', then uv run pytest tests --ignore=tests/smoke. Plus make check-import-contracts, make check-settings-key-ownership, make check-package-shape, make check-fake-coverage, make check-test-seams, make check-content-schemas. No bin/deploy-checks.zsh run: no terraform, IAM, SSM or env-name change.

CHANGE NOTICE: contributor note only (dark slice): the content root key and its values, make check-content-schemas and export-content-schemas, how to add a sender kind (model, register_content_kinds hookimpl, files and examples under <root>/<kind>/, run the export).

OPEN QUESTIONS: none (all resolved by C1-C11).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-20 (TASK-27.5 planning): the full-table read is RecordStore.read_all(table, *, max_items), all items or a PERMANENT_ERROR (RECORD_READ_LIMIT_EXCEEDED) past the cap, strongly consistent, no order (decisions/cloud-portability.md contract 4, whole-table reads). list_all and lookup use it with max_items from a documented webhooks package setting with a default; lookup filters client-side, allowed only because the webhooks table is configuration-sized.

2026-11-25 (re-cut, human-approved plan step s): dependencies TASK-7, TASK-36.2, TASK-27.2, TASK-27.5, TASK-108 and TASK-109 dropped. All are Done, and they served the old 37.1 scope (the frozen Webhook domain model and the RecordStore-backed store), which moved to TASK-37.2.2 (the WebhookStore port and the inbox store). The rescoped loader needs only TASK-168 (the approved design) and TASK-114.2 (the package generator conventions).

2026-11-25 implementation (Stack W W1, In Progress until the PR merges).
Loader: app/contracts/content/ (ContentDocument base with kind/version/id, ContentKind with owner and name, ContentKindRegistrar, ContentCatalogue, ContentProblem, ContentLoadError), app/infrastructure/content/ (loader, settings [content] root/max_file_bytes/max_items_per_kind, in_memory fake, schema), register_content_kinds hookspec, lifespan phase 3 load_provisioned_content (one CRITICAL content_load_failed per problem with kind/file/field/reason, then abort; catalogue registered by value), [content] validated in the configuration phase with the other infrastructure slices (host_configuration._validate_slices), bin/check_content_schemas.py with --root/--write/--export, make check-content-schemas and export-content-schemas, CI step after the test-seam step, app/content/examples/README.md, infrastructure.content in forbidden_modules. Owner names may be dotted (entry points such as incident.response). Unhashable YAML keys and a kind path that is a file are named problems (tests added). Dark: no kind registered; check-content-schemas reports 0 kinds.
ADRs: webhooks.md rewritten; touches in security, reliability, provisioned-content (layout, self-describing files, schemas owned by the app, duplicate keys, phase 3), organisation-content, managed-content, plugins, migration, README index. webhooks.md section 8 holds the acknowledged_count-approximate line that Lane A TASK-145.7.10 AC #3 cites; it names Lane A's planned AlertAcknowledgements adapter.
Re-cut applied with the CLI (see TASK-168 comment). doc-2 Wave 5 row names Stack W. Delivery-session change-notice.md and SKILL.md copied from /workspace (identical).
Gates (from app/): ruff check . All checks passed; targeted content/server/contracts tests 698 passed; full mypy 33 errors in 11 files, none in a file this branch touches (legacy modules/webhooks, modules/role, modules/incident, infrastructure/i18n, integrations/slack/channels.py, features/incident/core/adapters/google_calendar.py), pre-existing; full pytest 8151 passed, 235 warnings in 265s; make check-import-contracts 15 kept 0 broken; check-settings-key-ownership OK; check-package-shape OK (2 baselined); check-fake-coverage OK (4 baselined); check-test-seams OK (47 and 12 baselined); check-content-schemas ok (0 kinds). No deploy-checks: no terraform, IAM, SSM or env-name change.
Open for the human: TASK-193's MultilingualText rule (bot wording multilingual, sender content in its source language) sits as comments on 37.2.1 and 37.3; decide at 37.2.1 planning whether it becomes an AC. Task files whose slugs no longer match their titles are renamed with git mv in the session's commands.

2026-11-25: committed 1197c9f on stack-w/task-37.1-content-loader, PR #1889 open (Stack W bottom layer; stays in review until W2 is open above it). In Progress.

2026-11-27: merged in #1889 (ba7e479b). All 8 ACs checked, no post-deploy step (dark layer). Closed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @claude
created: 2026-09-16 13:47

---

2026-09-16 review of TASK-25.2.5: TASK-27 added as a dependency. Scope item 3 requires the WebhookStore to expose increment_invocation/increment_acknowledged over the StorageService Protocol, but that Protocol (app/infrastructure/storage/protocol.py) offers only put, put_if_not_exists, get, query and delete. There is no update and no atomic counter operation, and decisions/webhooks.md forbids resolving that with a read-modify-write. Without TASK-27 this slice would either grow a vendor-shaped update on the Protocol (the exact leak TASK-27 exists to remove, see decisions/cloud-portability.md contract 4) or hand-roll a race. New AC#5 pins the atomicity requirement. Two further gaps for whoever plans this slice: (a) list_all_webhooks and lookup_webhooks are DynamoDB scans today and the Protocol has no scan or list equivalent either, so the store needs a capability-shaped answer for full-table reads; (b) AC#4 assumes import-linter is running, but it is not installed or wired in app/ today (decisions/toolchain.md still describes it as pending) - the working precedent is the freeze-baseline guard scripts under app/bin/.

---

author: @claude
created: 2026-09-16 13:59

---

2026-09-16: dependency retargeted from TASK-27 to TASK-27.2 now that TASK-27 is decomposed. TASK-27.2 is the slice that adds the atomic update, the atomic numeric increment and the bounded full-table list this store needs, and it is scoped to land with this task as its first consumer - merge it immediately before this slice, or in the same PR if the size gate allows. TASK-27.1 (the typed key-condition read) is a prerequisite of TASK-27.2 and so is transitively required.

---

created: 2026-10-13 19:59

---

2026-10-13 records/incidents layout decision: TASK-27.2 narrowed to the update operation: counters use update with an increment change (missing counter counts as 0; not idempotent under SDK retry, acceptable for counters), the item must exist so create writes the zeroed counters. list_all and lookup use the full-table read shaped by TASK-27.5 (dependency added), not a bounded list from TASK-27.2. Plan refresh needed when this is picked up.

---

created: 2026-11-25T20:27:00Z

---

2026-11-25 re-cut (TASK-168 direction approved by the human): this task is no longer the domain model and RecordStore store. Where each old AC's intent now lives:
- Old #1 (frozen Webhook model and a RecordStore-backed WebhookStore; no direct integrations.aws.dynamodb call in the read/write path): the model is WebhookInstance (TASK-37.2.1); the WebhookStore port over the records contract is TASK-37.2.2; the legacy dynamodb calls in modules/slack/webhooks.py are deleted by TASK-37.6.2 and the route's own reads move at TASK-37.4.3.
- Old #2 (no caller above the store handles raw DynamoDB item shapes): TASK-37.2.2 for the store and the new route; TASK-37.4.3 for the route cutover; TASK-37.6.2 for the admin surface.
- Old #3 (URLs and behaviour unchanged, TASK-36 smoke tests pass before and after): held by every production slice (TASK-37.4.3, TASK-37.5, TASK-37.6.2) through the TASK-36.2 and TASK-36.1.4 pins; this slice is dark and changes no route.
- Old #4 (import-linter green, no new ignore entry; the capability imports no infrastructure/ or server/ module): restated on this slice for the loader's own contracts and carried by TASK-37.2.1 and TASK-37.2.2 for the capability.
- Old #5 (counters through one atomic RecordStore operation): superseded. Invocation and acknowledgement counters become metrics (rewritten decisions/webhooks.md, Observability), not stored attributes; the atomic increment stays a RecordStore capability for any later consumer.
Old scope items: the capability skeleton and WebhookSettings move to TASK-37.2.1; the WebhookSource enum is replaced by the protocol and sender-kind model (TASK-37.2.1, TASK-37.2.2); repointing the route and admin callers is TASK-37.4.3 and TASK-37.6.2. The old dependencies TASK-7, TASK-36.2, TASK-27.2, TASK-27.5, TASK-108 and TASK-109 are all completed and no longer needed here; the loader depends on TASK-168 and TASK-114.2 only.

---

created: 2026-11-25T20:42:00Z

---

2026-11-25: plan approved by the human with corrections C1-C11 (in the plan): owner-namespaced layout with optional folders, self-describing files, schemas owned by the app with a validator command over any root, duplicate keys rejected, loading in lifecycle phase 3, coordinator deps, TASK-88 on 37.6.2, TASK-168 AC 5 moved, no edits to in-flight Lane A task files, CODEOWNERS on 37.3.

---
<!-- COMMENTS:END -->
