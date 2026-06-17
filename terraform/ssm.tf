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

resource "aws_ssm_parameter" "slack_notify_mgmt_user_group_id" {
  name     = "slack_notify_mgmt_user_group_id"
  provider = aws.core_services
  type     = "SecureString"
  value    = var.slack_notify_mgmt_user_group_id

  tags = {
    CostCentre = var.billing_code
    Terraform  = true
  }
}
