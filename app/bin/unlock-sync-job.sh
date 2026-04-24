#!/bin/bash
#
# Force-release a stuck access sync job lock.
#
# Use this when a sync job was interrupted (e.g. server crash or restart) and
# left a "running" lock record in the idempotency store, blocking future syncs.
#
# Before running, verify there is no active sync thread still executing
# (e.g. by checking container/ECS task logs).
#

set -euo pipefail

TABLE="sre_bot_idempotency"
HASH_KEY="idempotency_key"
DEFAULT_ENDPOINT="http://dynamodb-local:8000"
ENDPOINT="${DYNAMODB_ENDPOINT:-$DEFAULT_ENDPOINT}"

show_usage() {
  cat << EOF
Usage: $0 --platform <platform> [--user-email <email>] [--dry-run] [--endpoint <url>]

Options:
  --platform    Platform key to unlock (e.g. aws)             [required]
  --user-email  Unlock the per-user lock for this email;
                omit to unlock the platform lock              [optional]
  --dry-run     Print current lock state without modifying    [optional]
  --endpoint    DynamoDB endpoint URL                         [optional]
                (default: http://dynamodb-local:8000)

Examples:
  $0 --platform aws
  $0 --platform aws --user-email alice@example.com
  $0 --platform aws --dry-run
  $0 --platform aws --endpoint http://dynamodb-local:8000

Environment:
  DYNAMODB_ENDPOINT   Override default endpoint (flag takes precedence)
  AWS_*               Standard AWS credential env vars
EOF
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

PLATFORM=""
USER_EMAIL=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --platform)    PLATFORM="$2";    shift 2 ;;
    --user-email)  USER_EMAIL="$2";  shift 2 ;;
    --dry-run)     DRY_RUN=true;     shift   ;;
    --endpoint)    ENDPOINT="$2";   shift 2 ;;
    --help|-h)     show_usage; exit 0 ;;
    *) echo "Error: unknown option '$1'"; echo ""; show_usage; exit 1 ;;
  esac
done

if [[ -z "$PLATFORM" ]]; then
  echo "Error: --platform is required"
  echo ""
  show_usage
  exit 1
fi

# ---------------------------------------------------------------------------
# Build lock key (must match platform_lock.py)
# ---------------------------------------------------------------------------

if [[ -n "$USER_EMAIL" ]]; then
  LOCK_KEY="access_sync:user_lock:${PLATFORM}:${USER_EMAIL,,}"
  TARGET_DESC="user lock  platform=${PLATFORM}  email=${USER_EMAIL}"
else
  LOCK_KEY="access_sync:platform_lock:${PLATFORM}"
  TARGET_DESC="platform lock  platform=${PLATFORM}"
fi

# ---------------------------------------------------------------------------
# DynamoDB helpers
# ---------------------------------------------------------------------------

ENDPOINT_FLAG=""
if [[ -n "$ENDPOINT" ]]; then
  ENDPOINT_FLAG="--endpoint-url ${ENDPOINT}"
fi

ddb_get() {
  aws dynamodb get-item \
    --table-name "$TABLE" \
    --key "{\"${HASH_KEY}\": {\"S\": \"$1\"}}" \
    ${ENDPOINT_FLAG} \
    --no-cli-pager 2>/dev/null
}

ddb_put() {
  # $1 = key, $2 = response_json string, $3 = ttl timestamp
  aws dynamodb put-item \
    --table-name "$TABLE" \
    --item "{
      \"${HASH_KEY}\": {\"S\": \"$1\"},
      \"response_json\": {\"S\": $2},
      \"ttl\": {\"N\": \"$3\"},
      \"created_at\": {\"N\": \"$(date +%s)\"},
      \"operation_type\": {\"S\": \"api_response\"}
    }" \
    ${ENDPOINT_FLAG} \
    --no-cli-pager
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

echo ""
echo "Target: ${TARGET_DESC}"
echo "Key:    ${LOCK_KEY}"

ITEM=$(ddb_get "$LOCK_KEY")

if [[ -z "$ITEM" ]] || [[ "$(echo "$ITEM" | jq -r '.Item // empty')" == "" ]]; then
  echo ""
  echo "No lock record found — nothing to unlock."
  exit 0
fi

# The record payload is JSON stored as a string inside response_json.S
RESPONSE_JSON=$(echo "$ITEM" | jq -r '.Item.response_json.S')
STATUS=$(echo "$RESPONSE_JSON" | jq -r '.status // "unknown"')
JOB_ID=$(echo "$RESPONSE_JSON" | jq -r '.job_id // "unknown"')
STARTED_AT=$(echo "$RESPONSE_JSON" | jq -r '.started_at // "unknown"')

echo ""
echo "Current lock:"
echo "  status     = ${STATUS}"
echo "  job_id     = ${JOB_ID}"
echo "  started_at = ${STARTED_AT}"
echo ""
echo "Full record:"
echo "$RESPONSE_JSON" | jq .

if [[ "$DRY_RUN" == true ]]; then
  echo ""
  echo "[dry-run] No changes made."
  exit 0
fi

if [[ "$STATUS" != "running" ]]; then
  echo "Lock status is '${STATUS}', not 'running' — already released or completed."
  exit 0
fi

# Patch the status in the stored JSON and write it back.
NOW_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TTL=$(( $(date +%s) + 14400 ))  # default 4 h stale window

UPDATED_JSON=$(echo "$RESPONSE_JSON" | jq \
  --arg released_at "$NOW_ISO" \
  '.status = "force_released" | .released_at = $released_at | .release_reason = "manual_unlock_script"')

# jq outputs a plain JSON string; we need it shell-escaped for the DynamoDB
# string attribute value.
ESCAPED=$(echo "$UPDATED_JSON" | jq -Rs .)

ddb_put "$LOCK_KEY" "$ESCAPED" "$TTL"

echo ""
echo "Lock force-released. Future sync jobs can now acquire the lock."
