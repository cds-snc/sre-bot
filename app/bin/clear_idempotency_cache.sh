#!/bin/bash

TABLE_NAME="sre_bot_idempotency"
ENDPOINT_URL="http://dynamodb-local:8000"

echo "Clearing idempotency cache from local DynamoDB..."

# Check if table exists
if ! aws dynamodb describe-table --table-name $TABLE_NAME --endpoint-url $ENDPOINT_URL --no-cli-pager &>/dev/null; then
  echo "Table $TABLE_NAME does not exist. Nothing to clear."
  exit 0
fi

# List all items and extract their keys
ITEM_KEYS=$(aws dynamodb scan --table-name $TABLE_NAME --endpoint-url $ENDPOINT_URL --query "Items[].idempotency_key.S" --output text)

# Print the number of items
ITEM_COUNT=$(echo $ITEM_KEYS | wc -w)
echo "Number of idempotency cache entries to delete: $ITEM_COUNT"

if [ $ITEM_COUNT -eq 0 ]; then
  echo "No items to delete."
  exit 0
fi

# Loop through each key and delete the item
for KEY in $ITEM_KEYS; do
  echo "Deleting cached entry: $KEY"
  aws dynamodb delete-item \
    --table-name $TABLE_NAME \
    --key "{\"idempotency_key\": {\"S\": \"$KEY\"}}" \
    --endpoint-url $ENDPOINT_URL \
    --no-cli-pager
done

echo "✓ Idempotency cache cleared successfully!"
