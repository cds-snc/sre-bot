module "sre_bot_bucket" {
  source      = "github.com/cds-snc/terraform-modules//S3?ref=v9.5.0"
  bucket_name = "sre-bot-bucket"
  versioning = {
    enabled = true
  }

  billing_tag_key   = "CostCentre"
  billing_tag_value = var.billing_code
}
