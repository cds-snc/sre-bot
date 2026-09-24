---
id: m-7
title: "Phase 2b - Plugin Architecture Foundation"
---

## Description

Build the six-layer foundation from decisions/plugin-architecture.md before any package moves: import-linter contracts first, then app/contracts/, the svcs service registry, entry-point plugin loading with per-environment enablement, the extension-point phase, the package generator, framework services into app/server/, workplace systems and audit into app/capabilities/, and existing packages into app/features/ one per PR. Exit: the six layers exist, import-linter enforces them with an ignore list that only shrinks, and no package imports infrastructure/ or another feature. Ref: decisions/plugin-architecture.md Migration.
