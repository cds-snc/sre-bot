---
status: Accepted
date: 2026-10-15
applies: target
scope: Settings ownership, configuration files, plugin enablement, environment identity, and secrets.
---

# Configuration

## Context

Every setting is read from environment variables today, through about three dozen `BaseSettings` classes with no configuration files.

Current code:
- AWS settings live only in `integrations/aws/settings.py`. Slack's settings have two homes: `integrations/slack/settings.py` and `infrastructure/configuration/integrations/slack.py`. Other vendors (Google, OpsGenie, Trello and more) live only in `infrastructure/configuration/integrations/`.
- Some feature settings sit with their feature (`packages/access/common`, `incident/scribe`, `oncall_sync`, `user_rotations`); others sit in `infrastructure/configuration/features/` (`atip`, `aws_ops`, `groups`, `incident`, `sre_ops`).
- Security settings are split: `CORS_ALLOWED_ORIGINS` and `DEV_BYPASS_ENABLED` on `AppSettings`, `ISSUER_CONFIG` and `DEV_BYPASS_TOKEN` on `ServerSettings`. No `SecuritySettings` slice exists.
- `AppSettings.ENVIRONMENT` is typed `Literal["local", "ci", "dev", "staging", "production"]` and drives environment-conditional behaviour. `AppSettings.PREFIX` no longer exists, and the `Settings` aggregator in `infrastructure/configuration/settings.py` is gone.
- Which features and jobs run is decided by environment variables and `ENVIRONMENT` checks in code.
- Vendor clients have no enablement rule, because they are clients, not plugins, and the per-entry-point key never reaches them. `SLACK_ENABLED` is an environment variable defined in three slices with three defaults, and it mixes two meanings: run the Slack transport, and have a Slack workspace. Google has no flag: it is in use when `GCP_SRE_SERVICE_ACCOUNT_KEY_FILE` is set, and `GOOGLE_WORKSPACE_CUSTOMER_ID` defaults to the `my_customer` API alias, not a tenant id.

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

**Environment names mirror the configuration path.** A secret a slice reads from the environment is named `<SLICE>__<FIELD>`: the slice's table name and the field, joined by a double underscore, with nested entries joined the same way (`<SLICE>__<ENTRY>__<FIELD>`). Each slice sets `env_prefix="<SLICE>__"` and `env_nested_delimiter="__"` and declares no per-field environment alias, which pydantic-settings applies without the prefix ([pydantic-settings](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/)). The double underscore is the hierarchy separator of ASP.NET Core and Dynaconf ([ASP.NET Core configuration](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/configuration/), [Dynaconf](https://www.dynaconf.com/envvars/)); it cannot collide with platform and SDK names such as `AWS_REGION`, or with a field name that contains a single underscore. Deployment identity (`ENVIRONMENT`, `GIT_SHA`) keeps its bare name.

**Plugin enablement lives in the configuration files.** Every plugin's entry point has an enablement key in the base file; an environment file may override it. The host skips a disabled plugin before registering it and never validates its settings slice ([plugins.md](plugins.md)).

**Vendor enablement is the presence of a tenant entry.** A vendor client (`integrations/<vendor>/`) is available when its settings slice holds a tenant entry (`SubModel | None`, a list once an instance has several tenants), as Backstage enables an integration by configuring it ([Backstage integrations](https://backstage.io/docs/integrations/), [pydantic-settings nested models](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/)). There is no `<VENDOR>_ENABLED` key. A present entry requires its secrets and is shape-checked at boot with no network call; an absent entry means the vendor is not configured. An invalid vendor slice fails boot, like a capability slice. The entry carries the vendor's real tenant id ([workplace-systems.md](workplace-systems.md) rule 3). Runtime on/off is a flag, not vendor setup ([OpenFeature](https://openfeature.dev/docs/reference/intro)). A platform transport is host code, not a vendor client: it has an enablement key in the configuration files like a plugin ([plugins.md](plugins.md)).

**Runtime flags use OpenFeature.** Gradual rollout or a kill switch without a deploy uses [OpenFeature](https://openfeature.dev/) with the self-hosted flagd provider, added only when a feature needs one. Configuration files are not reloaded at runtime.

**Environment identity.** `ENVIRONMENT: Literal["local", "ci", "dev", "staging", "production"]` is the only source of "which deployment am I?". Deriving it from hostnames, prefixes or `sys.modules` is prohibited. Security-relevant toggles (dev bypass) also need their own explicit boolean that defaults off: two independent guards. Command naming, so a dev and a prod bot coexist in one Slack workspace, is a transport setting (`COMMAND_PREFIX`) and is never derived from `ENVIRONMENT` ([transport-slack.md](transport-slack.md)).

**Fail fast, on static checks only.** Every slice validates in lifespan's configuration phase ([lifecycle.md](lifecycle.md)); an invalid file or a missing required secret fails boot with a message naming the key. A setting a feature needs only when it is enabled is required by that feature's slice, which is validated only when the plugin is enabled. An invalid feature slice skips that feature; an invalid host, capability or vendor slice fails boot ([plugins.md](plugins.md)). Validation checks presence and shape and never calls a service. Whether a credential actually works is the plugin's credential check, run after registration ([lifecycle.md](lifecycle.md)). `access/request`'s `ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG` validator is the pattern.

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
- Boot test: a disabled plugin's slice is never validated; an enabled feature with a missing required key is skipped with an event naming the key.
- Boot test: missing required secret → clean failure naming it.
- Boot test: a vendor slice with a tenant entry missing a secret or failing its shape check fails boot naming the key; an absent entry boots with the vendor unconfigured and no network call.
- grep: no settings field named `<VENDOR>_ENABLED` in `integrations/` (`SLACK_ENABLED` excepted until TASK-112).
- grep: no environment derivation outside `ENVIRONMENT`; no `os.environ` reads outside settings classes.
- Review: no feature or capability reads an environment variable directly.

## Migration

Tickets: TASK-24 (single home per vendor, `SecuritySettings` slice), TASK-111 (configuration files and TOML loading, and the environment renames), TASK-112 (tenant entries and the Slack transport key in the configuration files).

Tolerated until closed:
- dual vendor homes in `infrastructure/configuration/integrations/` and `integrations/<vendor>/settings.py`;
- feature slices in `infrastructure/configuration/features/`;
- security settings split across `AppSettings` and `ServerSettings`;
- all non-secret settings, and feature and job switches, read from environment variables;
- plain environment-variable secrets;
- flat, bare or aliased environment names (`SLACK_BOT_TOKEN`, `APP_TOKEN`, `SLACK__COMMAND_PREFIX`), until TASK-111 renames the variables that remain after values move into the files;
- `SLACK_ENABLED` as the interim Slack transport switch, with `SLACK_TEAM_ID` required when it is on, until TASK-112; Google in use when its service-account key file is set;
- production values held in the `sre-bot-config` and `sre-bot-config-infrastructure` SSM parameters, which `app/bin/entry.sh` writes to `.env` at container start and terraform reads but does not manage.

**Changes:**
- 2026-09-24: Migration names epic tickets only; values move to per-environment TOML files with plugin enablement, and the closed `PREFIX` and aggregator items are removed.
- 2026-09-25: settings validation stays static and runs only for enabled plugins; an invalid feature slice skips that feature; credential validity is a separate boot check.
- 2026-10-15: a vendor client is enabled by a tenant entry in its slice, with no `<VENDOR>_ENABLED` key; an invalid vendor slice fails boot; the Slack transport gets an enablement key in the configuration files (TASK-153).
- 2026-10-19: environment names mirror the configuration path (`<SLICE>__<FIELD>`, double-underscore nesting, no per-field aliases); the renames ride with TASK-111, once, for the variables that remain.
