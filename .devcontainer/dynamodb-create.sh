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