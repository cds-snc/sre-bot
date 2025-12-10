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
  aws dynamodb describe-table \
    --table-name "$1" \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager &>/dev/null
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

# aws_access_requests table - Hash + Range key
if table_exists "aws_access_requests"; then
  echo "✓ aws_access_requests table already exists"
else
  echo "Creating aws_access_requests table..."
  aws dynamodb create-table \
    --table-name aws_access_requests \
    --attribute-definitions \
      AttributeName=account_id,AttributeType=S \
      AttributeName=created_at,AttributeType=N \
    --key-schema \
      AttributeName=account_id,KeyType=HASH \
      AttributeName=created_at,KeyType=RANGE \
    --provisioned-throughput ReadCapacityUnits=1,WriteCapacityUnits=1 \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager >/dev/null
  echo "✓ aws_access_requests table created"
fi

# sre_bot_data table - Generic PK/SK pattern
if table_exists "sre_bot_data"; then
  echo "✓ sre_bot_data table already exists"
else
  echo "Creating sre_bot_data table..."
  aws dynamodb create-table \
    --table-name sre_bot_data \
    --attribute-definitions \
      AttributeName=PK,AttributeType=S \
      AttributeName=SK,AttributeType=S \
    --key-schema \
      AttributeName=PK,KeyType=HASH \
      AttributeName=SK,KeyType=RANGE \
    --provisioned-throughput ReadCapacityUnits=2,WriteCapacityUnits=2 \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager >/dev/null
  echo "✓ sre_bot_data table created"
fi

# incidents table - Simple hash key
if table_exists "incidents"; then
  echo "✓ incidents table already exists"
else
  echo "Creating incidents table..."
  aws dynamodb create-table \
    --table-name incidents \
    --attribute-definitions AttributeName=id,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH \
    --provisioned-throughput ReadCapacityUnits=2,WriteCapacityUnits=2 \
    --endpoint-url "$ENDPOINT" \
    --no-cli-pager >/dev/null
  echo "✓ incidents table created"
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

echo ""
echo "✓ All DynamoDB tables ready for local development"
echo ""
echo "Available tables:"
aws dynamodb list-tables --endpoint-url "$ENDPOINT" --output table --no-cli-pager