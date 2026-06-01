provider "aws" {
  region              = "ca-central-1"
  allowed_account_ids = ["283582579564"]
  default_tags {
    tags = {
      ssc_cbrid = "22DI"
    }
  }
}

provider "aws" {
  alias               = "core_services"
  region              = "ca-central-1"
  allowed_account_ids = ["283582579564"]
  default_tags {
    tags = {
      ssc_cbrid = "22DH"
    }
  }
}

provider "aws" {
  alias               = "us-east-1"
  region              = "us-east-1"
  allowed_account_ids = ["283582579564"]
  default_tags {
    tags = {
      ssc_cbrid = "22DI"
    }
  }
}

provider "aws" {
  alias               = "core_services_us-east-1"
  region              = "us-east-1"
  allowed_account_ids = ["283582579564"]
  default_tags {
    tags = {
      ssc_cbrid = "22DH"
    }
  }
}

data "aws_caller_identity" "current" {}