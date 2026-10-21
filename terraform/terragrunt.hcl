terraform {
  source = "."
}

locals {
  billing_code = "sre-bot"
}

# DO NOT CHANGE ANYTHING BELOW HERE UNLESS YOU KNOW WHAT YOU ARE DOING

inputs = {
  billing_code = local.billing_code
}

remote_state {
  backend = "s3"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
  config = {
    encrypt             = true
    bucket              = "${local.billing_code}-tf"
    dynamodb_table      = "terraform-state-lock-dynamo"
    region              = "ca-central-1"
    # The object terraform 1.5 wrote as "./terraform.tfstate": its AWS SDK v1
    # stripped the "./", which terraform 1.6+ sends as-is (hashicorp/terraform#34279).
    key                 = "terraform.tfstate"
    s3_bucket_tags      = { CostCenter : local.billing_code }
    dynamodb_table_tags = { CostCenter : local.billing_code }
  }
}