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

# Secrets the app reads under their <SLICE>__<FIELD> names (doc-14 rename map).
# Values are set outside terraform with put-parameter --overwrite; value_wo is
# write-only, so terraform never reads a value into state. Never bump
# value_wo_version: that writes the placeholder over the real value.
locals {
  sre_bot_secret_names = toset([
    "GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY",
    "NOTIFY__SRE_CLIENT_SECRET",
    "NOTIFY__SRE_USER_NAME",
    "OPENAI__API_KEY",
    "OPSGENIE__INTEGRATIONS_KEY",
    "SENTINEL__SHARED_KEY",
    "SLACK__APP_TOKEN",
    "SLACK__BOT_TOKEN",
    "SLACK__USER_TOKEN",
    "TRELLO__APP_KEY",
    "TRELLO__TOKEN",
  ])
}

resource "aws_ssm_parameter" "sre_bot_secret" {
  for_each         = local.sre_bot_secret_names
  name             = "/sre-bot/${each.value}"
  provider         = aws.core_services
  type             = "SecureString"
  value_wo         = "set-outside-terraform"
  value_wo_version = 1

  tags = {
    CostCentre = var.billing_code
    Terraform  = true
  }
}
