provider "aws" {
  region              = "ca-central-1"
  allowed_account_ids = ["283582579564"]
}

provider "aws" {
  alias               = "us-east-1"
  region              = "us-east-1"
  allowed_account_ids = ["283582579564"]
}


data "aws_caller_identity" "current" {}