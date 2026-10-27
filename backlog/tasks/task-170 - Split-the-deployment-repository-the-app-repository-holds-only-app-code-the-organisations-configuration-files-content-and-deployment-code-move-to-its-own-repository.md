---
id: TASK-170
title: >-
  Split the deployment repository: the app repository holds only app code; the
  organisation's configuration files, content and deployment code move to its
  own repository
status: To Do
assignee: []
created_date: '2026-10-26T22:38:00Z'
labels:
  - configuration
  - deployment
dependencies:
  - TASK-167
priority: low
ordinal: 451000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
End state recorded in decisions/product-scope.md and decisions/configuration.md (2026-10-26, human): this repository holds only the app code, and each organisation configures and deploys its instance from a deployment repository of its own. That repository holds its environment configuration file (today app/config/production.toml, every slice at once), its organisation content as TASK-167 rules (team playbooks included), and its deployment code (today terraform/ and the deploy workflows). Not scheduled. The app refactor (doc-11) comes first. To decide when planned: how the environment file reaches the container (an image layer over the upstream image, or a mounted or fetched file located by one new platform-provided name), how deploy and rollback (decisions/deployment.md) run from the deployment repository, and what a fresh adopter starts from (examples, not this organisation's data).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 This repository holds no organisation-specific value: base.toml, ci.toml and an example local.toml only; no production.toml and no terraform for this organisation's account
- [ ] #2 This organisation's instance is configured, deployed and rolled back from its deployment repository, and production behaviour is unchanged
- [ ] #3 decisions/configuration.md, deployment.md and product-scope.md describe the two repositories
<!-- AC:END -->
