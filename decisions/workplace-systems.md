---
status: Draft
date: 2026-09-10
applies: target
scope: Which external systems are hosting services chosen per deployment, which are workplace systems chosen per person or artifact, and where records of truth live.
---

# Workplace Systems

## Context

The organization will run Google Workspace with Slack, and Microsoft 365 with Teams, side by side for the long term. The bot coordinates the whole user base. Some employees work only in Google, others only in Microsoft, and contractors need narrower access than employees. One app instance serves one organization.

Hosting services fit a "one provider per deployment, chosen by configuration" model ([cloud-portability.md](cloud-portability.md)). Systems where people, their accounts and their artifacts live don't: several vendors are live at once, and the right one depends on who or what is involved.

Current state:

- `infrastructure/directory/`, `infrastructure/drive/` and `infrastructure/spreadsheets/` each expose a vendor-neutral Protocol with a single Google implementation, selected by a setting behind a cached factory.
- Incident and talent-role records are kept in Google Sheets and Docs. The incident list sheet is both a record and the view people use for metrics; a status update that fails to reach it is simply missing from the record (TASK-73).
- [platform-transports.md](platform-transports.md) already treats chat platforms as coexisting: one runtime per platform, no unified `Platform` Protocol.

## Decision

**Two kinds of external system.**

- **Hosting services:** storage, queue, coordination, secrets and similar backing services. One provider serves the whole deployment, chosen by configuration. Their Protocols live in `app/contracts/` and their implementations in `app/infrastructure/`, which is hosting only ([plugin-architecture.md](plugin-architecture.md)). [cloud-portability.md](cloud-portability.md) governs them.
- **Workplace systems:** Google Workspace, Microsoft 365, Slack, Teams, and any suite the organization adds. They hold people, their accounts and their artifacts. Several are live at once. Which one applies to an operation is **data**, not configuration:
  - the person's linked account ([people-and-accounts.md](people-and-accounts.md));
  - the artifact's stored reference;
  - the platform a conversation started on.

**Workplace systems are capabilities, not infrastructure.** Directory, documents, files, spreadsheets, calendar and mail live under `app/capabilities/`, exposed through each capability's `api.py`.

**Rules for workplace systems.**

1. **No suite-wide neutral contract.** A neutral contract across whole suites is the lowest-common-denominator trap ([Thoughtworks Radar](https://www.thoughtworks.com/radar/techniques/generic-cloud-usage)), and routing by person or artifact is organization policy, which infrastructure must not hold. A workplace capability's vocabulary is the organization's (a person's calendar, an incident's documents), not a vendor's.
2. **Vendor code lives in adapters.**
   - Behavior whose value is the vendor itself (e.g. Drive `appProperties`) stays in a feature's Path B adapter.
   - An operation several features need across suites lives in a workplace capability, with one adapter per system in its `adapters/`.
   - Every adapter is a Gateway ([Fowler](https://martinfowler.com/articles/gateway-pattern.html)) governed by [outbound-clients.md](outbound-clients.md) and [sdk-typing.md](sdk-typing.md).
3. **One instance, several tenants.** Configuration names each workplace tenant the instance works with (a Google Workspace domain, a Microsoft 365 tenant, a Slack workspace, a Teams tenant), each with its own least-privilege credentials. Configuration never selects "the" provider for a workplace concern.
4. **References carry their system.** Every stored reference to a workplace artifact, account or conversation records the system and tenant alongside the vendor's id. Never store a bare vendor id.
5. **Records of truth live in app storage.** Workplace documents and spreadsheets are one of two things:
   - **Collaboration spaces:** people work in them, and the app stores a reference.
   - **Projections:** the app writes derived views of stored records, such as an incident metrics sheet. A projection is never read back as a source of truth and can be rebuilt from storage.

## Consequences

- The model matches what [platform-transports.md](platform-transports.md) does for chat: coexisting platforms, no unified Protocol, per-platform handlers over one shared service.
- A failed projection write becomes a retry or a rebuild, not lost data.
- Routing needs identity first: no cross-suite operation can be built before people and their linked accounts exist.
- Cost: per-system adapters repeat some shape, e.g. two calendar adapters and two directory adapters. That duplication is the price of keeping each vendor's real behavior instead of a neutral subset.
- Hosting portability is unaffected: leaving AWS still touches only `infrastructure/`.

## Checks

- import-linter ([plugin-architecture.md](plugin-architecture.md)): features and capabilities never import `infrastructure/`.
- Review: every `app/infrastructure/` package implements a hosting contract; none serves a workplace concern.
- Review: stored models for workplace references include system and tenant fields.
- Review: no code reads a projection spreadsheet or document as input to a business decision.

## Migration

Tickets to create: move incident and talent-role records into storage (related: TASK-27, TASK-38); move `directory`, `drive` and `spreadsheets` to `app/capabilities/`.

Tolerated until then:
- the three workplace providers in `infrastructure/directory/`, `infrastructure/drive/` and `infrastructure/spreadsheets/`;
- Google Sheets and Docs as records for incidents and talent roles;
- a single configured Google tenant;
- legacy stored references without a system or tenant.

**Changes:**
- 2026-09-24: workplace systems are capabilities and infrastructure is hosting only, per plugin-architecture.md.
