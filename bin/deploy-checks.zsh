#!/usr/bin/env zsh
# Production deploy checks: a baseline before a merge and verification after its deploy. Read-only:
# describe, get and Logs Insights queries only; no write, registration, update-service or workflow dispatch.
# Never prints a secret: values stay in local variables and are compared in-process; log samples are masked.
# Developer helper for the configuration migration and plugin work, not part of the app.
#
# Usage (from any directory; needs AWS read credentials and gh auth):
#   zsh bin/deploy-checks.zsh pre [CHECK ...]   # before a merge: rollback image tag, task definition, 24h baseline,
#                                               # plus the pre part of each named task check that has one
#   zsh bin/deploy-checks.zsh post [CHECK ...]  # after the deploy: run, rollout, boot errors, runtime errors,
#                                               # Slack up, HTTP, plus each named task check
# Task checks (each belongs to a task; delete it once that task is Done):
#   vendors pre: the six Notify, Opsgenie and Trello parameters compared by hash with the blob lines they replace
#           (MATCH, DIFFER or MISSING, never printed), the NOTIFY_API_URL line (public) against production.toml's
#           [notify.tenant] api_url, any MAXMIND_DB_PATH or Opsgenie host line;
#           post: no configuration_invalid naming a vendor, no not-configured line, the Opsgenie and MaxMind
#           healthchecks healthy (TASK-111.12)
#   features pre: the five Slack id lines (public identifiers, printed) beside production.toml's [incident],
#           [sre_ops] and [atip] keys, MATCH or DIFFER; AWS_ADMIN_GROUPS and AWS_OPS_GROUP_NAME expected in no blob (production
#           ran on the code default the file now holds); post: no configuration_invalid naming incident, sre_ops or
#           cloud_operations; the startup message in the ops channel is a manual Slack check (TASK-111.14)
# Output: tmp/deploy-checks/<phase>-<UTC timestamp>.txt (gitignored, never commit it)
# Rollback: docs/runbooks/roll-back-a-deployment.md, with the image_tag printed by pre.

setopt no_unset
unsetopt xtrace verbose

TASK_CHECKS=(vendors features)
PRE_CHECKS=(vendors features)  # task checks with a pre part
phase=${1:-}
[[ $phase == pre || $phase == post ]] || { print -u2 "usage: $0 pre | post [${(j:|:)TASK_CHECKS} ...]"; exit 2 }
shift
checks=("$@")
for c in $checks; do (( ${TASK_CHECKS[(Ie)$c]} )) || { print -u2 "unknown check '$c'; known: $TASK_CHECKS"; exit 2 }; done
if [[ $phase == pre ]]; then
  for c in $checks; do (( ${PRE_CHECKS[(Ie)$c]} )) || { print -u2 "check '$c' has no pre part; pre parts: $PRE_CHECKS"; exit 2 }; done
fi

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

# Logs Insights: li <epoch start> <query> [epoch end, default now]; prints the rows as compact JSON objects.
li() {
  local start=$1 query=$2 end=${3:-$(date -u +%s)} qid qstate
  qid=$(aws logs start-query --region $REGION --log-group-name $LOG_GROUP \
    --start-time $start --end-time $end --query-string "$query" --output text --query queryId)
  for _ in {1..30}; do
    qstate=$(aws logs get-query-results --region $REGION --query-id $qid --query status --output text)
    [[ $qstate == Complete || $qstate == Failed || $qstate == Cancelled ]] && break
    sleep 2
  done
  [[ $qstate == Complete ]] || { print "query $qstate"; return 0; }
  aws logs get-query-results --region $REGION --query-id $qid --output json \
    | jq -c '.results[] | map({(.field): .value}) | add | del(."@ptr")'
}
li_count() { local v; v=$(li $1 "$2 | stats count() as n" ${3:-} | jq -r '.n // empty' | head -1); print -r -- ${v:-0}; }

# blob_where NAME: which blob(s) hold a NAME line (names only).
blob_where() { local b w=(); for b in $BLOBS; do aws ssm get-parameter --region $REGION --name $b --with-decryption --query Parameter.Value --output text | tr -d '\r' | grep -qE "^[[:space:]]*$1[[:space:]]*=" && w+=$b; done; print -r -- "${w:-none}"; }
# blob_value NAME: the value of a NAME line in the first blob holding it, quotes and spaces trimmed. Callers keep it
# in a local variable and never print it unless it is meant for the files.
blob_value() {
  local b line
  for b in $BLOBS; do
    line=$(aws ssm get-parameter --region $REGION --name $b --with-decryption --query Parameter.Value --output text \
      | tr -d '\r' | grep -E "^[[:space:]]*$1[[:space:]]*=" | tail -1)
    [[ -n $line ]] && { print -rn -- ${line#*=} | sed -E "s/^[[:space:]]+|[[:space:]]+\$//g; s/^[\"'](.*)[\"']\$/\1/"; return 0; }
  done
  return 1
}
# param_hash NAME: sha256 of a SecureString parameter's value, or 'missing'.
param_hash() {
  local v
  v=$(aws ssm get-parameter --region $REGION --name $1 --with-decryption --query Parameter.Value --output text 2>/dev/null) || { print missing; return; }
  print -rn -- $v | sha256sum | cut -c1-64
}
same_hash() { [[ $1 != missing && $1 == $2 ]] && print MATCH || print DIFFER; }
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

  if (( ${checks[(Ie)vendors]} )); then  # TASK-111.12
    section "Notify, Opsgenie and Trello parameters against the blob lines they replace (TASK-111.12; values never printed)"
    # line_hash NAME: sha256 of a blob line's value, or 'missing'; the value never leaves this function.
    line_hash() { local v; v=$(blob_value $1) && print -rn -- $v | sha256sum | cut -c1-64 || print missing; }
    vendors_ok=yes
    for pair in NOTIFY__SRE_USER_NAME:NOTIFY_SRE_USER_NAME NOTIFY__SRE_CLIENT_SECRET:NOTIFY_SRE_CLIENT_SECRET \
        OPSGENIE__INTEGRATIONS_KEY:OPSGENIE_INTEGRATIONS_KEY TRELLO__TENANT__APP_KEY:TRELLO_APP_KEY \
        TRELLO__TENANT__TOKEN:TRELLO_TOKEN TRELLO__ATIP_BOARD:TRELLO_ATIP_BOARD; do
      new=$(param_hash /sre-bot/${pair%%:*}); old=$(line_hash ${pair##*:})
      if [[ $new == missing ]]; then line="MISSING (no such parameter)"
      elif [[ $old == missing ]]; then line="MISSING (no such blob line)"
      else line=$(same_hash $new $old); fi
      print "${pair%%:*} vs the ${pair##*:} line: $line"
      [[ $line == MATCH ]] || vendors_ok=no
    done
    # The Notify API host is public: print the blob's and compare it with the file's.
    url_blob=$(blob_value NOTIFY_API_URL) || url_blob=
    url_file=$(sed -n '/^\[notify\.tenant\]/,/^\[/p' $ROOT/app/config/production.toml | sed -nE 's/^api_url = "(.*)"/\1/p')
    print "NOTIFY_API_URL line: ${url_blob:-missing}; production.toml [notify.tenant] api_url: ${url_file:-missing}"
    [[ -n $url_blob && ${url_blob%/} == ${url_file%/} ]] && print "Notify API host: MATCH" || { print "Notify API host: DIFFER (set production.toml to the blob's value first)"; vendors_ok=no; }
    for name in MAXMIND_DB_PATH OPSGENIE_API_URL; do
      where=$(blob_where $name)
      print "$name in (expected none; production.toml names the entry): $where"
      [[ $where == none ]] || vendors_ok=no
    done
    [[ $vendors_ok == yes ]] && result vendors_pre PASS || result vendors_pre "FAIL (a DIFFER or MISSING parameter, a host DIFFER or an override line blocks the merge: put-parameter or fix the file first)"
  fi

  if (( ${checks[(Ie)features]} )); then  # TASK-111.14
    section "Incident, SRE ops and ATIP ids against production.toml (TASK-111.14; Slack ids are public identifiers, printed)"
    # file_value TABLE KEY: a quoted string key of one table in production.toml.
    file_value() { sed -n "/^\[$1\]/,/^\[/p" $ROOT/app/config/production.toml | sed -nE "s/^$2 = \"(.*)\"/\1/p"; }
    features_ok=yes
    for triple in INCIDENT_CHANNEL:incident:incident_channel \
        SLACK_SECURITY_USER_GROUP_ID:incident:slack_security_user_group_id \
        SLACK_NOTIFY_MGMT_USER_GROUP_ID:incident:slack_notify_mgmt_user_group_id \
        SRE_OPS_CHANNEL_ID:sre_ops:sre_ops_channel_id \
        ATIP_ANNOUNCE_CHANNEL:atip:announce_channel_id; do
      name=${triple%%:*}; rest=${triple#*:}; table=${rest%%:*}; key=${rest#*:}
      old=$(blob_value $name) || old=missing
      new=$(file_value $table $key); new=${new:-missing}
      [[ $old != missing && $old == $new ]] && line=MATCH || { line=DIFFER; features_ok=no; }
      print "$name line: $old; production.toml [$table] $key: $new; $line"
    done
    for name in AWS_ADMIN_GROUPS AWS_OPS_GROUP_NAME; do
      where=$(blob_where $name)
      print "$name in (expected none; production ran on the code default): $where"
      [[ $where == none ]] || features_ok=no
    done
    print "production.toml [cloud_operations]: $(sed -n '/^\[cloud_operations\]/,/^\[/p' $ROOT/app/config/production.toml | grep -E '^aws_admin_groups' || print missing)"
    for name in GROUP_DOMAIN GROUP_PROVIDERS; do
      print "$name in (unread, inert until the blobs go in TASK-111.15): $(blob_where $name)"
    done
    [[ $features_ok == yes ]] && result features_pre PASS || result features_pre "FAIL (copy each DIFFER line's blob value into production.toml; an AWS_* line means production overrode the default: stop and replan)"
  fi
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

  # Boot ends 5 minutes after the last configured_systems_built (10 minutes after the rollout started if none).
  booted=$(li $since 'filter event = "configured_systems_built" | stats max(toMillis(@timestamp)) as t' | jq -r '.t // empty' | head -1)
  if [[ -n $booted ]]; then boot_end=$(( ${booted%%.*} / 1000 + 300 )); else boot_end=$(( since + 600 )); fi
  now=$(date -u +%s); (( boot_end > now )) && boot_end=$now

  section "Boot errors, rollout to $(date -u -d @$boot_end +%FT%TZ) (event names, masked samples)"
  n=$(li_count $since 'filter level in ["error","critical"] or @message like /ValidationError|ConfigurationError|Traceback|configuration files not loaded/' $boot_end)
  li $since 'filter level in ["error","critical"] or @message like /ValidationError|ConfigurationError|Traceback|configuration files not loaded/ | fields @timestamp, event, level, @message | limit 10' $boot_end | mask
  [[ $n == 0 ]] && result boot_errors PASS || result boot_errors "FAIL ($n lines)"

  section "Runtime errors after boot (a Socket Mode reconnect followed by a new session on the same task is WARN)"
  other=$(li_count $boot_end 'filter (level in ["error","critical"] or @message like /Traceback/) and @message not like /on_error invoked/')
  li $boot_end 'filter (level in ["error","critical"] or @message like /Traceback/) and @message not like /on_error invoked/ | fields @timestamp, @logStream, event, level, @message | limit 10' | mask
  # Per task (one log stream each): the last Socket Mode on_error and the last session established.
  errors=$(li $boot_end 'filter @message like /on_error invoked/ | stats max(toMillis(@timestamp)) as t, count() as n by @logStream')
  sessions=$(li $boot_end 'filter @message like /session has been established/ | stats max(toMillis(@timestamp)) as t by @logStream')
  reconnected=0 lost=0
  for row in ${(f)errors}; do
    stream=$(print -r -- $row | jq -r '."@logStream"')
    error_at=$(print -r -- $row | jq -r '.t | tonumber | floor')
    session_at=$(print -r -- $sessions | jq -r --arg s $stream 'select(."@logStream" == $s) | .t | tonumber | floor' | head -1)
    if [[ -n $session_at ]] && (( session_at > error_at )); then
      (( reconnected++ )); print "reconnected: $stream ($(print -r -- $row | jq -r .n) on_error, last at $(date -u -d @$(( error_at / 1000 )) +%FT%TZ))"
    else
      (( lost++ )); print "no session after the last on_error: $stream"
    fi
  done
  print "other runtime error lines: $other; Socket Mode reconnects: $reconnected; tasks without a session after on_error: $lost"
  if (( other > 0 || lost > 0 )); then result runtime_errors "FAIL (other=$other lost=$lost)"
  elif (( reconnected > 0 )); then result runtime_errors "WARN (Socket Mode reconnected on $reconnected task(s))"
  else result runtime_errors PASS; fi

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

  if (( ${checks[(Ie)vendors]} )); then  # TASK-111.12
    section "Notify, Trello, Opsgenie and MaxMind from the files and their secrets (TASK-111.12)"
    invalid=$(li_count $since 'filter event = "configuration_invalid" and @message like /notify|trello|opsgenie|maxmind|NOTIFY__|TRELLO__|OPSGENIE__|MAXMIND__/')
    print "configuration_invalid lines naming a vendor: $invalid (expected 0)"
    unconfigured=$(li_count $since 'filter event in ["revoke_api_key_not_configured","opsgenie_not_configured","maxmind_not_configured"]')
    li $since 'filter event in ["revoke_api_key_not_configured","opsgenie_not_configured","maxmind_not_configured"] | fields @timestamp, event | limit 5'
    print "not-configured lines: $unconfigured (expected 0)"
    li $since 'filter event = "integration_healthcheck_result" and integration in ["opsgenie","maxmind"] | stats count() as n by integration, result'
    unhealthy=$(li_count $since 'filter event = "integration_healthcheck_result" and integration in ["opsgenie","maxmind"] and result = "unhealthy"')
    healthy=$(li_count $since 'filter event = "integration_healthcheck_result" and integration in ["opsgenie","maxmind"] and result = "healthy"')
    print "opsgenie and maxmind healthchecks: $healthy healthy, $unhealthy unhealthy (expected > 0 and 0; they run every 5 minutes)"
    for name in NOTIFY_SRE_CLIENT_SECRET OPSGENIE_INTEGRATIONS_KEY TRELLO_TOKEN; do
      print "$name in (unread, inert until the blobs go in TASK-111.15): $(blob_where $name)"
    done
    [[ $invalid == 0 && $unconfigured == 0 && $unhealthy == 0 && $healthy -gt 0 ]] && result vendors PASS || result vendors "FAIL ($invalid configuration_invalid, $unconfigured not configured, $unhealthy unhealthy, $healthy healthy)"
  fi

  if (( ${checks[(Ie)features]} )); then  # TASK-111.14
    section "Incident, SRE ops and cloud operations slices from the files (TASK-111.14)"
    invalid=$(li_count $since 'filter event = "configuration_invalid" and @message like /incident|sre_ops|cloud_operations|atip|INCIDENT__|SRE_OPS__|CLOUD_OPERATIONS__|ATIP__/')
    print "configuration_invalid lines naming incident, sre_ops or cloud_operations: $invalid (expected 0)"
    print "Manual: the 'SRE Bot has started up' message arrived in the ops channel; an sre-ifs member's /aws groups list is answered"
    [[ $invalid == 0 ]] && result features PASS || result features "FAIL ($invalid configuration_invalid)"
  fi

  section "HTTP (allowed paths only; /api/v1/* answers 403 at the WAF until TASK-163)"
  version=$(curl -s $BASE_URL/version)
  print "version=$version head_sha=$head_sha"
  [[ $version == *${head_sha[1,7]}* ]] && result version PASS || result version "CHECK (compare with the run's head sha)"
  print "health=$(curl -s -o /dev/null -w '%{http_code}' $BASE_URL/health) root=$(curl -s -o /dev/null -w '%{http_code}' $BASE_URL/)"
fi

print "\nwritten: $OUT"
