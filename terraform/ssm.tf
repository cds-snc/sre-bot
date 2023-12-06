resource "aws_ssm_parameter" "google_oauth_pickle_string" {
  name  = "google_oauth_pickle_string"
  type  = "SecureString"
  value = var.google_oauth_pickle_string

  tags = {
    CostCentre = var.billing_code
    Terraform  = true
  }
}