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

ddb_delete() {
  aws dynamodb delete-item \
    --table-name "$TABLE" \
    --key "{\"${HASH_KEY}\": {\"S\": \"$1\"}}" \
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

STATUS=$(echo "$ITEM" | jq -r '.Item.status.S // "unknown"')
CLAIMED_AT_EPOCH=$(echo "$ITEM" | jq -r '.Item.claimed_at.N // ""')
IN_PROGRESS_EXPIRES_AT=$(echo "$ITEM" | jq -r '.Item.in_progress_expires_at.N // ""')

if [[ -n "$CLAIMED_AT_EPOCH" ]]; then
  CLAIMED_AT=$(date -u -d "@${CLAIMED_AT_EPOCH}" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "${CLAIMED_AT_EPOCH}")
else
  CLAIMED_AT="unknown"
fi

if [[ -n "$IN_PROGRESS_EXPIRES_AT" ]]; then
  EXPIRES_AT=$(date -u -d "@${IN_PROGRESS_EXPIRES_AT}" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "${IN_PROGRESS_EXPIRES_AT}")
else
  EXPIRES_AT="unknown"
fi

echo ""
echo "Current lock:"
echo "  status     = ${STATUS}"
echo "  claimed_at = ${CLAIMED_AT}"
echo "  expires_at = ${EXPIRES_AT}"
echo ""
echo "Full record:"
echo "$ITEM" | jq '.Item'

if [[ "$DRY_RUN" == true ]]; then
  echo ""
  echo "[dry-run] No changes made."
  exit 0
fi

if [[ "$STATUS" != "IN_PROGRESS" ]]; then
  echo "Lock status is '${STATUS}', not 'IN_PROGRESS' — already released or completed."
  exit 0
fi

ddb_delete "$LOCK_KEY"

echo ""
echo "Lock force-released. Future sync jobs can now acquire the lock."
