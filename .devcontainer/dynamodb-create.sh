#!/bin/bash

create_table() {
  local TABLE_NAME=$1

  # Check if table exists
  if aws dynamodb describe-table --table-name $TABLE_NAME --endpoint-url http://dynamodb-local:8000 >/dev/null 2>&1; then
    echo "Table $TABLE_NAME already exists, skipping creation"
  else
    # Create table
    aws dynamodb create-table \
      --table-name $TABLE_NAME \
      --attribute-definitions AttributeName=id,AttributeType=S \
      --key-schema AttributeName=id,KeyType=HASH \
      --provisioned-throughput ReadCapacityUnits=1,WriteCapacityUnits=1 \
      --endpoint-url http://dynamodb-local:8000 \
      --no-cli-pager
  fi
}

create_table "webhooks"
create_table "aws_access_requests"
create_table "sre_bot_data"
create_table "incidents"

# Create idempotency table with proper schema
if aws dynamodb describe-table --table-name sre_bot_idempotency --endpoint-url http://dynamodb-local:8000 >/dev/null 2>&1; then
  echo "Table sre_bot_idempotency already exists, skipping creation"
else
  aws dynamodb create-table \
    --table-name sre_bot_idempotency \
    --attribute-definitions AttributeName=idempotency_key,AttributeType=S \
    --key-schema AttributeName=idempotency_key,KeyType=HASH \
    --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --endpoint-url http://dynamodb-local:8000 \
    --no-cli-pager
fi

# Create audit trail table with proper schema and GSIs
if aws dynamodb describe-table --table-name sre_bot_audit_trail --endpoint-url http://dynamodb-local:8000 >/dev/null 2>&1; then
  echo "Table sre_bot_audit_trail already exists, skipping creation"
else
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
    --endpoint-url http://dynamodb-local:8000 \
    --no-cli-pager
fi