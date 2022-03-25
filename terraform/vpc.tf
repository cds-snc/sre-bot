module "vpc" {
  source = "github.com/cds-snc/terraform-modules?ref=v1.0.11//vpc"
  name   = "SREBotVPC"

  allow_https_request_in           = true
  allow_https_request_in_response  = true
  allow_https_request_out          = true
  allow_https_request_out_response = true

  high_availability = true

  billing_tag_value = var.billing_code
}