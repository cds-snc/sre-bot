#!/bin/bash

add_webhook() {
  local TABLE_NAME=$1
  local CHANNEL=$2
  local USER_ID=$3
  local NAME=$4
  local HOOK_TYPE=${5:-"alert"}
  local CREATED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  local ID=$(date +%s%N | sha256sum | head -c 32) # Generate a unique ID

  aws dynamodb put-item \
    --table-name $TABLE_NAME \
    --item "{\"id\": {\"S\": \"$ID\"}, \"channel\": {\"S\": \"$CHANNEL\"}, \"name\": {\"S\": \"$NAME\"}, \"created_at\": {\"S\": \"$CREATED_AT\"}, \"active\": {\"BOOL\": true}, \"user_id\": {\"S\": \"$USER_ID\"}, \"invocation_count\": {\"N\": \"0\"}, \"acknowledged_count\": {\"N\": \"0\"}, \"hook_type\": {\"S\": \"$HOOK_TYPE\"}}" \
    --endpoint-url http://dynamodb-local:8000 \
    --no-cli-pager

  if [ $? -eq 0 ]; then
    echo "Webhook added with ID: $ID"
  else
    echo "Failed to add webhook"
  fi
}

if [ "$#" -lt 4 ]; then
  echo "Usage: $0 <table_name> <channel> <user_id> <name> [hook_type]"
  exit 1
fi

TABLE_NAME=$1
CHANNEL=$2
USER_ID=$3
NAME=$4
HOOK_TYPE=$5

add_webhook $TABLE_NAME $CHANNEL $USER_ID $NAME $HOOK_TYPE