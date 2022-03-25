resource "aws_security_group" "sre_bot_load_balancer" {
  name        = "SRE Bot load balancer"
  description = "Ingress - SRE Bot Load Balancer"
  vpc_id      = module.vpc.vpc_id

  ingress {
    protocol    = "tcp"
    from_port   = 443
    to_port     = 443
    cidr_blocks = ["0.0.0.0/0"] #tfsec:ignore:AWS008
  }

  egress {
    protocol    = "tcp"
    from_port   = 8000
    to_port     = 8000
    cidr_blocks = ["${module.vpc.cidr_block}"] #tfsec:ignore:AWS008
  }

  tags = {
    "CostCentre" = var.billing_code
  }

}

resource "aws_security_group" "ecs_tasks" {
  name        = "sre-bot-security-group"
  description = "Allow inbound and outbout traffic for SRE Bot"
  vpc_id      = module.vpc.vpc_id

  ingress {
    protocol    = "tcp"
    from_port   = 8000
    to_port     = 8000
    cidr_blocks = ["${module.vpc.cidr_block}"]
  }

  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    "CostCentre" = var.billing_code
  }
}
