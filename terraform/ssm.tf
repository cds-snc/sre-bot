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

# Secrets and non-public values (decisions/configuration.md) the app reads under
# their <SLICE>__<FIELD> names (doc-14 rename map).
# Values are set outside terraform with put-parameter --overwrite; value_wo is
# write-only, so terraform never reads a value into state. Never bump
# value_wo_version: that writes the placeholder over the real value.
locals {
  sre_bot_secret_names = toset([
    "ACCESS_PERMISSION_SETS__SYSTEM_ADMIN_PERMISSIONS",
    "ACCESS_PERMISSION_SETS__VIEW_ONLY_PERMISSIONS",
    "AWS__TENANT__AUDIT_ROLE_ARN",
    "AWS__TENANT__INSTANCE_ARN",
    "AWS__TENANT__INSTANCE_ID",
    "AWS__TENANT__LOGGING_ROLE_ARN",
    "AWS__TENANT__ORG_ROLE_ARN",
    "CLOUD_OPERATIONS_SPENDING__SHEET_ID",
    "GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID",
    "GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL",
    "GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY",
    "INCIDENT_CORE__FOLDER_ID",
    "INCIDENT_CORE__LIST_SHEET_ID",
    "INCIDENT_CORE__REPORT_TEMPLATE_ID",
    "INCIDENT_POSTMORTEM__CALENDAR_ID",
    "INCIDENT_RESPONSE__HANDBOOK_ID",
    "NOTIFY__SRE_CLIENT_SECRET",
    "NOTIFY__SRE_USER_NAME",
    "OPENAI__API_KEY",
    "OPSGENIE__INTEGRATIONS_KEY",
    "SENTINEL__CUSTOMER_ID",
    "SENTINEL__SHARED_KEY",
    "SLACK__APP_TOKEN",
    "SLACK__BOT_TOKEN",
    "SLACK__USER_TOKEN",
    "TALENT__CORE_VALUES_INTERVIEW_NOTES_ID",
    "TALENT__INTAKE_FORM_TEMPLATE_ID",
    "TALENT__INTERNAL_FOLDER_ID",
    "TALENT__PANELIST_GUIDEBOOK_TEMPLATE_ID",
    "TALENT__PHONE_SCREEN_TEMPLATE_ID",
    "TALENT__RECRUITMENT_FEEDBACK_TEMPLATE_ID",
    "TALENT__SCORING_GUIDE_TEMPLATE_ID",
    "TALENT__TECHNICAL_INTERVIEW_NOTES_ID",
    "TALENT__TEMPLATES_FOLDER_ID",
    "TRELLO__APP_KEY",
    "TRELLO__ATIP_BOARD",
    "TRELLO__TENANT__APP_KEY",
    "TRELLO__TENANT__TOKEN",
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
