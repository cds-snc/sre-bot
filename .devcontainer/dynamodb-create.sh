aws dynamodb create-table \
   --table-name webhooks \
   --attribute-definitions AttributeName=id,AttributeType=S \
   --key-schema AttributeName=id,KeyType=HASH \
   --provisioned-throughput ReadCapacityUnits=1,WriteCapacityUnits=1 \
   --endpoint-url http://dynamodb-local:8000


aws dynamodb create-table \
   --table-name aws_access_requests \
   --attribute-definitions AttributeName=account_id,AttributeType=S AttributeName=created_at,AttributeType=N \
   --key-schema AttributeName=account_id,KeyType=HASH AttributeName=created_at,KeyType=RANGE \
   --provisioned-throughput ReadCapacityUnits=1,WriteCapacityUnits=1 \
   --endpoint-url http://dynamodb-local:8000