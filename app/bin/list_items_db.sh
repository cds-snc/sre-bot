#!/bin/bash

list_items() {
  local TABLE_NAME=$1

  aws dynamodb scan \
    --table-name $TABLE_NAME \
    --endpoint-url http://dynamodb-local:8000 \
    --no-cli-pager
}

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <table_name>"
  exit 1
fi

TABLE_NAME=$1

list_items $TABLE_NAME