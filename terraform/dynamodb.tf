resource "aws_dynamodb_table" "webhooks_table" {
  name           = "webhooks"
  hash_key       = "id"
  billing_mode   = "PAY_PER_REQUEST"
  read_capacity  = 1
  write_capacity = 1

  attribute {
    name = "id"
    type = "S"
  }
}