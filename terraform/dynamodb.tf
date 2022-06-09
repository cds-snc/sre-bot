resource "aws_dynamodb_table" "webhooks_table" {
  name           = "webhooks"
  hash_key       = "id"
  read_capacity  = 1
  write_capacity = 1

  attribute {
    name = "id"
    type = "S"
  }
}

resource "aws_dynamodb_table" "aws_access_requests_table" {
  name           = "aws_access_requests"
  hash_key       = "account_id"
  range_key      = "created_at"
  read_capacity  = 1
  write_capacity = 1

  attribute {
    name = "account_id"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "N"
  }
}