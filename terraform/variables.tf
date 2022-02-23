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

# Container secrets

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