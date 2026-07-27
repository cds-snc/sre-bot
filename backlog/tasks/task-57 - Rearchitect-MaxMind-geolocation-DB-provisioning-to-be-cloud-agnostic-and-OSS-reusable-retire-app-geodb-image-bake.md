---
id: TASK-57
title: >-
  Rearchitect MaxMind geolocation DB provisioning to be cloud-agnostic and
  OSS-reusable (retire app/geodb/ image bake)
status: To Do
assignee: []
created_date: '2026-07-27 16:08'
labels:
  - architecture
  - layers
  - cloud-portability
milestone: m-4
dependencies: []
references:
  - decisions/layers.md
  - decisions/cloud-portability.md
priority: medium
ordinal: 85000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
app/geodb/ is a top-level directory outside the three-tier model (decisions/layers.md) containing a committed GeoLite2-City.mmdb - a local dev copy of the MaxMind database. The production provisioning path is AWS- and CI-coupled and image-baked:
- .github/workflows/refresh_geodb.yml (cron every 4h) downloads GeoLite2-City from MaxMind using MAXMIND_LICENSE and uploads the tarball to an S3 bucket via an OIDC-assumed AWS role.
- .github/workflows/build_and_deploy.yml and ci_container.yml download the tarball from that S3 bucket at build time.
- Dockerfile COPYs GeoLite2-City.tar.gz into /app/geodb/, extracts the .mmdb, and bakes it into the image.
- At runtime app/integrations/maxmind/client.py reads a fixed MAXMIND_DB_PATH pointing at the baked file.

This couples geolocation to a specific AWS account/bucket/OIDC role and to a build-time image bake, which undermines two goals: cloud portability (decisions/cloud-portability.md) and keeping the app reusable as open source (a fork cannot obtain the DB without replicating our AWS plumbing, and cannot swap the source).

Target direction to evaluate and record: expose geolocation as a configurable capability whose DB source is a deployment detail - e.g. a configurable path/URL/object-store source resolved through settings, and/or an optional side geolocation service (a configurable compose service) so OSS adopters can plug in their own provider without the S3+image-bake pipeline. The committed dev .mmdb, the refresh workflow, and the Dockerfile bake are all in scope for the redesign.

This is an architecture task: it needs a decision (or a layers.md/cloud-portability.md note) on the target provisioning model before implementation, and a human-approved plan. Likely needs decomposition per the single-PR size gate.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A decision (or layers.md/cloud-portability.md note) records the target provisioning model for the geolocation DB: source configurable via settings and not hard-coupled to a specific AWS account/bucket, with an OSS-reusable path that does not require replicating our S3+OIDC pipeline
- [ ] #2 app/integrations/maxmind/client.py resolves the DB source through configuration rather than a fixed baked path, with the source swappable per deployment
- [ ] #3 The image-bake path (Dockerfile COPY/extract), the committed app/geodb/GeoLite2-City.mmdb dev copy, and .github/workflows/refresh_geodb.yml are re-evaluated and either removed or made optional/configurable per the recorded model
- [ ] #4 layers.md non-tier-directories section records app/geodb/ disposition and this ticket; geolocate healthcheck/tests pass against the new provisioning path
<!-- AC:END -->
