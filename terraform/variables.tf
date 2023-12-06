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