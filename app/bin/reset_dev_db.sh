#!/bin/bash

delete_incident_table() {
  local TABLE_NAME=$1

  # Check if table exists
  if aws dynamodb describe-table --table-name $TABLE_NAME --endpoint-url http://dynamodb-local:8000 >/dev/null 2>&1; then
    # Delete table
    aws dynamodb delete-table --table-name $TABLE_NAME --endpoint-url http://dynamodb-local:8000
  else
    echo "Table $TABLE_NAME does not exist, skipping deletion"
  fi
}

create_incident_table() {
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
      --provisioned-throughput ReadCapacityUnits=2,WriteCapacityUnits=2 \
      --endpoint-url http://dynamodb-local:8000 \
      --no-cli-pager
  fi
}


delete_incident_table "incidents"
create_incident_table "incidents"