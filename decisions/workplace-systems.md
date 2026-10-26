---
status: Accepted
date: 2026-10-15
applies: target
scope: Which external systems are hosting services chosen per deployment, which are workplace systems chosen per person or artifact, and where records of truth live.
---

# Workplace Systems

## Context

The organization will run Google Workspace with Slack, and Microsoft 365 with Teams, side by side for the long term. The bot coordinates the whole user base. Some employees work only in Google, others only in Microsoft. Who a person is comes from the organization's identity provider, and what they may do from its groups ([people-and-accounts.md](people-and-accounts.md)). One app instance serves one organization.

Hosting services fit a "one provider per deployment, chosen by configuration" model ([cloud-portability.md](cloud-portability.md)). Systems where people, their accounts and their artifacts live don't: several vendors are live at once, and the right one depends on who or what is involved.

Current state:

- `infrastructure/directory/`, `infrastructure/drive/` and `infrastructure/spreadsheets/` each expose a vendor-neutral Protocol with a single Google implementation, selected by a setting behind a cached factory.
- Incident and talent-role records are kept in Google Sheets and Docs. The incident list sheet is both a record and the view people use for metrics; a status update that fails to reach it is simply missing from the record (TASK-73).
- [platform-transports.md](platform-transports.md) already treats chat platforms as coexisting: one runtime per platform, no unified `Platform` Protocol.

## Decision

**Two kinds of external system.**

- **Hosting services:** records, queue, coordination, secrets and similar backing services. One provider serves the whole deployment, chosen by configuration. Their Protocols live in `app/contracts/` and their implementations in `app/infrastructure/`, which is hosting only ([plugin-architecture.md](plugin-architecture.md)). [cloud-portability.md](cloud-portability.md) governs them.
- **Workplace systems:** Google Workspace, Microsoft 365, Slack, Teams, and any suite the organization adds. They hold people, their accounts and their artifacts. Several are live at once. Which one applies to an operation is **data**, not configuration:
  - the person's linked account ([people-and-accounts.md](people-and-accounts.md));
  - the artifact's stored reference;
  - the platform a conversation started on.

**Workplace systems are capabilities, not infrastructure, and a capability is named for its purpose, not for a vendor product.** A workplace capability exists only where rule 2 puts one: an operation several features need, across suites. Its port is named for what the organization does with it (the people directory, an incident's documents), as ports are named for their purpose ([Cockburn, Hexagonal Architecture](https://alistaircockburn.com/Talk%202025-11%20Hexagonal.pdf)) and as Dispatch types its plugins by incident purpose (`document`, `storage`, `conference`, `participant`: [Dispatch plugin bases](https://github.com/Netflix/dispatch/tree/master/src/dispatch/plugins/bases)). A vendor product API (Drive, Sheets, Calendar) is not a capability by itself: a feature that needs one owns a purpose-named port, and its adapter calls the vendor integration (`integrations/<vendor>/`, one gateway per vendor that owns the client, credentials, tenant entry, retries and error classification). The insurance a neutral port buys is worth its complexity only in proportion to the likelihood of a second vendor ([Hohpe, Don't get locked up into avoiding lock-in](https://martinfowler.com/articles/oss-lockin.html)): the people directory has one (Microsoft Entra beside Google, [people-and-accounts.md](people-and-accounts.md)); files and spreadsheets have none planned, and spreadsheets become projections (rule 5). Which vendor serves an operation is data (rule 3), never a `provider` setting.

**Rules for workplace systems.**

1. **No suite-wide neutral contract.** A neutral contract across whole suites is the lowest-common-denominator trap ([Thoughtworks Radar](https://www.thoughtworks.com/radar/techniques/generic-cloud-usage)), and routing by person or artifact is organization policy, which infrastructure must not hold. A workplace capability's vocabulary is the organization's (a person's calendar, an incident's documents), not a vendor's.
2. **Vendor code lives in adapters.**
   - Behavior whose value is the vendor itself (e.g. Drive `appProperties`) stays in a feature's Path B adapter.
   - An operation several features need across suites lives in a workplace capability, with one adapter per system in its `adapters/`.
   - Every adapter is a Gateway ([Fowler](https://martinfowler.com/articles/gateway-pattern.html)) governed by [outbound-clients.md](outbound-clients.md) and [sdk-typing.md](sdk-typing.md).
3. **One instance, several tenants.** Configuration names each workplace tenant the instance works with (a Google Workspace domain, a Microsoft 365 tenant, a Slack workspace, a Teams tenant), each with its own least-privilege credentials, held in configuration, or in an installation store when the vendor issues them per installation through OAuth (Slack: [Bolt OAuth](https://docs.slack.dev/tools/bolt-python/concepts/authenticating-oauth)). A single-workspace Slack app keeps its tokens on the Slack slice, beside its one tenant entry ([configuration.md](configuration.md)). Configuration never selects "the" provider for a workplace concern. A tenant entry in a vendor's settings slice is what makes the instance work with that tenant ([configuration.md](configuration.md)); there is no separate enabled flag.
   - **The entry carries the vendor's real tenant id, never an API alias** (Google `my_customer`; Microsoft `common`, `organizations`, `consumers`, domain names).
   - **Format checks follow vendor documentation only.** Slack and Google document no id format, so their ids are opaque non-blank strings and aliases are rejected; Microsoft documents a GUID. Sources, read on 2026-10-15: [Slack ids are opaque](https://docs.slack.dev/changelog/2016/08/11/user-id-format-changes), [Google customer id](https://knowledge.workspace.google.com/admin/getting-started/find-your-customer-id), [Entra `tid`](https://learn.microsoft.com/en-us/entra/identity-platform/id-token-claims-reference).
   - **Features learn the configured systems through a read API** (a small configured-systems read provided where the store or capability is built), never by importing another slice.
   - **The entry is the expected tenant, verified against the vendor's own claim.** Like an OpenID Connect client that configures its issuer and rejects tokens from any other, the instance checks every inbound request's tenant claim against the entry and refuses a mismatch with an error event; it never learns the tenant from a request, and boot stays free of network calls. A batch job that stamps a tenant without a request first checks the entry against the vendor's identity call (Slack `auth.test`) and fails otherwise. Slack's tenant uses Slack's own pair: the Enterprise org (`enterprise_id`) when one is configured, as Slack advises keying org data by it, otherwise the workspace (`team_id`); the slice names both in Slack's terms. Sources, read on 2026-10-20: [OIDC Core 5.7](https://openid.net/specs/openid-connect-core-1_0.html) ("The sub (subject) and iss (issuer) Claims … used together, are the only Claims that an RP can rely upon as a stable identifier"), [Slack Enterprise orgs](https://docs.slack.dev/enterprise/developing-for-enterprise-orgs) ("it's best to associate Enterprise org workspace data with its `enterprise_id`"), [Bolt authorization](https://docs.slack.dev/tools/bolt-python/concepts/authorization).
4. **References carry their system.** Every stored reference to a workplace artifact, account or conversation records the system and tenant alongside the vendor's id. Never store a bare vendor id. The reason holds with one tenant: a vendor id is unique only within the scope that issued it, and records outlive configuration, so a workspace joining an Enterprise org or a second chat system would otherwise leave stored ids ambiguous, with no way to recover their scope. Writers stamp the verified tenant (rule 3). The system is a closed enum validated strictly where it is chosen; stored records are read tolerantly ([cloud-portability.md](cloud-portability.md) contract 4). The enum is `WorkplaceSystem` in `app/contracts/workplace/`, platform vocabulary every feature and the configured-systems read share.
5. **Records of truth live in the app**, behind the records contract. Workplace documents and spreadsheets are one of two things:
   - **Collaboration spaces:** people work in them, and the app stores a reference.
   - **Projections:** the app writes derived views of stored records, such as an incident metrics sheet. A projection is never read back as a source of truth and can be rebuilt from the stored records.

## Consequences

- The model matches what [platform-transports.md](platform-transports.md) does for chat: coexisting platforms, no unified Protocol, per-platform handlers over one shared service.
- A failed projection write becomes a retry or a rebuild, not lost data.
- Routing needs identity first: no cross-suite operation can be built before people and their linked accounts exist.
- Cost: per-system adapters repeat some shape, e.g. two calendar adapters and two directory adapters. That duplication is the price of keeping each vendor's real behavior instead of a neutral subset.
- Hosting portability is unaffected: leaving AWS still touches only `infrastructure/`.

## Checks

- import-linter ([plugin-architecture.md](plugin-architecture.md)): features and capabilities never import `infrastructure/`.
- Review: every `app/infrastructure/` package implements a hosting contract; none serves a workplace concern.
- Review: every workplace capability names at least two feature consumers in its README and is named for its purpose; no settings slice selects a vendor with a `provider` key.
- Review: stored models for workplace references include system and tenant fields.
- Review: no code reads a projection spreadsheet or document as input to a business decision.

## Migration

Tickets: TASK-145 (incident records owned by the app, decomposed in [incident-management.md](incident-management.md); replaces TASK-38) and TASK-39 (talent-role records, with the role surface rebuild); TASK-119 (`directory` to `app/capabilities/directory/`); TASK-120 and TASK-121 (`drive` and `spreadsheets`), re-scoped by TASK-169 from a move into `capabilities/` to purpose-named ports owned by their consumers over `integrations/google_workspace/`; TASK-138 (calendar) held by TASK-169 until a second consumer or a second suite needs it; TASK-111.13 deletes the `provider` settings of the three packages.

Tolerated until then:
- the three workplace providers in `infrastructure/directory/`, `infrastructure/drive/` and `infrastructure/spreadsheets/`;
- Google Sheets and Docs as records for incidents and talent roles;
- a single configured Google tenant;
- legacy stored references without a system or tenant.

**Changes:**
- 2026-09-24: workplace systems are capabilities and infrastructure is hosting only, per plugin-architecture.md.
- 2026-09-25: Accepted; Migration names its tickets.
- 2026-10-02: the incident record, its references and its projection are specified in [incident-management.md](incident-management.md) (TASK-97).
- 2026-10-13: the storage contract is the records contract (`RecordStore`, TASK-27.4).
- 2026-10-15: a tenant entry carries the vendor's real tenant id, never an alias, with format checks from vendor documentation only; features read the configured systems through a read API (TASK-153).
- 2026-10-15: `WorkplaceSystem` lives in `app/contracts/workplace/` (TASK-145.5.3).
- 2026-10-20: a tenant entry is the expected tenant, verified against each inbound request's claim (a mismatch is refused) and by a stamping batch job's identity call; Slack's tenant is the Enterprise org when configured, else the workspace; references carry the tenant because vendor ids are scoped by their issuer, not to support several tenants (TASK-157).
- 2026-10-22: per-tenant credentials live in configuration or, for a vendor that issues them per installation through OAuth, in an installation store; single-workspace Slack keeps its tokens on the slice (TASK-111.7 planning).
- 2026-10-26: a workplace capability is named for its purpose and exists only for an operation several features need across suites; a vendor product API (Drive, Sheets, Calendar) is reached through a consumer-owned port over the vendor integration; vendor choice is never a `provider` setting (TASK-111.10 review; TASK-169 confirms the Google split, TASK-111.13 deletes the settings).
