---
id: TASK-110
title: >-
  Load plugins from pyproject entry points and make any plugin load failure
  abort boot
status: Done
assignee: []
created_date: '2026-09-24 19:59'
updated_date: '2026-10-06 17:09'
labels:
  - plugin-architecture
  - plugins
milestone: m-7
dependencies:
  - TASK-107
  - TASK-35
  - TASK-14
references:
  - decisions/plugins.md
  - decisions/lifecycle.md
  - decisions/toolchain.md
priority: high
type: feature
ordinal: 252000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugins.md: discovery comes from entry points declared in pyproject.toml, loaded by pm.load_setuptools_entrypoints. Every mature pluggy host uses a declared list, never a folder scan. An entry-point target that will not import, or a hookimpl that raises during a hook call, aborts the lifespan.

Today auto_discover_plugins walks packages/ and modules/ with pkgutil.walk_packages and logs and skips a package that fails to import, so a broken feature silently does not load. No entry points are declared.

Scope:
- declare one entry point per plugin module under the host's group (the namespace constant from TASK-107);
- use dotted names for umbrella subdomains ("access.request");
- targets are the current flat import paths (packages.*) and are repointed to features.* or capabilities.* by each package move;
- replace the filesystem walk with load_setuptools_entrypoints;
- make import errors and raising hookimpls fatal in every layer (decisions/plugins.md); skipping a feature with invalid settings and the credential checks are TASK-126, which builds on this;
- add the CI check that every package shipping hookimpls has an entry-point line;
- running from bare, unsynced source loads zero plugins and fails loudly.

Packaging: load_setuptools_entrypoints reads installed-distribution metadata, so the image must install the app as a distribution (TASK-14).

legacy modules/: they keep their hand-written registration until each surface is rebuilt (decisions/migration.md). TASK-35 settles one registration path per module first. The walk is removed entirely, so any modules/ hookimpl still reached only by the walk must be on the legacy list by then.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 TASK-110.1 is done: modules.sre and modules.dev are on explicit legacy Slack registration with no hookimpls
- [x] #2 TASK-110.2 is done: plugins load only from pyproject entry points and any plugin load failure aborts boot
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-01 (amended decisions/feature-packages.md and plugins.md): an umbrella's core/ and common/ are never entry points and have no enablement key. Subdomain names for incident come from TASK-135 and the TASK-97 packet; incident.draft and incident.summary will not exist as separate entry points.

2026-10-06: Stack G merged (#1530-#1534). The incident scribe subdomain is packages/incident/scribe, entry point name incident.scribe; packages/incident/core is never an entry point. packages/incident_draft and packages/incident_summary no longer exist.

2026-10-06 (human decision): split for the single-PR gate, because moving sre/dev off pluggy is a behaviour-preserving refactor pinned by legacy_surface while entry-point loading changes boot semantics. TASK-110.1 moves modules.sre and modules.dev onto explicit legacy registration (walk still in place); TASK-110.2 (depends on 110.1, standalone deploy per doc-2) does the entry points, fatal loading and the rest. The original AC#1-#6 moved verbatim to TASK-110.2; AC#2 is kept literally because 110.1 removes the only first-party registration that would have needed a carve-out. The comments below (TASK-35 planning, Stack A leftovers) are addressed in TASK-110.2's plan.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-28 14:44
---
2026-09-28 (from TASK-35 planning): modules/sre and modules/dev register their /sre subcommands ONLY through register_slack_commands hookimpls (modules/sre/__init__.py, modules/dev/__init__.py -> platforms/slack.py register_commands(provider)); the legacy modules/sre/sre.py root-command wrapper is dead (provider registers /sre first, Bolt dispatch is first-match) and TASK-35 deletes it. Moving sre back onto _register_legacy_handlers() is not an option: the provider would have no sre subcommands. So when this task removes the pkgutil walk, it must keep modules.sre and modules.dev registered via the hand-written legacy registration that decisions/plugins.md reserves for modules/ until each surface is rebuilt (explicit registration of those two modules in startup, not new modules.* entry points), and cover it with a test. Planning must decide how that squares with 'pm.register() for a first-party plugin appears only in test fixtures'.
---

created: 2026-10-02 13:49
---
From the Stack A handoff, moved here when that doc was retired (2026-10-02; verified on main at f182ecd2). Three leftovers from TASK-107.3 and TASK-107.4 that this task is the natural place to settle:
1. server/plugins/manager.py still defines discover_and_init_features (:114) and collect_feature_i18n_resources (:45), and nothing outside that module calls them: lifespan inlines the same steps. Delete them here when the filesystem walk is replaced, or keep one as the single discovery entry point and have lifespan call it; do not leave both paths.
2. pyproject.toml declares no entry points, so the entry-point-group use of PLUGIN_NAMESPACE (contracts/plugins/namespace.py) has no consumer until this task adds them. Today the constant is used only for the pluggy markers and the plugin manager.
3. PLUGIN_NAMESPACE is read from the installed distribution metadata (metadata('sre-bot')), so importing contracts.plugins.namespace raises PackageNotFoundError wherever the project is not installed. That matches this task's 'bare, unsynced source fails loudly' scope, but it was only checked in a scratch venv built the way the Dockerfile builds it; no docker image build was run. Verify it in a real image build here (the packaging dependency is TASK-14).
---
<!-- COMMENTS:END -->
