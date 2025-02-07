#!/bin/bash

TABLE_NAME="incidents"
ENDPOINT_URL="http://dynamodb-local:8000"

# List all items and extract their keys
ITEM_KEYS=$(aws dynamodb scan --table-name $TABLE_NAME --endpoint-url $ENDPOINT_URL --query "Items[].id.S" --output text)

# Print the number of items
ITEM_COUNT=$(echo $ITEM_KEYS | wc -w)
echo "Number of items to delete: $ITEM_COUNT"

# Loop through each key and delete the item
for KEY in $ITEM_KEYS; do
  echo "Deleting item with key $KEY"
  aws dynamodb delete-item \
    --table-name $TABLE_NAME \
    --key "{\"id\": {\"S\": \"$KEY\"}}" \
    --endpoint-url $ENDPOINT_URL \
    --no-cli-pager
done