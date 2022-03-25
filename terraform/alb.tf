resource "aws_lb_target_group" "sre_bot" {
  name                 = "sre-bot"
  port                 = 8000
  protocol             = "HTTP"
  target_type          = "ip"
  deregistration_delay = 30
  vpc_id               = module.vpc.vpc_id

  health_check {
    enabled             = true
    interval            = 10
    path                = "/version"
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }

  tags = {
    "CostCentre" = var.billing_code
  }
}

resource "aws_lb_listener" "sre_bot_listener" {
  depends_on = [
    aws_acm_certificate.sre_bot,
    aws_route53_record.sre_bot_certificate_validation,
    aws_acm_certificate_validation.sre_bot,
  ]

  load_balancer_arn = aws_lb.sre_bot.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-FS-1-2-Res-2020-10"
  certificate_arn   = aws_acm_certificate.sre_bot.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.sre_bot.arn
  }
}

resource "aws_lb" "sre_bot" {

  name               = "sre-bot"
  internal           = false #tfsec:ignore:AWS005
  load_balancer_type = "application"

  security_groups = [
    aws_security_group.sre_bot_load_balancer.id
  ]

  subnets = module.vpc.public_subnet_ids

  tags = {
    "CostCentre" = var.billing_code
  }
}