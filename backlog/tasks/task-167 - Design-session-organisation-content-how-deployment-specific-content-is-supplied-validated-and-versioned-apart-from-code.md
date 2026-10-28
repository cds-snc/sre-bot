---
id: TASK-167
title: >-
  Design session: organisation content - how deployment-specific content is
  supplied, validated and versioned apart from code
status: Done
assignee: []
created_date: '2026-10-26T14:02:00Z'
updated_date: '2026-10-28T20:54:00Z'
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
- [x] #1 A decision record (new decisions/organisation-content.md or amendments) states the three categories (deployment configuration, code extensions, organisation content) and, for organisation content, format and schema, location, loading and validation, ownership, versioning and the adopter's starting set, with cited sources
- [x] #2 Every current and planned organisation-specific content type is inventoried and assigned the pattern (webhook sources and templates, access catalogue, playbooks, incident templates, notification templates)
- [x] #3 Follow-up scope changes are written into the affected tasks: the webhooks reassessment, TASK-165's playbooks subtask, TASK-166's catalogue loading, TASK-158
- [x] #4 Google document, folder, sheet and calendar ids are ruled on first (they gate TASK-111.10.3): deployment configuration under the non-public value rule (decisions/configuration.md, 2026-10-26: never in the public files, supplied like a secret, one key per id) or organisation content with its own source; the ruling names each id's owning slice or content type so the incident, talent and AWS carriers (145.6, 145.7, 145.10, 145.12, 39, 88) and TASK-158 follow it
- [x] #5 Each content location is designed for the end state in decisions/product-scope.md (2026-10-26): the organisation's own deployment repository holds its configuration files, content (team playbooks included) and deployment code. A location in this repository is named interim and can move without an app code change
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Design session 2026-10-28 (human-led), working tree only, nothing committed.

Records drafted (status Draft, each reviewed separately): decisions/organisation-content.md (choosing the category: deployment configuration, runtime flag, code extension, organisation content; choosing a content kind's source: provisioned files or managed records; rules every kind follows: consumer-owned read port, one source per item with explicit moves, never executable with size limits, no non-public value in public files; kind table with owners), decisions/provisioned-content.md (YAML per item validated by the consumer's model with exported JSON Schema, one content-root key, loaded once at startup for enabled plugins, CODEOWNERS, the image is the version, blast radius through CI, boot and the circuit breaker, examples for adopters, runtime fetching rejected, Git Sync not adopted for now), decisions/managed-content.md (one write path per kind with model and whole-set validation and limits, declared permission and optional approval, append-only versions with restore and retention, AU-3 audit, readers skip invalid items, per-kind runtime flag switches the managed source off, schema version per record compatible both ways, export; the Cloudflare 2025-11-18 and Google Cloud 2025-06-12 outages and their fixes). configuration.md carries the Google-id ruling and owners; product-scope.md and the README index link the records.

Rulings agreed by the human: Google document, folder, sheet and calendar ids are non-public deployment configuration, one key per id on the owning slice (incident 145.6, 145.7, 145.10, 145.12; cloud operations 88; talent 39; incident_drive_id and rep.g deleted in 111.10.3); once incident types or team templates exist (165) the template a type uses is managed content and the configured id the default. The 'no database' argument was withdrawn: the records contract exists, so in-flight change is designed for. Configuration stays fixed for a deploy; in-flight behaviour is an OpenFeature flag or managed content. Kinds: webhook sender kinds provisioned and instances managed (168), playbooks, incident types and templates managed with a provisioned starting set (165), entitlement catalogue managed (166), schedule mappings provisioned and self-managed rosters managed (146 re-cut), organisation wording provisioned (surface rebuilds). Newly found: CDS wording in locales and scribe, the ATIP letter, the aws_ops sre-ifs@cds-snc.ca default (88).

Checked against industry practice (Grafana provisioning, incident.io GitHub-managed types, Backstage, Keycloak import, Kubernetes CRDs, CEL and storage migration, Confluent compatibility, LaunchDarkly approvals, NIST AU-3, PagerDuty Event Orchestration, Fowler feature toggles): supported; six gaps folded into the records.

Open: AC #1 and #5 when the records are Accepted; AC #3 task scope changes (111.10.3, 145.6, 145.7, 145.10, 145.12, 39, 88, 146, 158, 165, 166, 168) after acceptance; no new tasks while designing (human). For the 146 re-cut: if Opsgenie's replacement supports overrides, self-managed rosters may not be needed.

2026-10-28 (TASK-111.14 planning, human): the aws_ops sre-ifs@cds-snc.ca default moves to production.toml as [aws_ops] aws_admin_groups in TASK-111.14, not TASK-88; TASK-88 AC #7 still deletes it with modules/permissions. organisation-content.md Tolerated list amended in the working tree.

2026-10-28: the table is [cloud_operations], not [aws_ops] (AWS_* environment names are the SDK's); organisation-content.md line amended.

- 2026-10-28 (human): the three records reviewed and Accepted; configuration.md, product-scope.md and the README index updated; ACs #1 and #5 checked. AC #3 written: Google-id carrier ACs reworded to the non-public ruling (145.6 #6, 145.7 #10, 145.10 #6, 145.12 #5, 39 #8, 88 #6; numbering kept), 111.10.3 description and AC #1, new ACs on 39 (organisation wording, ATIP letter), 158, 165 (playbooks, types, templates), 166 (entitlement catalogue, ACCESS_CONFIG_SOURCE deleted), 168 (sender kinds and instances, engine choice); notes on 146 (re-cut kinds), 145.6 and 145.7 (CDS wording). Remaining: the docs PR (human commits) and Done (human).
<!-- SECTION:NOTES:END -->
