---
id: m-4
title: "Phase 4 - Infrastructure Hardening"
---

## Description

Make the hosting and operations decisions real: capability-shaped StorageService, in-memory fakes for every hosting contract and externally facing capability api.py Protocol, the coordination rename and lease hardening, the queue contract when its first consumer exists, middleware trio (correlation, security headers, RFC 9457), distributed rate limiting, deletion of the in-process event dispatcher with no replacement (decisions/plugin-architecture.md: no in-process event bus), the webhooks and approvals capabilities and their consumers. The service registry with eager validation moved to m-7 (TASK-109; the lru_cache provider registry TASK-29 is retired). Exit: security/ops decision Checks pass; applies:target records flip to now. Ref: doc-1 Phase 4.
