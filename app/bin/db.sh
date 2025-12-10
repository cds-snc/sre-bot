#!/bin/bash
#
# DynamoDB Local CLI - Single interface for all DynamoDB operations
# Auto-detects table schemas and adapts to any key structure
#

ENDPOINT="http://dynamodb-local:8000"

show_usage() {
  cat << EOF
DynamoDB Local CLI - Manage local DynamoDB tables

Usage: $0 <command> [args]

Commands:
  list                              List all tables
  scan <table>                      Show all items in table
  get <table> <hash> [range]        Get specific item
  delete <table> <hash> [range]     Delete specific item  
  clear <table>                     Delete all items from table
  reset <table>                     Drop and recreate table

Examples:
  $0 list
  $0 scan incidents
  $0 get webhooks "hook-123"
  $0 get aws_access_requests "12345" "1234567890"
  $0 delete incidents "inc-001"
  $0 clear sre_bot_idempotency
  $0 reset incidents

Note: All operations auto-detect table key schemas
EOF
}

get_table_keys() {
  aws dynamodb describe-table \
    --table-name "$1" \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager 2>/dev/null | \
    jq -r '.Table.KeySchema | map({(.KeyType): .AttributeName}) | add'
}

cmd_list() {
  echo "DynamoDB Local Tables:"
  aws dynamodb list-tables \
    --endpoint-url "$ENDPOINT" \
    --output table \
    --no-cli-pager
}

cmd_scan() {
  local table=$1
  if [ -z "$table" ]; then
    echo "Error: Table name required"
    echo "Usage: $0 scan <table>"
    exit 1
  fi
  
  aws dynamodb scan \
    --table-name "$table" \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager
}

cmd_get() {
  local table=$1
  local hash_value=$2
  local range_value=$3
  
  if [ -z "$table" ] || [ -z "$hash_value" ]; then
    echo "Error: Table name and hash key value required"
    echo "Usage: $0 get <table> <hash_value> [range_value]"
    exit 1
  fi
  
  local keys=$(get_table_keys "$table")
  local hash_key=$(echo "$keys" | jq -r '.HASH')
  local range_key=$(echo "$keys" | jq -r '.RANGE // empty')
  
  if [ -z "$hash_key" ]; then
    echo "Error: Could not determine key schema for table $table"
    exit 1
  fi
  
  if [ -n "$range_key" ] && [ -n "$range_value" ]; then
    local key="{\"$hash_key\": {\"S\": \"$hash_value\"}, \"$range_key\": {\"S\": \"$range_value\"}}"
  else
    local key="{\"$hash_key\": {\"S\": \"$hash_value\"}}"
  fi
  
  aws dynamodb get-item \
    --table-name "$table" \
    --key "$key" \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager
}

cmd_delete() {
  local table=$1
  local hash_value=$2
  local range_value=$3
  
  if [ -z "$table" ] || [ -z "$hash_value" ]; then
    echo "Error: Table name and hash key value required"
    echo "Usage: $0 delete <table> <hash_value> [range_value]"
    exit 1
  fi
  
  local keys=$(get_table_keys "$table")
  local hash_key=$(echo "$keys" | jq -r '.HASH')
  local range_key=$(echo "$keys" | jq -r '.RANGE // empty')
  
  if [ -z "$hash_key" ]; then
    echo "Error: Could not determine key schema for table $table"
    exit 1
  fi
  
  if [ -n "$range_key" ] && [ -n "$range_value" ]; then
    local key="{\"$hash_key\": {\"S\": \"$hash_value\"}, \"$range_key\": {\"S\": \"$range_value\"}}"
  else
    local key="{\"$hash_key\": {\"S\": \"$hash_value\"}}"
  fi
  
  echo "Deleting item from $table..."
  aws dynamodb delete-item \
    --table-name "$table" \
    --key "$key" \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager
  
  echo "✓ Item deleted"
}

cmd_clear() {
  local table=$1
  
  if [ -z "$table" ]; then
    echo "Error: Table name required"
    echo "Usage: $0 clear <table>"
    exit 1
  fi
  
  echo "Clearing all items from table: $table"
  
  local keys=$(get_table_keys "$table")
  local hash_key=$(echo "$keys" | jq -r '.HASH')
  local range_key=$(echo "$keys" | jq -r '.RANGE // empty')
  
  if [ -z "$hash_key" ]; then
    echo "Error: Could not determine key schema for table $table"
    exit 1
  fi
  
  # Scan for all items
  if [ -n "$range_key" ]; then
    local items=$(aws dynamodb scan \
      --table-name "$table" \
      --endpoint-url "$ENDPOINT" \
      --no-cli-pager 2>/dev/null | \
      jq -r ".Items[] | {h: .$hash_key.S, r: .$range_key.S} | @json")
  else
    local items=$(aws dynamodb scan \
      --table-name "$table" \
      --endpoint-url "$ENDPOINT" \
      --no-cli-pager 2>/dev/null | \
      jq -r ".Items[] | .$hash_key.S")
  fi
  
  local count=$(echo "$items" | wc -l | tr -d ' ')
  
  if [ -z "$items" ] || [ "$count" -eq 0 ]; then
    echo "Table is already empty"
    return 0
  fi
  
  echo "Deleting $count items..."
  
  while IFS= read -r item; do
    if [ -n "$range_key" ]; then
      local hash_val=$(echo "$item" | jq -r '.h')
      local range_val=$(echo "$item" | jq -r '.r')
      local key="{\"$hash_key\": {\"S\": \"$hash_val\"}, \"$range_key\": {\"S\": \"$range_val\"}}"
    else
      local key="{\"$hash_key\": {\"S\": \"$item\"}}"
    fi
    
    aws dynamodb delete-item \
      --table-name "$table" \
      --key "$key" \
      --endpoint-url "$ENDPOINT" \
      --no-cli-pager 2>/dev/null
  done <<< "$items"
  
  echo "✓ Cleared $count items from $table"
}

cmd_reset() {
  local table=$1
  
  if [ -z "$table" ]; then
    echo "Error: Table name required"
    echo "Usage: $0 reset <table>"
    exit 1
  fi
  
  echo "Resetting table: $table"
  echo "This will delete and recreate the table"
  read -p "Are you sure? (y/N) " -n 1 -r
  echo
  
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled"
    exit 1
  fi
  
  echo "Deleting table..."
  aws dynamodb delete-table \
    --table-name "$table" \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager 2>/dev/null
  
  sleep 2
  
  echo "Recreating table..."
  /workspace/.devcontainer/dynamodb-create.sh
  
  echo "✓ Table reset complete"
}

# Main command router
case "${1:-help}" in
  list)
    cmd_list
    ;;
  scan)
    cmd_scan "$2"
    ;;
  get)
    cmd_get "$2" "$3" "$4"
    ;;
  delete)
    cmd_delete "$2" "$3" "$4"
    ;;
  clear)
    cmd_clear "$2"
    ;;
  reset)
    cmd_reset "$2"
    ;;
  help|--help|-h|"")
    show_usage
    ;;
  *)
    echo "Error: Unknown command '$1'"
    echo ""
    show_usage
    exit 1
    ;;
esac
