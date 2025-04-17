variable "billing_code" {
  description = "The billing code to tag our resources with"
  type        = string
}

variable "fargate_cpu" {
  type    = number
  default = 512
}

variable "fargate_memory" {
  type    = number
  default = 1024
}

variable "google_oauth_pickle_string" {
  description = "(Required) The Google OAuth pickle string"
  type        = string
  sensitive   = true
}

variable "gcp_sre_service_account_key" {
  description = "(Required) The GCP SRE service account key"
  type        = string
  sensitive   = true
}

variable "error_threshold" {
  description = "CloudWatch alarm threshold for the SRE Bot ERROR logs"
  type        = string
  default     = "1"
}

variable "warning_threshold" {
  description = "CloudWatch alarm threshold for the SRE Bot WARNING logs"
  type        = string
  default     = "10"
}

variable "slack_webhook_url" {
  description = "The URL of the Slack webhook."
  type        = string
  sensitive   = true
}

variable "authorized_endpoints_with_constraints" {
  description = "List of authorized endpoints with their positional constraints"
  type = list(object({
    path                  = string
    positional_constraint = string
  }))
  default = [
    { path = "/", positional_constraint = "EXACTLY" },
    { path = "/auth/login", positional_constraint = "EXACTLY" },
    { path = "/auth/logout", positional_constraint = "EXACTLY" },
    { path = "/auth/callback", positional_constraint = "EXACTLY" },
    { path = "/auth/me", positional_constraint = "EXACTLY" },
    { path = "/request_access", positional_constraint = "EXACTLY" },
    { path = "/active_requests", positional_constraint = "EXACTLY" },
    { path = "/past_requests", positional_constraint = "EXACTLY" },
    { path = "/accounts", positional_constraint = "EXACTLY" },
    { path = "/geolocate", positional_constraint = "STARTS_WITH" },
    { path = "/hook", positional_constraint = "STARTS_WITH" },
    { path = "/version", positional_constraint = "EXACTLY" },
    { path = "/static", positional_constraint = "STARTS_WITH" },
    { path = "/access", positional_constraint = "STARTS_WITH" },
    { path = "/health", positional_constraint = "EXACTLY" }
  ]
}
