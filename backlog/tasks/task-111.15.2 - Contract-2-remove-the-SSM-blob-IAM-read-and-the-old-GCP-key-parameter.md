---
id: TASK-111.15.2
title: 'Contract 2: remove the SSM blob IAM read and the old GCP key parameter'
status: Done
assignee: []
created_date: '2026-10-22T13:57:00Z'
updated_date: '2026-10-29T14:09:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.15.1
references:
  - terraform/iam.tf
  - terraform/ssm.tf
  - .github/workflows/tf_plan.yml
  - .github/workflows/tf_apply.yml
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1779
parent_task_id: TASK-111.15
priority: medium
type: feature
ordinal: 430000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second half of TASK-111.15, after the TASK-111.15.1 deploy is verified. Removes the IAM read on sre-bot-config and sre-bot-config-infrastructure (terraform/iam.tf:32-34), the old gcp_sre_service_account_key parameter's terraform resource and variable (terraform/ssm.tf:1, variables.tf:16; its value sits in terraform state today) and the TF_VAR_gcp_sre_service_account_key lines in tf_plan.yml and tf_apply.yml. The blob's ISSUER_CONFIG key is read only by images older than TASK-111.8 and goes with sre-bot-config; it needs no separate step. Checks TASK-54's AC #3 (entry.sh fetches no SSM parameter, delivered by TASK-111.15.1). Human, after merge: delete both SSM parameters and the GCP_SRE_SERVICE_ACCOUNT_KEY_FILE GitHub secret, and set TASK-54 to Done.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The IAM policy no longer grants read on sre-bot-config or sre-bot-config-infrastructure
- [x] #2 The old gcp_sre_service_account_key resource and variable are gone, and no TF_VAR_gcp_sre_service_account_key line remains in tf_plan.yml or tf_apply.yml
- [x] #3 The PR's tf plan shows only the IAM and parameter removals; nothing replaced
- [x] #4 TASK-54's AC #3 is checked; TASK-54 is left for the human to set Done
- [x] #5 bin/env-checks.zsh and app/bin/audit_env_names.py drop their migration part (SSM blob reads, doc-14 destinations, the baseline retired names, HINTS); the env-file, Codespaces and GitHub Actions audit stays, and its tests pass
- [x] #6 The dead TF_VAR_google_oauth_pickle_string lines are deleted from tf_plan.yml and tf_apply.yml (no terraform variable reads them; a leftover of the pre-service-account OAuth admin user, found 2026-10-26), and the Actions secret GOOGLE_PICKLE_STRING is deleted (human, after merge)
- [x] #7 The /sre-bot/TRELLO__APP_KEY and /sre-bot/TRELLO__TOKEN parameters (never read; no longer injected since TASK-111.15.1) are removed from terraform/ssm.tf after 111.15.1's Verify passed: revision 67 and earlier reference their ARNs, so they stay until the IAM read removal ends those revisions as rollback targets
- [ ] #8 Migration-only tooling and tests are pruned in this PR, each deletion citing what it guarded (a name production supplied through the blobs, a doc-14 row, or a name retired since TASK-111.1), with the steady-state checks kept: (a) bin/env-checks.zsh drops the blob scan and the BASELINE retired-name diff; (b) app/bin/audit_env_names.py drops the blob verdicts, the split-line rule, HINTS, SUPERSEDED, the retired-name baseline and the doc-14 reader (AC #5); (c) app/bin/audit_env_coverage.py takes its names from the env_only fields and terraform/ssm.tf instead of doc-14, keeping the terraform, SSM-set and Codespaces checks and the development-unconfigured rule, and dropping the source and old-name columns; (d) bin/deploy-checks.zsh drops BLOBS, blob_where and blob_value; (e) the matching cases in test_bin_audit_env_names_classify.py, test_bin_audit_env_names_dynamic_refs.py, test_bin_audit_env_names_fix_commands.py and test_bin_audit_env_coverage_classify.py go; (f) the retired-name pins (RETIRED_NAMES in the integration conftests, the per-slice 'flat name reaches no field' tests) and test_configuration_settings_production_names.py's blob cases (spaced .env lines, the retired-name lists) go, since a ConfigurationSlice reads only its own prefix and check-settings-key-ownership enforces it; (g) doc-14 is archived (backlog doc, CLI) once the blobs are deleted
- [x] #9 A task check `contract` in bin/deploy-checks.zsh (post, read-only, names and verdicts only) reports the IAM policy without the blob and old GCP key ARNs, the three destroyed parameters not found, and the running revision healthy; the sentinel and names_only checks and their blob helpers are gone
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Human: both SSM parameters and the GCP_SRE_SERVICE_ACCOUNT_KEY_FILE GitHub secret are deleted after the deploy is verified
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Size and gate
One PR, mostly deletions (human 2026-10-29: a deleting PR is not bound by the size gate; not decomposed). Estimate: ~32 files, about -1100 LOC (tests ~-650, tooling ~-350, terraform/workflows ~-45) and about +70 LOC added (audit_env_coverage.py reshaped onto env_only + terraform/ssm.tf, a `contract` post check). Subsystems: terraform, workflows, dev tooling, tests; no app runtime code, so the app gates are not the verification for the tooling (bin tests + ruff are), but the tests under app/ run the full gates because test files change.

## Facts found (path:line)
- terraform/iam.tf:32-34 blob ARNs + gcp key ARN in the ssm statement; :35 the /sre-bot secret ARNs stay. terraform/ssm.tf:1-11 gcp param, :54,:58 Trello names, :61 sre_bot_unread_secret_names; terraform/ecs.tf:31-35 the setsubtract on that local. terraform/variables.tf:16-20 variable. .github/workflows/tf_plan.yml:12,14 and tf_apply.yml:15,17.
- skip_destroy is only on the TASK DEFINITION (ecs.tf), not on the parameters. Removing the Trello names and the gcp resource from terraform therefore DESTROYS those three parameters in AWS at tf_apply (not "forgotten"). The blob parameters (sre-bot-config, sre-bot-config-infrastructure) are not in terraform at all: only a human delete removes them. No template (terraform/templates) references the gcp parameter; revision :69 and the task definition no longer inject the Trello ARNs (revisions <=67 do; they stop being rollback targets anyway once the IAM read goes, since those images fetch the blobs).
- The IAM policy is on sre-bot-ecs-role, which is both execution_role_arn and task_role_arn (ecs.tf:12,17).
- google_oauth_pickle_string: no terraform variable, only the two workflow lines (dead).
- LICENSE_KEY: '${MAXMIND_KEY}' at .devcontainer/docker-compose.yml:21 stays (human 2026-10-29: MAXMIND_KEY is needed; never mark it for deletion).

## Steps (ordered)
1. Terraform (AC1, AC2, AC3, AC7): iam.tf drop :32-34 (keep the concat of the sre_bot_secret ARNs, simplify the concat); ssm.tf delete the gcp resource, delete TRELLO__APP_KEY and TRELLO__TOKEN from the set and delete sre_bot_unread_secret_names; ecs.tf :31-35 iterate sort(local.sre_bot_secret_names) directly and drop the comment (the secrets JSON is byte-identical to :69, so no new task definition revision); variables.tf delete gcp_sre_service_account_key. Update the ssm.tf header comment that cites the doc-14 rename map.
2. Workflows (AC2, AC6): delete the TF_VAR_google_oauth_pickle_string and TF_VAR_gcp_sre_service_account_key lines in tf_plan.yml and tf_apply.yml (and the stray blank lines in tf_apply.yml).
3. bin/deploy-checks.zsh (AC8d): delete BLOBS, blob_where (no callers), blob_value, param_hash, same_hash, the sentinel and names_only task checks; replace TASK_CHECKS with one post-only check `contract` (see Verification); PRE_CHECKS empty and the pre-only validation loop removed (dead). Keep the generic pre/post sections.
4. bin/env-checks.zsh (AC5, AC8a): delete BLOBS, BASELINE, the blob scan, the git archive of the baseline and the baseline-names cache; the audit_env_names calls lose the sha/tree arguments. KEEP the /sre-bot get-parameters-by-path scan (ssm-param rows): it is the steady SSM-set evidence audit_env_coverage uses (see OQ1). Reword the "Migration part" comment to "SSM".
5. app/bin/audit_env_names.py (AC5, AC8b): delete HINTS (75-163), SUPERSEDED (165-186), baseline_names/CACHE (51, 227-236), BLOB_END, _split_line, _production_blob and the ssm-blob dispatch in classify, replacement, _is_retired, the retired Context fields, parameter_rows/staged_parameters/doc14_destinations/config_table users, the LEGEND blob sentence, and the baseline argument in main; remove the HINTS/SUPERSEDED branches inside _developer and _actions. Keep Verdict, Context (slimmed), env_names, workflow_references, setup_references, RUNTIME, _github_target, fix_commands, read_last_refs, unprovided_workflow_references. Evidence for each deletion: HINTS/SUPERSEDED entries and the BLOB_END sources named in the module docstring; retired names listed in the pins. Keep PARAMETER_DESTINATION/REPO_ROOT/Destinations/Verdict only if coverage still imports them after step 6 (delete what it does not).
6. app/bin/audit_env_coverage.py (AC8c): names come from contracts.configuration env_only fields (the same metadata app/bin/generate_env_example.py reads: _env_only 70-72) plus terraform_parameters() (already parses ssm.tf, :49-52); drop the doc-14 reader, the source and old-name columns, the blob branches (72-73, 84-89). Keep the terraform check, the SSM-set check, the Codespaces gap check (91-95) and unconfigured_in_development (55-60). Identifiers whose values reach print use names without secret/token/key/password (CodeQL), e.g. `credential_names`, `param_state`.
7. MAXMIND_KEY and the .devcontainer LICENSE_KEY line are not touched (human 2026-10-29). After steps 5-6, the audits must never give MAXMIND_KEY a delete verdict in any source (env file, Codespaces, Actions, Dependabot): verify on the reshaped classification, and pin it with a test if any path could reach delete.
8. Tests (AC5, AC8e, AC8f): per the survey, delete the migration-only cases and keep steady ones.
   - app/tests/unit/bin/test_bin_audit_env_names_classify.py: delete 78-105, 107-125, 128-190, 199-206, 230-272, 275-295, 297-405 (retired names, SUPERSEDED, blob lines, split lines, replacement); keep 43-76 (minus 49-52 retired rows), 193-196, 209-227; shrink CTX (22-36) to the surviving fields.
   - test_bin_audit_env_names_dynamic_refs.py and _fix_commands.py: drop the baseline_names monkeypatches (93-98, 110/123; 139, 159), and the ssm-blob row (fix_commands:98); keep the rest.
   - test_bin_audit_env_coverage_classify.py: rewrite the helper and the expected-reason table (17-23) onto env_only + ssm.tf; delete 83-105, 145-186; keep 42-81, 107-141, 188-205 adapted.
   - app/tests/unit/infrastructure/configuration/test_configuration_settings_production_names.py: delete the retired-name tests and lists (188, 242, 256, 321, 371, 532 and tables 147-159, 203-210, 279-286, 331-345, 460-475) and the blob wording of the module docstring (1-40); KEEP the live ones (production names 101, lowercase/case rules, tenant tests, 430 spaced .env lines with reworded docstring, 402, 412, 450, 479-523). Keep any test whose assertion is a live field/validation behavior even if it mentions a retired name.
   - RETIRED_NAMES in the integration conftests (trello:19, maxmind:20, aws:19, google_workspace:19-26, openai:19, notify:19, opsgenie:19) and the per-slice tests that use them or inline lists (trello 85-102, maxmind 68-71, aws 137-156, google_workspace 98-104, openai 85-102, notify 86-98, opsgenie 79-88, sentinel 22/101, slack 36/56/178, security 30/50/144, incident_response 26/45/97, directory 21/110-114, coordination 22/111-114, audit 97-, features 92, jobs 64, server_slack_transport 5): delete the pin tests and lists; keep every test of a live behavior. Rationale: a ConfigurationSlice reads only its own prefix; check-settings-key-ownership enforces it (test_bin_settings_key_ownership_check stays; 593's wording fixed).
   - app/tests/unit/modules/atip/test_atip_settings_load.py:5 is legacy app/modules: left alone, flagged (OQ4).
   - Kept: test_bin_container_start_contract.py, generate_env_example tests, pytest-env blanks.
9. doc-14: archive after the blobs are deleted, as a human step (OQ2 recommendation) with `backlog doc archive doc-14`; nothing in the PR reads it after step 6 (rg doc-14 in app/bin, tests, terraform/ssm.tf comment returns zero). Also update decisions/configuration.md:19, :119 (blobs and IAM read gone; parameters deleted by the human) and the doc-11 row 9.15.2 in the same PR (memory rule: write decisions back).
10. TASK-54 (AC4): `backlog task edit task-54 --check-ac 3` after verifying entry.sh is gone (app/bin has no SSM fetch; test_bin_container_start_contract.py pins it; running revision :69 verified by 111.15.1 names_only PASS). Do not set TASK-54 Done. Also AC #4 of TASK-54 (no fetch logic in app/bin) is then true: mention it to the human.
11. Fix the 2026-10-26 note: append with `backlog task edit task-111.15.2 --append-notes` that TASK-158 is superseded by TASK-111.10.3 (no code reader of GOOGLE_RESOURCES remains) and does not split it; the remaining mentions are the tooling this PR prunes.

## AC traceability
AC1: step 1 (rg shows no blob ARN in iam.tf; tf plan shows the policy update). AC2: steps 1, 2. AC3: PR tf plan = 1 policy in-place update + 3 destroys (gcp, 2 Trello), no replace, no task definition change. AC4: step 10. AC5: steps 4-5, 8 (bin tests + ruff). AC6: step 2 (+ human secret delete). AC7: step 1. AC8a-g: steps 4, 5, 6, 3, 8, 8, 9. Enabling work justified: step 7 (dead), step 11 (note), `contract` check (new AC proposed).

## Test matrix
- audit_env_names: kept developer-name, Actions-reference, setup-reference, fix-command, dynamic-reference cases still pass (happy); an unevidenced name is still reported (boundary); no baseline argument needed (main runs without it).
- audit_env_coverage (test_bin_audit_env_coverage_classify.py): names from env_only fields, a name in ssm.tf but not set (SSM-set gap), a name set and in terraform (ok), a development-unconfigured name (rule kept), a Codespaces gap, a terraform gap; no source/old-name columns.
- terraform: `terraform validate`/fmt via the PR tf_plan check; `rg` zero hits for gcp_sre_service_account_key, google_oauth_pickle_string, sre_bot_unread_secret_names, BLOBS, blob_value, HINTS, SUPERSEDED, baseline_names (with --hidden).
- deploy-checks `contract` post and `zsh -n bin/deploy-checks.zsh bin/env-checks.zsh`.

## Verification
- cd app && uv run ruff check . ; uv run pytest tests/unit/bin (tooling); full pytest tests --ignore=tests/smoke and mypy because app/tests change; make env-example drift test.
- New post check `contract` (read-only, human runs): the sre-bot-secrets-manager policy default version names neither blob ARN nor the gcp ARN; `get-parameter` on the three destroyed parameters returns ParameterNotFound; the running revision is still :69 (or later) and the service shows no task start failures since the apply; prints names/verdicts only. The blobs' existence is reported as informational (they remain until the human deletes them).

## Rollout (human)
1. Before merge: note rollback target image tag df749d05f98afb45cf52e1773385130626470daa-2026-10-28 on :69 (the 175857b6 tag still fetches the blobs and stops working once the IAM read goes).
2. Merge to main runs tf_apply and build_and_deploy together. The apply removes the IAM read and destroys the three terraform parameters; the deploy renders from the latest revision (:69 content, no new secrets change). Run `bin/deploy-checks.zsh post contract` after both finish.
3. Blob parameters (not in terraform): the human deletes sre-bot-config and sre-bot-config-infrastructure from the AWS console (Systems Manager > Parameter Store, ca-central-1) a few tasks downstream of this merge (human 2026-10-29: destructive, deferred). Every later session prompt carries the reminder until done. Confirm read-only with `aws ssm get-parameter --region ca-central-1 --name sre-bot-config` returning ParameterNotFound (same for sre-bot-config-infrastructure).
4. Delete GitHub Actions secrets GCP_SRE_SERVICE_ACCOUNT_KEY_FILE and GOOGLE_PICKLE_STRING (names verified in tf_plan.yml:12,14 and tf_apply.yml:15,17): `gh secret delete GCP_SRE_SERVICE_ACCOUNT_KEY_FILE --repo cds-snc/sre-bot` and `gh secret delete GOOGLE_PICKLE_STRING --repo cds-snc/sre-bot`, after the merged PR's tf_apply has run (the next apply must not need them). Delete the old GCP service-account key in Google Cloud (IAM & Admin > Service accounts > the SRE service account > Keys) if it is still valid (its value was in tf state until the destroy); carried as a reminder in every later session prompt until done.
5. After the blobs are deleted (step 3): the human archives doc-14 (`backlog doc archive doc-14`) and sets TASK-54 Done, checking its AC #4; both carried as reminders in every later session prompt until done.

## Assumptions and doubts (with how to verify)
- A1: the secrets JSON in the rendered task definition is identical after step 1: `terraform plan` must show no aws_ecs_task_definition change (AC3). If it does, stop.
- A2: nothing else reads the destroyed parameters: rg --hidden gcp_sre_service_account_key|TRELLO__APP_KEY|TRELLO__TOKEN shows only the files in this plan (done at planning; repeat at implementation).
- A3: revisions <=67 stop being usable rollback targets at this merge: accepted since :69 is the stated rollback target and older images fetch the blobs.
- A4: deleting retired-name pins loses no live guard: each deleted test is checked for a live-behavior assertion before deletion; check-settings-key-ownership and extra="forbid" cover the rest. Verify by running the full tests after each file.
- A5: audit_env_coverage depends on audit_env_names symbols (PARAMETER_DESTINATION, REPO_ROOT, Destinations, Verdict, config_table): keep exactly what remains imported.
- A6: terraform_parameters in ssm.tf parser keeps working after the local is removed (the toset literal remains).

## Blast radius and rollback
Terraform: IAM narrowed (any task still on a blob-fetching image fails to start; circuit breaker rolls back to :69-class revisions which do not fetch). Destroyed parameters are unrecoverable (values for gcp key from the secret; Trello params were never read). One git revert restores IAM and terraform resources, but not the parameter values (re-put by a human) nor the blob parameters once the human deletes them: do the human deletes only after verification. Tooling/test deletions are revertible. Ordering: the human parameter and secret deletes come after the contract check.

## Review (human, 2026-10-29)
Approved with: OQ1 AC #5 reworded to 'SSM blob reads'; OQ2 doc-14 archived by the human after the blobs go; OQ3 the human sets TASK-54 Done (reminder carried); OQ4 blob delete deferred, the human deletes them in the console a few tasks downstream; OQ5 no Sentinel post check; OQ6 retired-name pins deleted; OQ7 rejected: MAXMIND_KEY and the LICENSE_KEY line stay and are never marked for deletion (AC #10 removed). The old GCP service-account key deletion is carried as a reminder.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-26: the env audit's SUPERSEDED map (old Google ID secrets folded into GOOGLE_RESOURCES by #975, FRONTEND_URL) goes with the migration part. GOOGLE_RESOURCES carries an unread key rep.g (folder for Google Groups reports, reader removed by #1460); TASK-158 splits GOOGLE_RESOURCES and drops it.

2026-10-28 (TASK-111.15.1 plan review, OQ3): the Trello parameters' deletion is this task's (AC added); decisions/configuration.md (rename rule) and decisions/deployment.md (skip_destroy, circuit breaker) already order it, no ADR gap. Sentinel: 111.15.1 moves the reads to SENTINEL__CUSTOMER_ID, SENTINEL__SHARED_KEY and [sentinel] log_type, so the blob deletion here loses no Sentinel value; the SENTINEL__* parameters stay until TASK-171's ruling.

2026-10-28 (human): the migration-only scripts and tests are pruned in this last PR of the chain (AC added with the inventory, surveyed against main plus the 111.15.1 working tree). Kept, steady state: test_bin_container_start_contract.py (no fetch can come back), the env_only metadata and make env-example with its drift test, the pytest-env blanks (a Codespace still injects them), check_settings_key_ownership, deploy-checks' generic param_hash and same_hash. Size gate at planning: these are deletions in dev tooling and tests riding with the IAM and parameter removals (standing decision), but the planner judges the mechanical-cleanup-plus-behaviour-change rule; split only if the gate requires it. Preconditions: 111.15.1 Done (its sentinel and names_only task checks deleted first, the last users of blob_value), and no remaining task check reads a blob.

2026-10-29 (human): a PR that only deletes is not bound by the single-PR size gate; this task's pruning (AC #8) rides in its one PR.

2026-10-29 correction: the 2026-10-26 note that TASK-158 splits GOOGLE_RESOURCES is wrong. TASK-158 is superseded by TASK-111.10.3 (each Google document id has its own key; no code reader of GOOGLE_RESOURCES remains). The remaining GOOGLE_RESOURCES mentions in app/bin and app/tests are migration tooling this task prunes.

- 2026-10-29: plan approved (human) with the corrections in the plan's Review section; AC #5 reworded, AC #10 (LICENSE_KEY) removed.

2026-10-29 implemented (uncommitted, on the human's branch): terraform iam.tf reads only the /sre-bot/* ARNs; ssm.tf drops the gcp resource, TRELLO__APP_KEY, TRELLO__TOKEN and sre_bot_unread_secret_names; ecs.tf iterates sort(local.sre_bot_secret_names) (same rendered secrets list as revision 69); variables.tf drops the variable; tf_plan.yml and tf_apply.yml drop both TF_VAR lines. terraform fmt and validate pass locally; AC #3 waits on the PR's tf plan (stop if it shows any aws_ecs_task_definition change). deploy-checks: blob helpers, param_hash, same_hash and the sentinel and names_only checks deleted; new post check contract (IAM names no parameter outside /sre-bot/, the three destroyed parameters not found, rollout COMPLETED with running = desired and no stopped task with a secrets failure; blobs reported informationally). PRE_CHECKS kept empty with its validation loop (generic pre-part mechanism). env-checks: blob scan, BASELINE and git archive deleted; /sre-bot scan kept. audit_env_names.py: HINTS, SUPERSEDED, baseline, doc-14, blob and split-line parts and the rename action deleted; human decision 2026-10-29: retirement evidence is one RETIRED map (seeded with GCP_SRE_SERVICE_ACCOUNT_KEY_FILE and GOOGLE_PICKLE_STRING) so plan/apply stays live; MAXMIND_KEY never in it (test pins that no source gives it a delete verdict). audit_env_coverage.py reads env_only fields (generate_env_example.collect) and terraform/ssm.tf; config_table moved into it; new steady Codespaces rule: a codespaces-sourced env-only name no Codespaces secret provides is a check. Retired-name pins deleted across 20 test files (live-behaviour tests kept). Gates: ruff clean; mypy 41 errors, none in touched files (pre-existing); pytest tests --ignore=tests/smoke 5862 passed; contracts 13 kept; key ownership OK; bin tests 255 passed before pruning. TASK-54 AC #3 checked. decisions/configuration.md and doc-14 updated. TASK-175 created (follow-up from TASK-172, human 2026-10-29).

2026-10-29: PR #1808 tf plan: 0 to add, 1 to change (aws_iam_policy.sre-bot_secrets_manager, in place; policy document read during apply), 3 to destroy (gcp_sre_service_account_key, sre_bot_secret[TRELLO__APP_KEY], [TRELLO__TOKEN]); no aws_ecs_task_definition change, nothing replaced; only warning is the S3 module's deprecated argument (pre-existing). All PR checks green. Pre at merge 13:46Z: sre-bot-task:69, rollout COMPLETED 2/2, rollback tag df749d05f98afb45cf52e1773385130626470daa-2026-10-28; 24h baseline 3 error lines (two Socket Mode connection resets, one slack_listener_error).

2026-10-29: merged as #1808 (cd090014), tf_apply success (policy v33, three parameters destroyed), deployed on sre-bot-task:70 (build success; deploy job red from the verify bake-time race until TASK-164, sbom from the trivy-db rate limit). post contract 14:03Z: rollout, boot_errors, runtime_errors, slack_up, contract_iam (37 readable parameters, none outside /sre-bot/), contract_parameters, contract_revision (2/2, no secrets failure), version all PASS; blobs present (human console delete, deferred). Actions secrets GCP_SRE_SERVICE_ACCOUNT_KEY_FILE and GOOGLE_PICKLE_STRING deleted (human); env-checks 14:04Z lists neither in any source and plans nothing (AC #6 checked). Coverage audit's new Codespaces rule reports SLACK__SIGNING_SECRET and SLACK__USER_TOKEN missing from Codespaces (finding, for the next task touching the Slack slice or env tooling). Left for Done: AC #8g and DoD #1 (blob delete, doc-14 archive), the human's deferred steps.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-29T00:23:00Z

---

Planner proposals (2026-10-29): (1) AC #5 says drop the '/sre-bot parameter reads' but AC #8c keeps the SSM-set check, which needs them. Plan keeps the /sre-bot get-parameters-by-path scan in env-checks.zsh (steady evidence) and drops only blobs, doc-14 and the baseline; propose rewording AC #5 to 'SSM blob reads'. (2) skip_destroy is on the task definition only: removing the Trello and gcp resources from terraform destroys those parameters at tf_apply (no human delete needed for them); only the two blobs and the GitHub secrets are human steps. (3) Plan drops sentinel's post part with the check; if a Sentinel post check is still wanted before TASK-171, say so.

---
<!-- COMMENTS:END -->
