module "vpc" {
  source = "github.com/cds-snc/terraform-modules//vpc?ref=v10.10.2"
  name   = "SREBotVPC"

  allow_https_request_in           = true
  allow_https_request_in_response  = true
  allow_https_request_out          = true
  allow_https_request_out_response = true

  availability_zones = 3
  cidrsubnet_newbits = 8

  billing_tag_value = var.billing_code
}
