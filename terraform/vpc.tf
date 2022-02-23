module "vpc" {
  source = "github.com/cds-snc/terraform-modules?ref=v1.0.11//vpc"
  name   = "SREBotVPC"

  allow_https_request_out          = true
  allow_https_request_out_response = true

  billing_tag_value = var.billing_code
}