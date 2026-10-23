---
id: TASK-162
title: >-
  Evaluate separating the generic SRE bot from the CDS deployment (upstream
  package, downstream configured repo)
status: To Do
assignee: []
created_date: '2026-10-22T19:22:00Z'
updated_date: '2026-10-23T18:09:00Z'
labels:
  - architecture
  - configuration
dependencies: []
references:
  - https://github.com/cds-snc/sre-bot/issues/1783
priority: low
ordinal: 433000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Idea (human, 2026-10-22, TASK-111.7 planning): the SRE bot source lives in a workplace-agnostic upstream repo that publishes a versioned package or base image, and CDS keeps a downstream deployment repo holding its configuration files (app/config/*.toml with workspace-specific ids such as Slack channels and user groups), terraform, and CDS-only plugins (for example the Notify API-key leak response, TASK-161), built as a thin image on the upstream release. Prior art: Backstage ships framework packages and each adopter keeps its own app repo with app-config.production.yaml (https://backstage.io/docs/next/golden-path/deployment/config-first); Helm charts with values in a GitOps repo. What exists already: plugins load from pyproject entry points (decisions/plugins.md), so a downstream distribution can add plugins; configuration is base + per-ENVIRONMENT TOML files read by server/configuration/ (decisions/configuration.md). Open questions for the ADR: package vs base image; where the configuration directory comes from (a configurable path); how CI, the image digest pin and rollback (decisions/deployment.md) work across two repos; licensing and release cadence; which current code is CDS-specific. Not queued in doc-11; output is a decision record (architecture mode), no code.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A decision record in decisions/ states whether to split, the chosen packaging model, and the configuration-directory contract, with sources
- [ ] #2 The CDS-specific code and configuration are inventoried, each with its target repo
- [ ] #3 If the split is accepted, follow-up tasks exist for the extraction steps, each with expand/contract ordering and its rollback
<!-- AC:END -->
