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