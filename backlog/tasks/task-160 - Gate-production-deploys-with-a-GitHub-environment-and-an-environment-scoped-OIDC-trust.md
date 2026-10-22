---
id: TASK-160
title: >-
  Gate production deploys with a GitHub environment and an environment-scoped
  OIDC trust
status: To Do
assignee: []
created_date: '2026-10-22T15:15:00Z'
labels:
  - configuration
dependencies:
  - TASK-111.16
ordinal: 431000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-111.16 limits manual runs and re-runs of build_and_deploy.yml to repository admins with an in-workflow check (require-admin.sh), which the workflow code enforces. GitHub can enforce it instead: a production environment with required reviewers (up to six users or teams; optionally no self-review) and deployment branches limited to main. Referencing an environment changes the OIDC subject to repo:cds-snc/sre-bot:environment:<name>, so the sre-bot-apply trust policy (not in this repo) must accept it first. Decide whether merge deploys also need approval or only manual runs, then replace or keep the in-workflow check.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The sre-bot-apply trust policy accepts the environment subject before any job references the environment
- [ ] #2 Manual runs and re-runs of the deploy job need an approval from the listed reviewers; the decision on merge deploys is recorded in decisions/deployment.md
- [ ] #3 Deployment branches for the environment are limited to main
<!-- AC:END -->
