#!/usr/bin/env zsh
# Production deploy checks: a baseline before a merge and verification after its deploy. Read-only:
# describe, get and Logs Insights queries only; no write, registration, update-service or workflow dispatch.
# Never prints a secret: values stay in local variables and are compared in-process; log samples are masked.
# Developer helper for the configuration migration and plugin work, not part of the app.
#
# Usage (from any directory; needs AWS read credentials and gh auth):
#   zsh bin/deploy-checks.zsh pre               # before a merge: rollback image tag, task definition, 24h baseline
#   zsh bin/deploy-checks.zsh post [CHECK ...]  # after the deploy: run, rollout, boot errors, Slack up, HTTP,
#                                               # plus each named task check
# Task checks (each belongs to a task; delete it once that task is Done):
#   plugins    [plugins.<area>] enablement and the retired ACCESS_*_ENABLED names (TASK-112.2, TASK-112.3)
# Output: tmp/deploy-checks/<phase>-<UTC timestamp>.txt (gitignored, never commit it)
# Rollback: docs/runbooks/roll-back-a-deployment.md, with the image_tag printed by pre.

setopt no_unset
unsetopt xtrace verbose

TASK_CHECKS=(plugins)
phase=${1:-}
[[ $phase == pre || $phase == post ]] || { print -u2 "usage: $0 pre | post [${(j:|:)TASK_CHECKS} ...]"; exit 2 }
shift
checks=("$@")
for c in $checks; do (( ${TASK_CHECKS[(Ie)$c]} )) || { print -u2 "unknown check '$c'; known: $TASK_CHECKS"; exit 2 }; done
[[ $phase == pre && ${#checks} -gt 0 ]] && { print -u2 "task checks run with post only"; exit 2 }

ROOT=$(git -C ${0:A:h} rev-parse --show-toplevel)
REGION=ca-central-1
CLUSTER=sre-bot-cluster
SERVICE=sre-bot-service
LOG_GROUP=/ecs/sre-bot-app
BLOBS=(sre-bot-config sre-bot-config-infrastructure)  # entry.sh order: both, concatenated into .env
BASE_URL=https://sre-bot.cdssandbox.xyz
OUT_DIR=$ROOT/tmp/deploy-checks
OUT=$OUT_DIR/$phase${checks:+-${(j:-:)checks}}-$(date -u +%Y%m%dT%H%M%SZ).txt
mkdir -p $OUT_DIR
exec > >(tee $OUT) 2>&1

section() { print "\n== $1 =="; }
result() { print "RESULT $1: $2"; }
mask() { sed -E "s/(xox[abpersu]-|xapp-)[A-Za-z0-9-]+/\1***/g; s/input_value=('[^']*'|\"[^\"]*\"|[^,} ]*)/input_value=***/g" | cut -c1-200; }

# Logs Insights: li <epoch start> <query>; prints the rows as compact JSON objects.
li() {
  local start=$1 query=$2 qid qstate
  qid=$(aws logs start-query --region $REGION --log-group-name $LOG_GROUP \
    --start-time $start --end-time $(date -u +%s) --query-string "$query" --output text --query queryId)
  for _ in {1..30}; do
    qstate=$(aws logs get-query-results --region $REGION --query-id $qid --query status --output text)
    [[ $qstate == Complete || $qstate == Failed || $qstate == Cancelled ]] && break
    sleep 2
  done
  [[ $qstate == Complete ]] || { print "query $qstate"; return 0; }
  aws logs get-query-results --region $REGION --query-id $qid --output json \
    | jq -c '.results[] | map({(.field): .value}) | add | del(."@ptr")'
}
li_count() { local v; v=$(li $1 "$2 | stats count() as n" | jq -r '.n // empty' | head -1); print -r -- ${v:-0}; }

# blob_where NAME: which blob(s) hold a NAME line (names only).
blob_where() { local b w=(); for b in $BLOBS; do aws ssm get-parameter --region $REGION --name $b --with-decryption --query Parameter.Value --output text | tr -d '\r' | grep -qE "^[[:space:]]*$1[[:space:]]*=" && w+=$b; done; print -r -- "${w:-none}"; }
primary_deployment() {
  aws ecs describe-services --region $REGION --cluster $CLUSTER --services $SERVICE --output json \
    | jq -c '.services[0].deployments[] | select(.status=="PRIMARY") | {taskDefinition, rolloutState, runningCount, desiredCount, createdAt}'
}

print "phase=$phase checks=${checks:-none} run_at=$(date -u +%FT%TZ)"

section "ECS service and image (rollback target in pre)"
dep=$(primary_deployment); print -r -- $dep
td=$(print -r -- $dep | jq -r .taskDefinition)
image=$(aws ecs describe-task-definition --region $REGION --task-definition $td --query 'taskDefinition.containerDefinitions[0].image' --output text)
print "task_definition=$td"
print "image=$image"
if [[ $image == *@sha256:* ]]; then
  digest=${image##*@}
  print "image_digest=$digest"
  print "image_tag=$(aws ecr describe-images --region $REGION --repository-name sre-bot --image-ids imageDigest=$digest --query 'imageDetails[0].imageTags' --output text)  (rollback: image_tag input of build_and_deploy)"
else
  print "image_tag=${image##*:}"
fi

section "Task definition names only"
aws ecs describe-task-definition --region $REGION --task-definition $td --output json \
  | jq -c '.taskDefinition.containerDefinitions[0] | {secrets: [.secrets[]?.name] | sort, environment: [.environment[]?.name] | sort}'

if [[ $phase == pre ]]; then
  section "Baseline, last 24h"
  since=$(( $(date -u +%s) - 86400 ))
  print "slack_app_initialized: $(li_count $since 'filter event = "slack_app_initialized"')"
  print "error or critical lines: $(li_count $since 'filter level in ["error","critical"]')"
  li $since 'filter event = "configured_systems_built" | fields @timestamp, @message | sort @timestamp desc | limit 3'
fi

if [[ $phase == post ]]; then
  section "Deploy run (judge build and deploy jobs; sbom may fail on the trivy-db rate limit)"
  run=$(gh run list --repo cds-snc/sre-bot --workflow build_and_deploy.yml --branch main --limit 1 --json databaseId,headSha,status,conclusion,createdAt)
  print -r -- $run
  gh run view --repo cds-snc/sre-bot $(print -r -- $run | jq -r '.[0].databaseId') --json jobs --jq '.jobs[] | "\(.name): \(.conclusion)"'
  head_sha=$(print -r -- $run | jq -r '.[0].headSha')

  section "Rollout"
  rollout=$(print -r -- $dep | jq -r .rolloutState)
  [[ $rollout == COMPLETED ]] && result rollout PASS || result rollout "FAIL ($rollout)"
  since=$(print -r -- $dep | jq -r '.createdAt | if type=="number" then floor else (sub("\\.[0-9]+";"") | sub("[+-][0-9:]+$";"Z") | fromdateiso8601) end')
  print "window_start=$(date -u -d @$since +%FT%TZ)"

  section "Boot errors since the deploy (event names, masked samples)"
  n=$(li_count $since 'filter level in ["error","critical"] or @message like /ValidationError|ConfigurationError|Traceback|configuration files not loaded/')
  li $since 'filter level in ["error","critical"] or @message like /ValidationError|ConfigurationError|Traceback/ | fields @timestamp, event, level, @message | limit 10' | mask
  [[ $n == 0 ]] && result boot_errors PASS || result boot_errors "FAIL ($n lines)"

  section "Non-JSON lines since the deploy (uvicorn lines expected until TASK-28.2)"
  print "count=$(li_count $since 'filter @message not like /^\s*\{/')"
  li $since 'filter @message not like /^\s*\{/ | fields @message | limit 15' | mask

  tasks=$(print -r -- $dep | jq -r .runningCount)

  section "Slack up"
  print "slack_app_initialized: $(li_count $since 'filter event = "slack_app_initialized"')"
  print "socket session established: $(li_count $since 'filter @message like /session has been established/')"
  li $since 'filter event = "configured_systems_built" | fields @timestamp, @message | limit 4'
  bad=$(li_count $since 'filter event in ["slack_disabled_skipping_init","slack_app_initialization_failed","slack_provider_app_unavailable","incident_comms_registration_skipped"] or @message like /missing_bot_token|missing_app_token|invalid_auth|not_authed/')
  [[ $bad == 0 ]] && result slack_up PASS || result slack_up "FAIL ($bad lines; rerun the samples above)"

  if (( ${checks[(Ie)plugins]} )); then  # TASK-112.2, TASK-112.3
    section "Plugin enablement from [plugins.<area>] (TASK-112.2)"
    li $since 'filter event = "feature_plugins_loaded" | fields @timestamp, plugins, disabled | limit 4'
    loaded=$(li_count $since 'filter event = "feature_plugins_loaded" and @message like /"disabled": ?\["access.catalog", ?"access.request", ?"access.sync"\]/ and @message like /"plugins": ?\["geolocate", ?"incident.comms", ?"incident.scribe", ?"oncall_sync", ?"rant", ?"user_rotations"\]/')
    print "feature_plugins_loaded with the six plugins and access disabled: $loaded (tasks=$tasks)"
    print "no_plugin_entry_points or enablement errors: $(li_count $since 'filter @message like /no_plugin_entry_points|has no enablement key|names no installed entry point/')"
    print "access log lines since the deploy (expected 0, the plugins are not imported): $(li_count $since 'filter logger like /packages.access/')"
    [[ $loaded -ge $tasks ]] && result plugins PASS || result plugins "FAIL (loaded=$loaded tasks=$tasks; read the plugins and disabled fields above)"
    for n in ACCESS_SYNC_ENABLED ACCESS_REQUESTS_ENABLED ACCESS_CATALOG_ENABLED; do print "$n in (unread since TASK-112.3): $(blob_where $n)"; done
  fi

  section "HTTP (allowed paths only; /api/v1/* answers 403 at the WAF until TASK-163)"
  version=$(curl -s $BASE_URL/version)
  print "version=$version head_sha=$head_sha"
  [[ $version == *${head_sha[1,7]}* ]] && result version PASS || result version "CHECK (compare with the run's head sha)"
  print "health=$(curl -s -o /dev/null -w '%{http_code}' $BASE_URL/health) root=$(curl -s -o /dev/null -w '%{http_code}' $BASE_URL/)"
fi

print "\nwritten: $OUT"
