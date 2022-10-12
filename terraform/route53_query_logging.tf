resource "aws_cloudwatch_log_group" "sre_bot_dns" {
  provider = aws.us-east-1

  name              = "/aws/route53/${aws_route53_zone.sre_bot.name}"
  retention_in_days = 30
}


data "aws_iam_policy_document" "route53_query_logging_policy" {
  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["arn:aws:logs:*:*:log-group:/aws/route53/*"]

    principals {
      identifiers = ["route53.amazonaws.com"]
      type        = "Service"
    }
  }
}

resource "aws_cloudwatch_log_resource_policy" "route53_query_logging_policy" {
  provider = aws.us-east-1

  policy_document = data.aws_iam_policy_document.route53-query-logging-policy.json
  policy_name     = "route53-query-logging-policy"
}

resource "aws_route53_query_log" "sre_bot_dns" {
  depends_on = [aws_cloudwatch_log_resource_policy.route53_query_logging_policy]

  cloudwatch_log_group_arn = aws_cloudwatch_log_group.sre_bot_dns.arn
  zone_id                  = aws_route53_zone.sre_bot_dns.zone_id
}
