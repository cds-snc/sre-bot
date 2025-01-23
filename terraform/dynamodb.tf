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

resource "aws_dynamodb_table" "sre_bot_data" {
  name           = "sre_bot_data"
  hash_key       = "PK"
  range_key      = "SK"
  read_capacity  = 2
  write_capacity = 2

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }
}


resource "aws_dynamodb_table" "incidents_table" {
  name           = "incidents"
  hash_key       = "id"
  read_capacity  = 1
  write_capacity = 1

  attribute {
    name = "id"
    type = "S"
  }
}
