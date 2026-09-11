---
id: TASK-89
title: Assess the impact on the AWS integration of hosting the app outside AWS
status: To Do
assignee: []
created_date: '2026-09-11 15:49'
updated_date: '2026-09-11 15:53'
labels:
  - architecture
dependencies: []
references:
  - app/integrations/aws/client.py
  - decisions/cloud-portability.md
  - decisions/workplace-systems.md
  - decisions/layers.md
  - decisions/outbound-clients.md
priority: medium
type: spike
ordinal: 190000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Spike (created 2026-09-11 during the TASK-25.2 reassessment). The AWS vendor client (app/integrations/aws/client.py) needs no credentials of its own because the SRE Bot runs inside an AWS account and uses boto3's ambient credential chain, unlike the Google Workspace client, which carries a service-account key. That assumption is implicit and undocumented.

AWS plays two roles for this app: hosting provider (DynamoDB, Secrets Manager, ECS) and the target system of several Path B business features (Identity Center administration, access requests via SSO-Admin, Organizations and account-health reporting, Lambda inventory). decisions/workplace-systems.md states that leaving AWS touches only hosting implementations; that holds for the hosting role but not for the second role, which must keep reaching AWS from wherever the app runs.

Assess, for a hypothetical move of hosting to another cloud (e.g. Azure): how the client obtains credentials (OIDC / workload identity federation into an IAM role vs static keys vs a proxy account), whether get_aws_client's eager AssumeRole and role ARN settings still fit, which settings would then become required and whether they belong in integrations/aws/settings.py (transport, per decisions/outbound-clients.md) or in feature settings, and what changes in decisions/cloud-portability.md and decisions/workplace-systems.md. Output is a written assessment and a decision-record amendment proposal (at most one short dated sentence per changed decision, amended in place), not code.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A written assessment covers credential acquisition options, the fit of the current factory (eager AssumeRole, role ARN settings) and the settings that would become required, with sources cited
- [ ] #2 A proposed amendment to decisions/cloud-portability.md and/or decisions/workplace-systems.md distinguishes AWS as hosting provider from AWS as a Path B target system
- [ ] #3 The implicit ambient-credentials assumption is documented where the human decides it belongs (decision record or client.py module docstring)
<!-- AC:END -->
