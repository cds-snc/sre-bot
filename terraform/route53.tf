resource "aws_route53_zone" "sre_bot" {
  name = "sre-bot.cdssandbox.xyz"

  tags = {
    "CostCentre" = var.billing_code
  }
}

resource "aws_route53_record" "sre_bot" {
  zone_id = aws_route53_zone.sre_bot.zone_id
  name    = aws_route53_zone.sre_bot.name
  type    = "A"

  alias {
    name                   = aws_lb.sre_bot.dns_name
    zone_id                = aws_lb.sre_bot.zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_health_check" "sre_bot_healthcheck" {
  fqdn              = aws_route53_zone.sre_bot.name
  port              = 443
  type              = "HTTPS"
  resource_path     = "/version"
  failure_threshold = "3"
  request_interval  = "30"

  tags = {
    "CostCentre" = var.billing_code
  }
}