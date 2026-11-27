variable "billing_code" {
  description = "The billing code to tag our resources with"
  type        = string
}

variable "fargate_cpu" {
  type    = number
  default = 1024
}

variable "fargate_memory" {
  type    = number
  default = 2048
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

variable "landing_page_max_query_string_bytes" {
  description = "Largest query string, in bytes, the WAF allows on the landing page before blocking the request"
  type        = number
  default     = 256
}

variable "slack_webhook_url" {
  description = "The URL of the Slack webhook."
  type        = string
  sensitive   = true
}


# On-demand DynamoDB tables are capped at these request rates (decisions/deployment.md Tables),
# a cost ceiling against unbounded traffic: past it, requests throttle instead of scaling.
variable "dynamodb_max_read_request_units" {
  description = "Highest read request units per second an on-demand DynamoDB table may serve"
  type        = number
  default     = 1000

  validation {
    condition     = var.dynamodb_max_read_request_units > 0
    error_message = "dynamodb_max_read_request_units must be positive."
  }
}

variable "dynamodb_max_write_request_units" {
  description = "Highest write request units per second an on-demand DynamoDB table may serve"
  type        = number
  default     = 1000

  validation {
    condition     = var.dynamodb_max_write_request_units > 0
    error_message = "dynamodb_max_write_request_units must be positive."
  }
}
