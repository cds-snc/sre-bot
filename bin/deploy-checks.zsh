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
#   google  pre: the three GOOGLE_WORKSPACE__TENANT__ parameters compared by hash with the values they
#           replace (MATCH or DIFFER, never printed);
#           post: Google configured on every task, no credential or delegation error (TASK-111.10.2)
#   aws     pre: the five AWS__TENANT__ and ACCESS_PERMISSION_SETS__ parameters compared by hash with the blob lines
#           they replace (MATCH, DIFFER or MISSING, never printed), the instance id and ARN checked against the
#           documented formats, any tuning line, the AWS_ names in the task definition;
#           post: no region, endpoint, credential or role error, DynamoDB-backed events present (TASK-111.11.1)
# Output: tmp/deploy-checks/<phase>-<UTC timestamp>.txt (gitignored, never commit it)
# Rollback: docs/runbooks/roll-back-a-deployment.md, with the image_tag printed by pre.

setopt no_unset
unsetopt xtrace verbose

TASK_CHECKS=(google aws)
PRE_CHECKS=(google aws)  # task checks with a pre part
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

  if (( ${checks[(Ie)google]} )); then  # TASK-111.10.2
    section "Google tenant parameters against the values they replace (TASK-111.10.2)"
    # line_hash NAME: sha256 of a blob line's value, or 'missing'; the value never leaves this function.
    line_hash() { local v; v=$(blob_value $1) && print -rn -- $v | sha256sum | cut -c1-64 || print missing; }
    customer_new=$(param_hash /sre-bot/GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID)
    customer_old=$(line_hash GOOGLE_WORKSPACE_CUSTOMER_ID)
    print "GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID vs the GOOGLE_WORKSPACE_CUSTOMER_ID line: $(same_hash $customer_new $customer_old)"
    key_new=$(param_hash /sre-bot/GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY)
    key_old=$(param_hash gcp_sre_service_account_key)
    print "GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY vs gcp_sre_service_account_key: $(same_hash $key_new $key_old)"
    delegated_new=$(param_hash /sre-bot/GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL)
    delegated_old=$(line_hash SRE_BOT_EMAIL)
    print "GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL vs the SRE_BOT_EMAIL line: $(same_hash $delegated_new $delegated_old)"
    for name in GOOGLE_DELEGATED_ADMIN_EMAIL GOOGLE_API_NUM_RETRIES GOOGLE_API_TIMEOUT_SECONDS; do
      print "$name in (unread after TASK-111.10.2; blob lines go with the blobs): $(blob_where $name)"
    done
    [[ $(same_hash $customer_new $customer_old) == MATCH && $(same_hash $key_new $key_old) == MATCH && $(same_hash $delegated_new $delegated_old) == MATCH ]] \
      && result google_pre PASS || result google_pre "FAIL (a DIFFER blocks the merge: put-parameter the right value first)"
  fi

  if (( ${checks[(Ie)aws]} )); then  # TASK-111.11.1
    section "AWS tenant and permission-set parameters against the blob lines they replace (TASK-111.11.1; values never printed)"
    # line_hash is defined in the google check above only when it ran, so define it here too.
    line_hash() { local v; v=$(blob_value $1) && print -rn -- $v | sha256sum | cut -c1-64 || print missing; }
    # compare NEW_PARAMETER OLD_BLOB_LINE: MATCH, DIFFER, or MISSING (the parameter or the blob line is absent).
    compare() {
      local new old; new=$(param_hash /sre-bot/$1); old=$(line_hash $2)
      if [[ $new == missing ]]; then print "$1 vs the $2 line: MISSING (no such parameter)"
      elif [[ $old == missing ]]; then print "$1 vs the $2 line: MISSING (no such blob line)"
      else print "$1 vs the $2 line: $(same_hash $new $old)"; fi
    }
    aws_ok=yes
    for pair in AWS__TENANT__INSTANCE_ID:AWS_SSO_INSTANCE_ID AWS__TENANT__INSTANCE_ARN:AWS_SSO_INSTANCE_ARN AWS__TENANT__ORG_ROLE_ARN:AWS_ORG_ACCOUNT_ROLE_ARN \
        AWS__TENANT__AUDIT_ROLE_ARN:AWS_AUDIT_ACCOUNT_ROLE_ARN AWS__TENANT__LOGGING_ROLE_ARN:AWS_LOGGING_ACCOUNT_ROLE_ARN \
        ACCESS_PERMISSION_SETS__SYSTEM_ADMIN_PERMISSIONS:AWS_SSO_SYSTEM_ADMIN_PERMISSIONS ACCESS_PERMISSION_SETS__VIEW_ONLY_PERMISSIONS:AWS_SSO_VIEW_ONLY_PERMISSIONS; do
      line=$(compare ${pair%%:*} ${pair##*:}); print -r -- $line
      [[ $line == *MATCH ]] || aws_ok=no
    done
    # Documented formats of the blob values (a NO would fail boot on the tenant entry): IdentityStoreId (d- and ten hex
    # digits, or a UUID) and the sso-admin InstanceArn.
    id_pattern='^(d-[0-9a-f]{10}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$'
    arn_pattern='^arn:aws(-[a-z]{1,5}){0,3}:sso:::instance/(sso)?ins-[a-zA-Z0-9.-]{16}$'
    instance_id=$(blob_value AWS_SSO_INSTANCE_ID) || instance_id=
    instance_arn=$(blob_value AWS_SSO_INSTANCE_ARN) || instance_arn=
    if [[ $instance_id =~ $id_pattern ]]; then print "AWS_SSO_INSTANCE_ID format: OK"; else print "AWS_SSO_INSTANCE_ID format: NO"; aws_ok=no; fi
    if [[ $instance_arn =~ $arn_pattern ]]; then print "AWS_SSO_INSTANCE_ARN format: OK"; else print "AWS_SSO_INSTANCE_ARN format: NO"; aws_ok=no; fi
    for name in AWS_RETRY_MAX_ATTEMPTS AWS_RETRY_MODE AWS_CONNECT_TIMEOUT_SECONDS AWS_READ_TIMEOUT_SECONDS AWS_TRANSIENT_RETRY_AFTER_SECONDS AWS_NOT_FOUND_CODES AWS_UNAUTHORIZED_CODES AWS_TRANSIENT_CODES; do
      where=$(blob_where $name)
      print "$name in (expected none; a present line needs an [aws] key in production.toml first): $where"
      [[ $where == none ]] || aws_ok=no
    done
    td_aws=$(aws ecs describe-task-definition --region $REGION --task-definition $td --output json \
      | jq -r '[.taskDefinition.containerDefinitions[0] | (.environment[]?.name), (.secrets[]?.name) | select(startswith("AWS_") and (startswith("AWS__") | not))] | join(" ")')
    print "task definition SDK names AWS_* (the slice names AWS__* excluded; expected none: ECS injects the region; if post shows NoRegionError, add AWS_DEFAULT_REGION to the task definition first): ${td_aws:-none}"
    [[ $aws_ok == yes ]] && result aws_pre PASS || result aws_pre "FAIL (a DIFFER or MISSING parameter, a format NO or a tuning line blocks the merge: put-parameter the right value first)"
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

  if (( ${checks[(Ie)google]} )); then  # TASK-111.10.2
    section "Google Workspace from the files and GOOGLE_WORKSPACE__TENANT__* (TASK-111.10.2)"
    with_google=$(li $since 'filter event = "configured_systems_built" and @message like /google/ | stats count_distinct(@logStream) as n' | jq -r '.n // 0' | head -1)
    print "tasks whose configured_systems_built lists google: ${with_google:-0} (tasks=$tasks)"
    bad=$(li_count $since 'filter event in ["google_workspace_not_configured","invalid_credentials_json"] or @message like /RefreshError|invalid_grant|unauthorized_client/')
    li $since 'filter event in ["google_workspace_not_configured","invalid_credentials_json"] or @message like /RefreshError|invalid_grant|unauthorized_client/ | fields @timestamp, event, @message | limit 10' | mask
    print "credential or delegation error lines: $bad (expected 0)"
    for name in GOOGLE_WORKSPACE_CUSTOMER_ID SRE_BOT_EMAIL GOOGLE_DELEGATED_ADMIN_EMAIL; do
      print "$name in (unread, inert until the blobs go in TASK-111.15): $(blob_where $name)"
    done
    [[ ${with_google:-0} -ge $tasks && $bad == 0 ]] && result google PASS || result google "FAIL (google on ${with_google:-0}/$tasks tasks, $bad error lines)"
  fi

  if (( ${checks[(Ie)aws]} )); then  # TASK-111.11.1
    section "AWS from the files and the SDK (TASK-111.11.1)"
    aws_filter='@message like /NoRegionError|EndpointConnectionError|InvalidClientTokenId/ or (@message like /AccessDenied/ and @message like /AssumeRole/)'
    bad=$(li_count $since "filter $aws_filter")
    li $since "filter $aws_filter | fields @timestamp, event, @message | limit 10" | mask
    print "region, endpoint, credential or AssumeRole error lines: $bad (expected 0)"
    invalid=$(li_count $since 'filter event = "configuration_invalid"')
    print "configuration_invalid lines: $invalid (expected 0)"
    dynamo=$(li_count $since 'filter event like /coordination|lease|record|status_update/')
    print "DynamoDB-backed coordination or record events since the deploy: $dynamo (expected > 0)"
    for name in AWS_SSO_INSTANCE_ID AWS_ORG_ACCOUNT_ROLE_ARN AWS_SSO_SYSTEM_ADMIN_PERMISSIONS; do
      print "$name in (unread, inert until the blobs go in TASK-111.15): $(blob_where $name)"
    done
    [[ $bad == 0 && $invalid == 0 && $dynamo -gt 0 ]] && result aws PASS || result aws "FAIL ($bad error lines, $invalid configuration_invalid, $dynamo DynamoDB-backed events)"
  fi

  section "HTTP (allowed paths only; /api/v1/* answers 403 at the WAF until TASK-163)"
  version=$(curl -s $BASE_URL/version)
  print "version=$version head_sha=$head_sha"
  [[ $version == *${head_sha[1,7]}* ]] && result version PASS || result version "CHECK (compare with the run's head sha)"
  print "health=$(curl -s -o /dev/null -w '%{http_code}' $BASE_URL/health) root=$(curl -s -o /dev/null -w '%{http_code}' $BASE_URL/)"
fi

print "\nwritten: $OUT"
