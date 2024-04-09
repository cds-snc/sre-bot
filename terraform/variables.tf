variable "billing_code" {
  description = "The billing code to tag our resources with"
  type        = string
}

variable "fargate_cpu" {
  type    = number
  default = 256
}

variable "fargate_memory" {
  type    = number
  default = 512
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
