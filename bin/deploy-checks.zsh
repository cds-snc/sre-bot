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
#   google_ids pre: the 15 Google document id parameters compared by hash with the GOOGLE_RESOURCES paths they
#           replace (MATCH, DIFFER or MISSING, never printed); inc.d and rep.g are not carried (TASK-111.10.3)
# Output: tmp/deploy-checks/<phase>-<UTC timestamp>.txt (gitignored, never commit it)
# Rollback: docs/runbooks/roll-back-a-deployment.md, with the image_tag printed by pre.

setopt no_unset
unsetopt xtrace verbose

TASK_CHECKS=(google_ids)
PRE_CHECKS=(google_ids)  # task checks with a pre part
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

  if (( ${checks[(Ie)google_ids]} )); then  # TASK-111.10.3
    section "Google document ids against the GOOGLE_RESOURCES paths they replace (TASK-111.10.3; values never printed)"
    resources=$(blob_value GOOGLE_RESOURCES) || resources=
    [[ -n $resources ]] && print "GOOGLE_RESOURCES line: present" || print "GOOGLE_RESOURCES line: missing"
    # path_hash PATH: sha256 of one GOOGLE_RESOURCES value (a jq path such as inc.f), or 'missing'; the value never
    # leaves this function.
    path_hash() { local v; v=$(print -rn -- $resources | jq -er ".$1 // empty" 2>/dev/null) && [[ -n $v ]] && print -rn -- $v | sha256sum | cut -c1-64 || print missing; }
    google_ok=yes
    for pair in INCIDENT_CORE__FOLDER_ID:inc.f INCIDENT_CORE__REPORT_TEMPLATE_ID:inc.t \
        INCIDENT_CORE__LIST_SHEET_ID:inc.l INCIDENT_RESPONSE__HANDBOOK_ID:inc.h \
        INCIDENT_POSTMORTEM__CALENDAR_ID:cal.sre CLOUD_OPERATIONS_SPENDING__SHEET_ID:aws.s \
        TALENT__INTERNAL_FOLDER_ID:tal.i TALENT__TEMPLATES_FOLDER_ID:tal.t \
        TALENT__SCORING_GUIDE_TEMPLATE_ID:tal.s TALENT__CORE_VALUES_INTERVIEW_NOTES_ID:tal.c \
        TALENT__TECHNICAL_INTERVIEW_NOTES_ID:tal.tech TALENT__INTAKE_FORM_TEMPLATE_ID:tal.int \
        TALENT__PHONE_SCREEN_TEMPLATE_ID:tal.ph TALENT__RECRUITMENT_FEEDBACK_TEMPLATE_ID:tal.rec \
        TALENT__PANELIST_GUIDEBOOK_TEMPLATE_ID:tal.pan; do
      new=$(param_hash /sre-bot/${pair%%:*}); old=$(path_hash ${pair##*:})
      if [[ $new == missing ]]; then line="MISSING (no such parameter)"
      elif [[ $old == missing ]]; then line="MISSING (no such GOOGLE_RESOURCES path)"
      else line=$(same_hash $new $old); fi
      print "${pair%%:*} vs GOOGLE_RESOURCES ${pair##*:}: $line"
      [[ $line == MATCH ]] || google_ok=no
    done
    print "GOOGLE_RESOURCES inc.d and rep.g: not carried (no reader), not compared"
    [[ $google_ok == yes ]] && result google_ids_pre PASS || result google_ids_pre "FAIL (a DIFFER or MISSING parameter blocks the merge of the reader PR: put-parameter from the named path first)"
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

  section "HTTP (allowed paths only; /api/v1/* answers 403 at the WAF until TASK-163)"
  version=$(curl -s $BASE_URL/version)
  print "version=$version head_sha=$head_sha"
  [[ $version == *${head_sha[1,7]}* ]] && result version PASS || result version "CHECK (compare with the run's head sha)"
  print "health=$(curl -s -o /dev/null -w '%{http_code}' $BASE_URL/health) root=$(curl -s -o /dev/null -w '%{http_code}' $BASE_URL/)"
fi

print "\nwritten: $OUT"
