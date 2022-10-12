resource "aws_cloudwatch_log_group" "sre_bot_dns" {
  name              = "/aws/route53/sre_bot_vpc"
  retention_in_days = 30
}


data "aws_iam_policy_document" "route53_resolver_logging_policy" {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["arn:aws:logs:ca-central-1:283582579564:log-group:/aws/route53/*"]

    principals {
      identifiers = ["route53.amazonaws.com"]
      type        = "Service"
    }
  }
}

resource "aws_cloudwatch_log_resource_policy" "route53_resolver_logging_policy" {
  policy_document = data.aws_iam_policy_document.route53_resolver_logging_policy.json
  policy_name     = "route53_resolver_logging_policy"
}

resource "aws_route53_resolver_query_log_config" "sre_bot" {
  name            = "sre_bot"
  destination_arn = aws_cloudwatch_log_group.sre_bot_dns.arn
}

resource "aws_route53_resolver_query_log_config_association" "sre_bot" {
  resolver_query_log_config_id = aws_route53_resolver_query_log_config.sre_bot.id
  resource_id                  = module.vpc.id
}
