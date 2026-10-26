---
id: TASK-167
title: >-
  Design session: organisation content - how deployment-specific content is
  supplied, validated and versioned apart from code
status: To Do
assignee: []
created_date: '2026-10-26T14:02:00Z'
labels:
  - architecture
  - configuration
  - framework
dependencies: []
references:
  - decisions/product-scope.md
  - decisions/configuration.md
  - decisions/plugins.md
  - decisions/webhooks.md
priority: high
type: spike
ordinal: 442000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Human-led design session (2026-10-26, human decision). The bot is being built as a framework another organisation can adopt (decisions/product-scope.md), but no record says where organisation-specific content lives or how it is loaded, and the code and plans hold three diverging patterns:
- webhook source patterns: Python modules in app/modules/webhooks/patterns/ (CDS senders: Upptime, AWS budget, Blazer check, API key leak), discovered by an import-time os.listdir/importlib walk (simple_text.py:215-235, aws_sns_notification.py:391-422) with _HANDLER-suffix naming and import-string resolvers;
- access platform catalogue: a pluggable loader (ACCESS_CONFIG_SOURCE bundle | inline_json | file_json | env, packages/access/common/settings.py);
- TASK-165 playbooks: a central configuration repository, a folder per team owned through CODEOWNERS, read through a catalogue port.
Other candidates to inventory: incident templates and document ids ([google_resources], TASK-158), notification message templates, the people and on-call sources.

The session separates three things and decides each: (1) deployment configuration (the TOML files, decisions/configuration.md, settled); (2) code extensions (plugins through entry points, decisions/plugins.md, settled); (3) organisation content: data an adopter supplies without forking (mappings, templates, playbooks, catalogues). For (3) it decides: format and schema (declarative and validated, never executable), where it lives (in-repo content directory, external content repository, or both through one port), how it loads (startup with fail-fast validation, or refreshed at runtime), ownership and review (CODEOWNERS), versioning and rollback, and what a fresh adopter starts with (examples, not CDS data).

Seed research (2026-10-26, to deepen in the session): Backstage separates plugins from organisation data held as catalog YAML loaded from configured locations and entity providers (https://backstage.io/docs/features/software-catalog/external-integrations/entity-providers); Grafana provisions alert rules, contact points and notification templates from files, the API or Terraform, and a provisioned resource is edited only in its source (https://grafana.com/docs/grafana/v10.1/alerting/set-up/provision-alerting-resources); PagerDuty transforms inbound events with rules and transformations configured as data, its older Custom Event Transformer ran JavaScript per integration. Industry direction: declarative content over executable per-sender code.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A decision record (new decisions/organisation-content.md or amendments) states the three categories (deployment configuration, code extensions, organisation content) and, for organisation content, format and schema, location, loading and validation, ownership, versioning and the adopter's starting set, with cited sources
- [ ] #2 Every current and planned organisation-specific content type is inventoried and assigned the pattern (webhook sources and templates, access catalogue, playbooks, incident templates, notification templates)
- [ ] #3 Follow-up scope changes are written into the affected tasks: the webhooks reassessment, TASK-165's playbooks subtask, TASK-166's catalogue loading, TASK-158
<!-- AC:END -->
