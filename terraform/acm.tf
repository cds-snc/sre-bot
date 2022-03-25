resource "aws_acm_certificate" "sre_bot" {
  domain_name               = "sre-bot.cdssandbox.xyz"
  subject_alternative_names = ["*.sre-bot.cdssandbox.xyz"]
  validation_method         = "DNS"

  tags = {
    "CostCentre" = var.billing_code
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "sre_bot_certificate_validation" {
  zone_id = aws_route53_zone.sre_bot.zone_id

  for_each = {
    for dvo in aws_acm_certificate.sre_bot.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  type            = each.value.type

  ttl = 60
}

resource "aws_acm_certificate_validation" "sre_bot" {
  certificate_arn         = aws_acm_certificate.sre_bot.arn
  validation_record_fqdns = [for record in aws_route53_record.sre_bot_certificate_validation : record.fqdn]
}