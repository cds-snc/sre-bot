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

# Container secrets for Slack

variable "slack_token" {
  description = "The slack token to use for the slack bot"
  type        = string
  sensitive   = true
}

variable "app_token" {
  description = "The app token to use for the slack bot"
  type        = string
  sensitive   = true
}

# Container secrets for Google Drive

variable "pickle_string" {
  description = "The pickle string used to access Google Drive"
  type        = string
  sensitive   = true
}

variable "sre_drive_id" {
  description = "The Google Drive ID for the SRE team drive"
  type        = string
  sensitive   = true
}

variable "sre_incident_folder" {
  description = "The Google Drive ID for the SRE incident folder"
  type        = string
  sensitive   = true
}

variable "sre_incident_template" {
  description = "The Google Drive ID for the SRE incident template"
  type        = string
  sensitive   = true
}

variable "sre_incident_list" {
  description = "The Google Drive ID for the SRE incident list"
  type        = string
  sensitive   = true
}

variable "slack_incident_channel" {
  description = "The Slack channel to post incident updates to"
  type        = string
  sensitive   = true
}
