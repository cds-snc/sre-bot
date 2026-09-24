---
id: m-5
title: "Phase 5 - Legacy Modules Strangler"
---

## Description

Strangler-fig rebuild of app/modules/ (13 module groups) by surface, not by module, into app/features/ and app/capabilities/ per decisions/migration.md and plugin-architecture.md: inventory every surface with its target, pin it with smoke tests, rebuild, cut over, delete. Order: webhooks, incident (after the TASK-97 decision), small wins (role, secret, atip), AWS and provisioning, remainder. Exit: app/modules/ deleted, single registration path, python-i18n removed, deprecated-client baseline empty, other teams unaffected. Ref: plan par.10 Phase 5, decisions/migration.md.
