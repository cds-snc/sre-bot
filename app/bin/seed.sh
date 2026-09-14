#!/bin/bash
#
# DynamoDB Local Seeding Tool - Create test data for local development
# Helps developers create realistic entries for testing features that require pre-existing data
#

ENDPOINT="http://dynamodb-local:8000"

show_usage() {
  cat << EOF
DynamoDB Local Seeding Tool - Create test data

Usage: $0 <entity> [options]

Entities:
  webhook <channel_id> <user_id> <name> [hook_type]
      Create a webhook entry
      Example: $0 webhook C12345 U67890 "Alert Webhook" alert

  incident <channel_id> <channel_name> <name> <user_id> [status]
      Create an incident entry
      Example: $0 incident C12345 "inc-api-down" "API Down" U67890 Open

Examples:
  # Create a webhook for testing alert routing
  $0 webhook C0123456789 U9876543210 "Production Alerts" alert

  # Create an incident for testing incident commands
  $0 incident C1111111111 "inc-db-outage" "Database Outage" U2222222222 Open

Notes:
  - All IDs are auto-generated (UUIDs)
  - Timestamps default to current time
  - Created entries can be viewed with: ./bin/db.sh scan <table>
  - Clean up test data with: ./bin/db.sh clear <table>
EOF
}

seed_webhook() {
  local channel="$1"
  local user_id="$2"
  local name="$3"
  local hook_type="${4:-alert}"
  
  if [ -z "$channel" ] || [ -z "$user_id" ] || [ -z "$name" ]; then
    echo "Error: webhook requires <channel_id> <user_id> <name>"
    exit 1
  fi
  
  local id=$(cat /proc/sys/kernel/random/uuid)
  local created_at=$(date -u +"%Y-%m-%d %H:%M:%S.%6N")
  
  aws dynamodb put-item \
    --table-name webhooks \
    --endpoint-url "$ENDPOINT" \
    --item "{
      \"id\": {\"S\": \"$id\"},
      \"channel\": {\"S\": \"$channel\"},
      \"user_id\": {\"S\": \"$user_id\"},
      \"name\": {\"S\": \"$name\"},
      \"hook_type\": {\"S\": \"$hook_type\"},
      \"created_at\": {\"S\": \"$created_at\"},
      \"active\": {\"BOOL\": true},
      \"invocation_count\": {\"N\": \"0\"},
      \"acknowledged_count\": {\"N\": \"0\"}
    }" \
    --no-cli-pager >/dev/null
  
  if [ $? -eq 0 ]; then
    echo "✓ Webhook created:"
    echo "  ID: $id"
    echo "  Channel: $channel"
    echo "  Name: $name"
    echo "  Type: $hook_type"
  else
    echo "✗ Failed to create webhook"
    exit 1
  fi
}

seed_incident() {
  local channel_id="$1"
  local channel_name="$2"
  local name="$3"
  local user_id="$4"
  local status="${5:-Open}"
  
  if [ -z "$channel_id" ] || [ -z "$channel_name" ] || [ -z "$name" ] || [ -z "$user_id" ]; then
    echo "Error: incident requires <channel_id> <channel_name> <name> <user_id>"
    exit 1
  fi
  
  local id=$(cat /proc/sys/kernel/random/uuid)
  local created_at=$(date +%s)
  local report_url="https://docs.google.com/document/d/test-$id"
  
  aws dynamodb put-item \
    --table-name incidents \
    --endpoint-url "$ENDPOINT" \
    --item "{
      \"id\": {\"S\": \"$id\"},
      \"channel_id\": {\"S\": \"$channel_id\"},
      \"channel_name\": {\"S\": \"$channel_name\"},
      \"name\": {\"S\": \"$name\"},
      \"user_id\": {\"S\": \"$user_id\"},
      \"status\": {\"S\": \"$status\"},
      \"created_at\": {\"S\": \"$created_at\"},
      \"report_url\": {\"S\": \"$report_url\"},
      \"teams\": {\"L\": []},
      \"logs\": {\"L\": []},
      \"start_impact_time\": {\"S\": \"Unknown\"},
      \"end_impact_time\": {\"S\": \"Unknown\"},
      \"detection_time\": {\"S\": \"Unknown\"},
      \"environment\": {\"S\": \"prod\"}
    }" \
    --no-cli-pager >/dev/null
  
  if [ $? -eq 0 ]; then
    echo "✓ Incident created:"
    echo "  ID: $id"
    echo "  Channel: $channel_name ($channel_id)"
    echo "  Name: $name"
    echo "  Status: $status"
    echo "  Report: $report_url"
  else
    echo "✗ Failed to create incident"
    exit 1
  fi
}

# Main command router
if [ $# -lt 1 ]; then
  show_usage
  exit 1
fi

case "$1" in
  webhook)
    shift
    seed_webhook "$@"
    ;;
  incident)
    shift
    seed_incident "$@"
    ;;
  -h|--help|help)
    show_usage
    ;;
  *)
    echo "Error: Unknown entity '$1'"
    echo ""
    show_usage
    exit 1
    ;;
esac
