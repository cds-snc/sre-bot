resource "aws_ssm_parameter" "gcp_sre_service_account_key" {
  name     = "gcp_sre_service_account_key"
  provider = aws.core_services
  type     = "SecureString"
  value    = var.gcp_sre_service_account_key

  tags = {
    CostCentre = var.billing_code
    Terraform  = true
  }
}

