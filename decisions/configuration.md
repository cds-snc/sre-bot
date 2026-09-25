---
status: Accepted
date: 2026-07-24
applies: target
scope: Settings ownership, configuration files, plugin enablement, environment identity, and secrets.
---

# Configuration

## Context

Every setting is read from environment variables today, through about three dozen `BaseSettings` classes with no configuration files.

Current code:
- AWS settings live only in `integrations/aws/settings.py`. Slack's settings have two homes: `integrations/slack/settings.py` and `infrastructure/configuration/integrations/slack.py`. Other vendors (Google, OpsGenie, Trello and more) live only in `infrastructure/configuration/integrations/`.
- Some feature settings sit with their feature (`packages/access/common`, `incident_draft`, `incident_summary`, `oncall_sync`, `user_rotations`); others sit in `infrastructure/configuration/features/` (`atip`, `aws_ops`, `groups`, `incident`, `sre_ops`).
- Security settings are split: `CORS_ALLOWED_ORIGINS` and `DEV_BYPASS_ENABLED` on `AppSettings`, `ISSUER_CONFIG` and `DEV_BYPASS_TOKEN` on `ServerSettings`. No `SecuritySettings` slice exists.
- `AppSettings.ENVIRONMENT` is typed `Literal["local", "ci", "dev", "staging", "production"]` and drives environment-conditional behaviour. `AppSettings.PREFIX` no longer exists, and the `Settings` aggregator in `infrastructure/configuration/settings.py` is gone.
- Which features and jobs run is decided by environment variables and `ENVIRONMENT` checks in code.

The app is promoted as one image through every environment, and plugins are enabled per environment ([plugin-architecture.md](plugin-architecture.md)). Environment variables are a poor home for non-secret, reviewable configuration: they are invisible in the repo and differ silently between environments.

## Decision

**Settings live with their owner.** Each owner defines one typed `pydantic_settings.BaseSettings` slice next to its code:
- features: `features/<feature>/settings.py`;
- capabilities: `capabilities/<capability>/settings.py`;
- hosting services: `infrastructure/<service>/settings.py`;
- vendor clients: `integrations/<vendor>/settings.py`.

A system reached in more than one role holds one least-privilege credential per role, not one shared login. For example, Slack's bot and Socket Mode tokens (transport) are separate from an admin token used by a feature that changes Slack ([platform-transports.md](platform-transports.md)). A recurring job's schedule and lease TTL belong to the job's feature, not a central scheduler slice ([reliability.md](reliability.md)). The security domain owns a `SecuritySettings` slice: issuers and JWKS, the CORS allow-list, the rate-limit backend and the dev-bypass settings. One key has exactly one owning slice.

**Values come from checked-in TOML configuration files.** A base file holds defaults for every slice; one file per environment overrides it. `ENVIRONMENT` selects the environment file. pydantic-settings' TOML source loads both, and each slice reads its own table. Files are reviewed like code and validated at boot.

**Environment variables carry only secrets and deployment identity.** Identity is `ENVIRONMENT` plus values the platform injects (such as `GIT_SHA`). Everything else is in the configuration files.

**Plugin enablement lives in the configuration files.** Every plugin's entry point has an enablement key in the base file; an environment file may override it. The host skips a disabled plugin before registering it ([plugins.md](plugins.md)).

**Runtime flags use OpenFeature.** Gradual rollout or a kill switch without a deploy uses [OpenFeature](https://openfeature.dev/) with the self-hosted flagd provider, added only when a feature needs one. Configuration files are not reloaded at runtime.

**Environment identity.** `ENVIRONMENT: Literal["local", "ci", "dev", "staging", "production"]` is the only source of "which deployment am I?". Deriving it from hostnames, prefixes or `sys.modules` is prohibited. Security-relevant toggles (dev bypass) also need their own explicit boolean that defaults off: two independent guards. Command naming, so a dev and a prod bot coexist in one Slack workspace, is a transport setting (`COMMAND_PREFIX`) and is never derived from `ENVIRONMENT` ([transport-slack.md](transport-slack.md)).

**Fail fast.** Every slice validates in lifespan's configuration phase ([lifecycle.md](lifecycle.md)); an invalid file or a missing required secret fails boot with a message naming the key.

**Secrets.** Secret material resolves through the secrets contract ([cloud-portability.md](cloud-portability.md)) or is injected by the platform at deploy time (ECS task-definition `secrets:` from Secrets Manager). Plain environment-variable secrets are tolerated, not the target. Secrets never appear in configuration files, defaults, logs ([observability.md](observability.md)) or `repr`. JWKS refreshes at runtime; static secrets rotate by redeploy.

**Consumers receive slices.** A service constructor takes its own settings slice, nothing wider. No aggregator of all settings exists.

**Migration rides with the work.** Any task that touches a domain's service moves that domain's slice to its target home in the same change and deletes the old one.

## Consequences

- "Where is this configured?" has one answer per owner; deleting a feature deletes its configuration.
- Differences between environments are visible in a diff of two files.
- A typo in `ENVIRONMENT` or a configuration key is a validation error at boot.
- Cost: a change to non-secret configuration needs a PR and a deploy; runtime changes need a flag.

## Checks

- CI: each key is owned by exactly one settings slice.
- CI: no secret-shaped key (token, password, key) appears in a configuration file.
- Boot test: every plugin entry point has an enablement key in the base file.
- Boot test: missing required secret → clean failure naming it.
- grep: no environment derivation outside `ENVIRONMENT`; no `os.environ` reads outside settings classes.
- Review: no feature or capability reads an environment variable directly.

## Migration

Ticket: TASK-24 (single home per vendor, `SecuritySettings` slice). Configuration files and TOML loading are a ticket to create ([plugin-architecture.md](plugin-architecture.md)).

Tolerated until closed:
- dual vendor homes in `infrastructure/configuration/integrations/` and `integrations/<vendor>/settings.py`;
- feature slices in `infrastructure/configuration/features/`;
- security settings split across `AppSettings` and `ServerSettings`;
- all non-secret settings, and feature and job switches, read from environment variables;
- plain environment-variable secrets.

**Changes:**
- 2026-09-24: Migration names epic tickets only; values move to per-environment TOML files with plugin enablement, and the closed `PREFIX` and aggregator items are removed.
