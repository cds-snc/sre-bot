#!/bin/bash

get_item_by_id() {
  local TABLE_NAME=$1
  local ITEM_ID=$2

  aws dynamodb get-item \
    --table-name $TABLE_NAME \
    --key "{\"id\": {\"S\": \"$ITEM_ID\"}}" \
    --endpoint-url http://dynamodb-local:8000 \
    --no-cli-pager
}

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <table_name> <item_id>"
  exit 1
fi

TABLE_NAME=$1
ITEM_ID=$2

get_item_by_id $TABLE_NAME $ITEM_ID