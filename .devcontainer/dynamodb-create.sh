#!/bin/bash
#
# DynamoDB Local Table Creation Script
# This script creates all tables defined in terraform/dynamodb.tf for local development
# Table schemas MUST match production Terraform definitions exactly
#

ENDPOINT="http://dynamodb-local:8000"

echo "Creating DynamoDB tables for local development..."

# Helper function to check if table exists
table_exists() {
  local output
  if output=$(aws dynamodb describe-table --table-name "$1" --endpoint-url "$ENDPOINT" --no-cli-pager 2>&1); then
    return 0
  fi

  if echo "$output" | grep -q -E 'ResourceNotFoundException|Cannot do operations on a non-existent table'; then
    return 1
  fi

  echo "Warning: aws describe-table failed for '$1': $output" >&2
  return 1
}

# Helper function to check if a table has a global secondary index
gsi_exists() {
  aws dynamodb describe-table --table-name "$1" --endpoint-url "$ENDPOINT" --no-cli-pager --output json 2>/dev/null \
    | jq -e --arg index "$2" '.Table.GlobalSecondaryIndexes // [] | any(.IndexName == $index)' >/dev/null
}

# Helper function to wait until a table and one of its indexes are ACTIVE
wait_for_active() {
  local attempt status
  for attempt in $(seq 1 30); do
    status=$(aws dynamodb describe-table --table-name "$1" --endpoint-url "$ENDPOINT" --no-cli-pager --output json 2>/dev/null \
      | jq -r --arg index "$2" '[.Table.TableStatus, (.Table.GlobalSecondaryIndexes // [] | map(select(.IndexName == $index)) | .[0].IndexStatus // "MISSING")] | join(" ")')
    if [ "$status" = "ACTIVE ACTIVE" ]; then
      return 0
    fi
    sleep 1
  done
  echo "Error: table '$1' index '$2' not ACTIVE after 30s (status: $status)" >&2
  return 1
}

# Helper function to add a missing index to an existing table (one index per update-table call)
add_gsi_if_missing() {
  local table="$1" index="$2" attribute_definitions="$3" index_json="$4"
  if gsi_exists "$table" "$index"; then
    echo "✓ $table index $index already exists"
    return 0
  fi
  echo "Adding $index index to $table table..."
  # shellcheck disable=SC2086 # attribute_definitions holds several space-separated arguments
  aws dynamodb update-table \
    --table-name "$table" \
    --attribute-definitions $attribute_definitions \
    --global-secondary-index-updates "[{\"Create\":$index_json}]" \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager >/dev/null || return 1
  wait_for_active "$table" "$index" || return 1
  echo "✓ $table index $index added"
}

# webhooks table - Simple hash key
if table_exists "webhooks"; then
  echo "✓ webhooks table already exists"
else
  echo "Creating webhooks table..."
  aws dynamodb create-table \
    --table-name webhooks \
    --attribute-definitions AttributeName=id,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH \
    --provisioned-throughput ReadCapacityUnits=1,WriteCapacityUnits=1 \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager >/dev/null
  echo "✓ webhooks table created"
fi

# sre_bot_access table - Generic PK/SK pattern
if table_exists "sre_bot_access"; then
  echo "✓ sre_bot_access table already exists"
else
  echo "Creating sre_bot_access table..."
  aws dynamodb create-table \
    --table-name sre_bot_access \
    --attribute-definitions \
      AttributeName=PK,AttributeType=S \
      AttributeName=SK,AttributeType=S \
    --key-schema \
      AttributeName=PK,KeyType=HASH \
      AttributeName=SK,KeyType=RANGE \
    --provisioned-throughput ReadCapacityUnits=2,WriteCapacityUnits=2 \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager >/dev/null
  echo "✓ sre_bot_access table created"
fi

# sre_bot_access_requests table - Access Requests lifecycle records (PK/SK pattern)
if table_exists "sre_bot_access_requests"; then
  echo "✓ sre_bot_access_requests table already exists"
else
  echo "Creating sre_bot_access_requests table..."
  aws dynamodb create-table \
    --table-name sre_bot_access_requests \
    --attribute-definitions \
      AttributeName=PK,AttributeType=S \
      AttributeName=SK,AttributeType=S \
    --key-schema \
      AttributeName=PK,KeyType=HASH \
      AttributeName=SK,KeyType=RANGE \
    --provisioned-throughput ReadCapacityUnits=2,WriteCapacityUnits=2 \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager >/dev/null
  echo "✓ sre_bot_access_requests table created"
fi

# sre_bot_incident_status_updates table - One item per incident status update (PK/SK pattern)
if table_exists "sre_bot_incident_status_updates"; then
  echo "✓ sre_bot_incident_status_updates table already exists"
else
  echo "Creating sre_bot_incident_status_updates table..."
  aws dynamodb create-table \
    --table-name sre_bot_incident_status_updates \
    --attribute-definitions \
      AttributeName=PK,AttributeType=S \
      AttributeName=SK,AttributeType=S \
    --key-schema \
      AttributeName=PK,KeyType=HASH \
      AttributeName=SK,KeyType=RANGE \
    --provisioned-throughput ReadCapacityUnits=2,WriteCapacityUnits=2 \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager >/dev/null
  echo "✓ sre_bot_incident_status_updates table created"
fi

# incidents table - Simple hash key with the by_channel GSI and the sparse open GSI
INCIDENTS_BY_CHANNEL_GSI="{\"IndexName\":\"by_channel\",\"KeySchema\":[{\"AttributeName\":\"channel_id\",\"KeyType\":\"HASH\"}],\"Projection\":{\"ProjectionType\":\"ALL\"},\"ProvisionedThroughput\":{\"ReadCapacityUnits\":1,\"WriteCapacityUnits\":2}}"
INCIDENTS_OPEN_GSI="{\"IndexName\":\"open\",\"KeySchema\":[{\"AttributeName\":\"open_bucket\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"opened_at\",\"KeyType\":\"RANGE\"}],\"Projection\":{\"ProjectionType\":\"ALL\"},\"ProvisionedThroughput\":{\"ReadCapacityUnits\":1,\"WriteCapacityUnits\":2}}"
if table_exists "incidents"; then
  echo "✓ incidents table already exists"
  # Existing local tables predate the GSIs; codespaces are not rebuilt, so add what is missing.
  add_gsi_if_missing incidents by_channel \
    "AttributeName=channel_id,AttributeType=S" "$INCIDENTS_BY_CHANNEL_GSI"
  add_gsi_if_missing incidents open \
    "AttributeName=open_bucket,AttributeType=S AttributeName=opened_at,AttributeType=S" "$INCIDENTS_OPEN_GSI"
else
  echo "Creating incidents table with GSIs..."
  aws dynamodb create-table \
    --table-name incidents \
    --attribute-definitions \
      AttributeName=id,AttributeType=S \
      AttributeName=channel_id,AttributeType=S \
      AttributeName=open_bucket,AttributeType=S \
      AttributeName=opened_at,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH \
    --provisioned-throughput ReadCapacityUnits=2,WriteCapacityUnits=2 \
    --global-secondary-indexes "[$INCIDENTS_BY_CHANNEL_GSI,$INCIDENTS_OPEN_GSI]" \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager >/dev/null
  echo "✓ incidents table created"
fi

# sre_bot_incident_timeline table - One item per timeline entry, entry_key '<posted_at ISO-8601>#<entry_id>'
if table_exists "sre_bot_incident_timeline"; then
  echo "✓ sre_bot_incident_timeline table already exists"
else
  echo "Creating sre_bot_incident_timeline table..."
  aws dynamodb create-table \
    --table-name sre_bot_incident_timeline \
    --attribute-definitions \
      AttributeName=incident_id,AttributeType=S \
      AttributeName=entry_key,AttributeType=S \
    --key-schema \
      AttributeName=incident_id,KeyType=HASH \
      AttributeName=entry_key,KeyType=RANGE \
    --provisioned-throughput ReadCapacityUnits=2,WriteCapacityUnits=2 \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager >/dev/null
  echo "✓ sre_bot_incident_timeline table created"
fi

# sre_bot_idempotency table - Idempotency cache with TTL
if table_exists "sre_bot_idempotency"; then
  echo "✓ sre_bot_idempotency table already exists"
else
  echo "Creating sre_bot_idempotency table..."
  aws dynamodb create-table \
    --table-name sre_bot_idempotency \
    --attribute-definitions AttributeName=idempotency_key,AttributeType=S \
    --key-schema AttributeName=idempotency_key,KeyType=HASH \
    --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager >/dev/null
  echo "✓ sre_bot_idempotency table created"
fi

# sre_bot_audit_trail table - Complex with GSIs
if table_exists "sre_bot_audit_trail"; then
  echo "✓ sre_bot_audit_trail table already exists"
else
  echo "Creating sre_bot_audit_trail table with GSIs..."
  aws dynamodb create-table \
    --table-name sre_bot_audit_trail \
    --attribute-definitions \
      AttributeName=resource_id,AttributeType=S \
      AttributeName=timestamp_correlation_id,AttributeType=S \
      AttributeName=user_email,AttributeType=S \
      AttributeName=timestamp,AttributeType=S \
      AttributeName=correlation_id,AttributeType=S \
    --key-schema \
      AttributeName=resource_id,KeyType=HASH \
      AttributeName=timestamp_correlation_id,KeyType=RANGE \
    --provisioned-throughput ReadCapacityUnits=2,WriteCapacityUnits=2 \
    --global-secondary-indexes \
      "[{\"IndexName\":\"user_email-timestamp-index\",\"KeySchema\":[{\"AttributeName\":\"user_email\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"timestamp\",\"KeyType\":\"RANGE\"}],\"Projection\":{\"ProjectionType\":\"ALL\"},\"ProvisionedThroughput\":{\"ReadCapacityUnits\":1,\"WriteCapacityUnits\":1}},{\"IndexName\":\"correlation_id-index\",\"KeySchema\":[{\"AttributeName\":\"correlation_id\",\"KeyType\":\"HASH\"}],\"Projection\":{\"ProjectionType\":\"ALL\"},\"ProvisionedThroughput\":{\"ReadCapacityUnits\":1,\"WriteCapacityUnits\":1}}]" \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager >/dev/null
  echo "✓ sre_bot_audit_trail table created"
fi

# sre_bot_retry_records table - Distributed retry system with TTL and GSI
if table_exists "sre_bot_retry_records"; then
  echo "✓ sre_bot_retry_records table already exists"
else
  echo "Creating sre_bot_retry_records table..."
  aws dynamodb create-table \
    --table-name sre_bot_retry_records \
    --attribute-definitions \
      AttributeName=record_id,AttributeType=S \
      AttributeName=status,AttributeType=S \
      AttributeName=next_retry_at,AttributeType=N \
    --key-schema \
      AttributeName=record_id,KeyType=HASH \
    --provisioned-throughput ReadCapacityUnits=2,WriteCapacityUnits=2 \
    --global-secondary-indexes \
      "[{\"IndexName\":\"status-next_retry_at-index\",\"KeySchema\":[{\"AttributeName\":\"status\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"next_retry_at\",\"KeyType\":\"RANGE\"}],\"Projection\":{\"ProjectionType\":\"ALL\"},\"ProvisionedThroughput\":{\"ReadCapacityUnits\":2,\"WriteCapacityUnits\":2}}]" \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager >/dev/null
  echo "✓ sre_bot_retry_records table created"
fi

echo ""
echo "✓ All DynamoDB tables ready for local development"
echo ""
echo "Available tables:"
aws dynamodb list-tables --endpoint-url "$ENDPOINT" --output table --no-cli-pager