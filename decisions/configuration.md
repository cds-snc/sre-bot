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
- AWS settings live only in `integrations/aws/settings.py`. Slack settings live only in `integrations/slack/settings.py`. OpenAI, Trello, MaxMind, Notify, OpsGenie and Sentinel live only in `integrations/<vendor>/settings.py`, and Google in `integrations/google_workspace/settings.py`. `GOOGLE_RESOURCES`, the Google document and folder ids of several features, is read by `GoogleResourcesConfig` in the same module.
- Some feature settings sit with their feature (`packages/access/common`, `incident/scribe`, `oncall_sync`, `user_rotations`); others sit in `infrastructure/configuration/features/` (`atip`, `aws_ops`, `groups`, `incident`, `sre_ops`).
- Security settings (`ISSUER_CONFIG`, the `CORS_ALLOWED_*` lists, `DEV_BYPASS_ENABLED`, `DEV_BYPASS_TOKEN`) live in one `SecuritySettings` slice in `infrastructure/security/settings.py`, beside the code that reads them; TASK-116 moves both to `server/security/`.
- `AppSettings.ENVIRONMENT` is typed `Literal["local", "ci", "production"]`, is required, and drives environment-conditional behaviour. The app runs in three places: local development (including GitHub Codespaces), the CI workflow, and one production deployment on ECS Fargate.
- Production values come from two SSM parameters, `sre-bot-config` and `sre-bot-config-infrastructure`, each a block of `KEY=value` lines mixing secrets and non-secrets, which `app/bin/entry.sh` writes to `.env` at container start. The task definition adds `BACKEND_URL`, `CORS_ALLOWED_ORIGINS`, `FORWARDED_ALLOW_IPS` and `SLACK__COMMAND_PREFIX` as plain environment variables and one secret (`GCP_SRE_SERVICE_ACCOUNT_KEY_FILE`) through `secrets:`. `AppSettings.PREFIX` no longer exists, and the `Settings` aggregator in `infrastructure/configuration/settings.py` is gone.
- Which features and jobs run is decided by environment variables and `ENVIRONMENT` checks in code.
- Vendor clients have no enablement rule, because they are clients, not plugins, and the per-entry-point key never reaches them. `SLACK_ENABLED` is an environment variable read by one slice, and it mixes two meanings: run the Slack transport, and have a Slack workspace. Google has no flag: it is in use when `GCP_SRE_SERVICE_ACCOUNT_KEY_FILE` is set, and `GOOGLE_WORKSPACE_CUSTOMER_ID` defaults to the `my_customer` API alias, not a tenant id.

The app is promoted as one image through every environment, and plugins are enabled per environment ([plugin-architecture.md](plugin-architecture.md)). Environment variables are a poor home for non-secret, reviewable configuration: they are invisible in the repo and differ silently between environments.

## Decision

**Settings live with their owner.** Each owner defines one typed `pydantic_settings.BaseSettings` slice next to its code:
- features: `features/<feature>/settings.py`;
- capabilities: `capabilities/<capability>/settings.py`;
- hosting services: `infrastructure/<service>/settings.py`;
- vendor clients: `integrations/<vendor>/settings.py`.

A system reached in more than one role holds one least-privilege credential per role, not one shared login. For example, Slack's bot and Socket Mode tokens (transport) are separate from an admin token used by a feature that changes Slack ([platform-transports.md](platform-transports.md)). A recurring job's schedule and lease TTL belong to the job's feature, not a central scheduler slice ([reliability.md](reliability.md)). The security domain owns a `SecuritySettings` slice: issuers and JWKS, the CORS allow-list, the rate-limit backend and the dev-bypass settings. One key has exactly one owning slice.

**Values come from checked-in TOML configuration files.** `app/config/base.toml` holds defaults for every slice; one file per `ENVIRONMENT` value (`local.toml`, `ci.toml`, `production.toml`) overrides it. Files are reviewed like code and validated at boot. The base file is secure and production-shaped (dev bypass off, no wildcard CORS); `local.toml` holds the developer-friendly overrides.

**Loading order.** An identity slice reads `ENVIRONMENT` and `GIT_SHA` from the process environment only, never from a file, and selects the files: the base file, then the environment file. Both must exist; pydantic-settings silently skips a missing file, so the loader checks. The two files are deep-merged, so an environment file overrides key by key and never drops the base file's other keys in a table (`TomlConfigSettingsSource(..., deep_merge=True)`). Each slice reads only its own table (`toml_table_header`, pydantic-settings 2.15 or later: [releases](https://github.com/pydantic/pydantic-settings/releases)). A value resolves from, highest first: constructor arguments (tests), the process environment, the `.env` file, the configuration files, the field default. The settings-slice base class and the Protocol that supplies the file list are in `contracts/configuration.py`, so every layer that owns a slice can import them; the loader that implements the Protocol is host code in `server/configuration/` ([plugin-architecture.md](plugin-architecture.md)). This is the order ASP.NET Core and Backstage use: the host learns its environment first, then loads the base and environment files ([ASP.NET Core configuration](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/configuration/), [Backstage configuration](https://backstage.io/docs/conf/writing)).

**Environment variables carry only secrets and platform-provided names.** The platform-provided names are a closed list: `ENVIRONMENT`, `GIT_SHA` and `FORWARDED_ALLOW_IPS` (derived from the VPC subnets by terraform and read by uvicorn, not the app: [uvicorn settings](https://uvicorn.dev/settings/)). Everything else, including values terraform could compute such as the public URL and the CORS origins, is in the configuration files, where a change is reviewed. Names that an SDK or runtime reads itself (`AWS_*`, including `AWS_REGION` and `AWS_ENDPOINT_URL_<SERVICE>` ([AWS SDK endpoints](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)), `UVICORN_*`, `OTEL_*`) are outside the app's naming rule: no slice declares them as fields, and the ownership check allow-lists them.

**Environment names mirror the configuration path.** A secret a slice reads from the environment is named `<SLICE>__<FIELD>`: the slice's table name and the field, joined by a double underscore, with nested entries joined the same way (`<SLICE>__<ENTRY>__<FIELD>`). Each slice sets `env_prefix="<SLICE>__"` and `env_nested_delimiter="__"` and declares no per-field environment alias, which pydantic-settings applies without the prefix ([pydantic-settings](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/)). The double underscore is the hierarchy separator of ASP.NET Core and Dynaconf ([ASP.NET Core configuration](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/configuration/), [Dynaconf](https://www.dynaconf.com/envvars/)); it cannot collide with platform and SDK names such as `AWS_REGION`, or with a field name that contains a single underscore. The platform-provided names keep their bare names.

**Case.** Field names and TOML keys are lower snake_case (PEP 8 attribute names, TOML convention); environment names are upper case, the convention POSIX sets for environment variables ([POSIX XBD 8.1](https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap08.html)). Each slice sets `case_sensitive=False`, so `SLACK__TENANT__BOT_TOKEN` fills `tenant.bot_token`, as Spring Boot's relaxed binding and ASP.NET Core's case-insensitive keys bridge the same gap ([Spring Boot external configuration](https://docs.spring.io/spring-boot/reference/features/external-config.html)). `case_sensitive=True` would force upper-case field names and TOML keys, and since pydantic-settings 2.15 it also applies to file sources and nested keys. Two names that differ only by case are one key for ownership, which the CI check compares case-insensitively.

**Renaming an environment name.** The new name is published on the deployment side beside the old one before the code that reads it deploys; the code reads only the new name, with no alias and no compatibility shim; the old name is removed once the deploy is verified. The ECS circuit breaker rolls a failed deploy back to the previous task-definition revision ([ECS deployment circuit breaker](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-circuit-breaker.html)), and that revision still reads the old name, so rollback stays safe. A value is never renamed in place inside a store that both revisions read. This is a parallel change whose contract step follows the verified deploy ([Parallel change](https://martinfowler.com/bliki/ParallelChange.html)).

**Plugin enablement lives in the configuration files.** Every plugin's entry point has an enablement key in the base file; an environment file may override it. The host skips a disabled plugin before registering it and never validates its settings slice ([plugins.md](plugins.md)).

**Vendor enablement is the presence of a tenant entry.** A vendor client (`integrations/<vendor>/`) is available when its settings slice holds a tenant entry (`SubModel | None`, a list once an instance has several tenants), as Backstage enables an integration by configuring it ([Backstage integrations](https://backstage.io/docs/integrations/), [pydantic-settings nested models](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/)). There is no `<VENDOR>_ENABLED` key. A present entry requires its secrets and is shape-checked at boot with no network call; an absent entry means the vendor is not configured. An invalid vendor slice fails boot, like a capability slice. The entry carries the vendor's real tenant id ([workplace-systems.md](workplace-systems.md) rule 3). Runtime on/off is a flag, not vendor setup ([OpenFeature](https://openfeature.dev/docs/reference/intro)). A platform transport is host code, not a vendor client: it has an enablement key in the configuration files like a plugin ([plugins.md](plugins.md)).

**Runtime flags use OpenFeature.** Gradual rollout or a kill switch without a deploy uses [OpenFeature](https://openfeature.dev/) with the self-hosted flagd provider, added only when a feature needs one. Configuration files are not reloaded at runtime.

**Environment identity.** `ENVIRONMENT: Literal["local", "ci", "production"]`, required with no default, is the only source of "which deployment am I?". `local` is development on a workstation or in Codespaces, `ci` is the test run (locally and in the CI workflow), `production` is the deployment. Adding an environment is one more `Literal` value and one more configuration file; a test fails when a value has no file. Deriving it from hostnames, prefixes or `sys.modules` is prohibited. Security-relevant toggles (dev bypass) also need their own explicit boolean that defaults off: two independent guards. Command naming, so a dev and a prod bot coexist in one Slack workspace, is a transport setting (`COMMAND_PREFIX`) and is never derived from `ENVIRONMENT` ([transport-slack.md](transport-slack.md)).

**Fail fast, on static checks only.** Every slice validates in lifespan's configuration phase ([lifecycle.md](lifecycle.md)); an invalid file or a missing required secret fails boot with a message naming the key. Every slice on the configuration files sets `extra="forbid"`, so a misspelled key in its table fails boot naming it; a table that no slice owns fails the CI check. A setting a feature needs only when it is enabled is required by that feature's slice, which is validated only when the plugin is enabled. An invalid feature slice skips that feature; an invalid host, capability or vendor slice fails boot ([plugins.md](plugins.md)). Validation checks presence and shape and never calls a service. Whether a credential actually works is the plugin's credential check, run after registration ([lifecycle.md](lifecycle.md)). `access/request`'s `ACCESS_REQUESTS_FALLBACK_APPROVER_SLUG` validator is the pattern.

**Secrets.** Secret material resolves through the secrets contract ([cloud-portability.md](cloud-portability.md)) or is injected by the platform at deploy time. On ECS each secret is one SSM SecureString parameter, injected under its `<SLICE>__<FIELD>` name by the task definition's `secrets:` ([ECS secrets from Parameter Store](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-ssm-paramstore.html)). Terraform creates each parameter and its `secrets:` entry; the value is set outside terraform (`ignore_changes` on the value), so it never reaches terraform state or the repository. A secret missing at start keeps the task from running, and the circuit breaker rolls back. One parameter per secret matches the existing service-account key parameter, costs nothing at the standard tier, and lets each value change alone; Secrets Manager's rotation does not apply to these vendor tokens. No container-start script fetches configuration. Plain environment-variable secrets are tolerated, not the target. Secrets never appear in configuration files, defaults, logs ([observability.md](observability.md)) or `repr`. JWKS refreshes at runtime; static secrets rotate by redeploy.

**Consumers receive slices.** A service constructor takes its own settings slice, nothing wider. No aggregator of all settings exists.

**Migration rides with the work.** Any task that touches a domain's service moves that domain's slice to its target home in the same change and deletes the old one. That covers slices whose move is scheduled. Slices with no scheduled move (the host, security, vendor and hosting slices), and every value production sets today, move onto the configuration files in TASK-111, so no value is left in the old store. A feature value moves under its current class's table: table names do not depend on module paths, so a later package move relocates the class and leaves the files alone.

## Consequences

- "Where is this configured?" has one answer per owner; deleting a feature deletes its configuration.
- Differences between environments are visible in a diff of two files.
- A typo in `ENVIRONMENT` or a configuration key is a validation error at boot.
- Cost: a change to non-secret configuration needs a PR and a deploy; runtime changes need a flag.

## Checks

- CI (`bin/check_settings_key_ownership.py`): each key is owned by exactly one settings slice, compared case-insensitively.
- CI: no secret-shaped key (token, password, key) appears in a configuration file, and gitleaks finds no secret in the repository ([gitleaks](https://github.com/gitleaks/gitleaks)).
- CI (same script): each table in a configuration file is owned by exactly one slice; the platform-provided names and the SDK and runtime namespaces are allow-listed.
- Unit test: `base.toml` and one file per `ENVIRONMENT` value exist and parse.
- Boot test: a missing configuration file, malformed TOML or an unknown key in a slice's table fails boot naming the file, table and key.
- Boot test: every plugin entry point has an enablement key in the base file.
- Boot test: a disabled plugin's slice is never validated; an enabled feature with a missing required key is skipped with an event naming the key.
- Boot test: missing required secret → clean failure naming it.
- Boot test: a vendor slice with a tenant entry missing a secret or failing its shape check fails boot naming the key; an absent entry boots with the vendor unconfigured and no network call.
- CI (same script): no settings key named `<VENDOR>_ENABLED` in `integrations/` (`SLACK_ENABLED` excepted until TASK-112); no `os.environ` or `os.getenv` reads outside settings classes (`bin/` developer scripts and tests excepted).
- grep: no environment derivation outside `ENVIRONMENT`.
- Review: no feature or capability reads an environment variable directly.

## Migration

Tickets: TASK-24 (single home per vendor, `SecuritySettings` slice), TASK-111 (configuration files and loading, every value production sets onto them, the secret renames and the end of the SSM parameters; split into TASK-111.1 to 111.15), TASK-112 (the Slack transport key in the configuration files), TASK-158 (the `[google_resources]` table removed), TASK-159 (`infrastructure/configuration/` removed).

Tolerated until closed:
- `GOOGLE_RESOURCES`, feature data, in the Google vendor module `integrations/google_workspace/settings.py` instead of the owning feature slices; TASK-111 turns it into an interim `[google_resources]` table, each owner moves its ids into its own table (TASK-145.6, 145.7, 145.10, 145.12, 39, 88), and TASK-158 deletes it;
- feature slices in `infrastructure/configuration/features/` (incident, sre_ops and aws_ops once TASK-111 deletes the dead atip and groups slices), until their features move; TASK-159 deletes the package;
- non-secret settings, and feature and job switches, read from environment variables, until TASK-111 moves them onto the files (feature switches: TASK-112);
- plain environment-variable secrets and flat, bare or aliased environment names (`SLACK_BOT_TOKEN`, `APP_TOKEN`, `SLACK__COMMAND_PREFIX`), until TASK-111 publishes each remaining secret under its `<SLICE>__<FIELD>` name;
- upper-case field names and `case_sensitive=True`, until TASK-111 lower-cases each slice it migrates; feature slices change with their package move;
- `SLACK_ENABLED` as the interim Slack transport switch, with `SLACK_TEAM_ID` (or, for an Enterprise org, the enterprise id) required when it is on and checked against every inbound request ([workplace-systems.md](workplace-systems.md) rule 3), until TASK-112; Google in use when its service-account key file or customer id is set, both then required;
- tenant entries derived from those flat variables (`SlackSettings.tenant`, `GoogleWorkspaceSettings.tenant`, frozen sub-models read by every consumer instead of the flat fields), until TASK-111 moves each into the vendor's table in the configuration files (`[slack.tenant]`, `[google_workspace.tenant]`), with its secrets named `<SLICE>__TENANT__<FIELD>`;
- production values held in the `sre-bot-config` and `sre-bot-config-infrastructure` SSM parameters, which `app/bin/entry.sh` writes to `.env` at container start and terraform reads but does not manage, until TASK-111 moves every value out and deletes them.

**Changes:**
- 2026-09-24: Migration names epic tickets only; values move to per-environment TOML files with plugin enablement, and the closed `PREFIX` and aggregator items are removed.
- 2026-09-25: settings validation stays static and runs only for enabled plugins; an invalid feature slice skips that feature; credential validity is a separate boot check.
- 2026-10-15: a vendor client is enabled by a tenant entry in its slice, with no `<VENDOR>_ENABLED` key; an invalid vendor slice fails boot; the Slack transport gets an enablement key in the configuration files (TASK-153).
- 2026-10-19: environment names mirror the configuration path (`<SLICE>__<FIELD>`, double-underscore nesting, no per-field aliases); the renames ride with TASK-111, once, for the variables that remain.
- 2026-10-20: the security settings are one `SecuritySettings` slice (TASK-24.2); the split-security tolerance is closed.
- 2026-10-20: Slack settings have one home, `integrations/slack/settings.py`; the legacy slice in `infrastructure/configuration/integrations/` and `SlackPlatformSettings` are deleted, and only Google is left in the tolerated second home (TASK-24.3).
- 2026-10-20: Google settings have one home, `integrations/google_workspace/settings.py`, and `infrastructure/configuration/integrations/` is deleted; `GOOGLE_RESOURCES` waits in the same module until TASK-111 splits it into feature slices (TASK-24.4).
- 2026-10-20: the interim Slack tenant entry is `SLACK_TEAM_ID` or, for an Enterprise org, `SLACK_ENTERPRISE_ID`, checked against every inbound request (TASK-157).
- 2026-10-20: the interim tenant entries are frozen sub-models derived from the flat variables and read by every consumer; Google's entry is present when its key file or customer id is set and then needs both, and the customer id has no `my_customer` default (TASK-24.5).
- 2026-10-20: environment names are upper case and matched exactly by each slice; key ownership compares them case-insensitively, and one CI script enforces ownership, the vendor-switch ban and the `os.environ` ban (TASK-24.6).
- 2026-10-20: TASK-111 planning. Field names and TOML keys are lower snake_case with `case_sensitive=False` (replaces the exact-match rule above); `ENVIRONMENT` is `local`, `ci` or `production`, required, one configuration file each; the identity-first loading order, deep merge and table per slice (pydantic-settings 2.15 or later), with the slice base in `contracts/` and the loader in `server/configuration/`; "deployment identity" becomes a closed list of platform-provided names, and SDK and runtime namespaces are exempt; renames publish the new name beside the old one and remove it after the verified deploy, with no alias (settling the AliasChoices question); secrets are SSM SecureString parameters through task-definition `secrets:`, and no start script fetches configuration (the TASK-54 retirement rides with TASK-111); `extra="forbid"` per slice and no unowned table; TASK-111 moves every value production sets; the tolerated list names its closing tickets.
