resource "aws_cloudwatch_query_definition" "api_errors" {
  name     = "SRE Bot Errors"
  provider = aws.core_services
  log_group_names = [
    local.api_cloudwatch_log_group
  ]

  query_string = <<-QUERY
    fields @timestamp, @message, @logStream
    | filter @message like /(?i)ERROR|FAILED/
    | sort @timestamp desc
    | limit 20
  QUERY
}

resource "aws_cloudwatch_query_definition" "api_warnings" {
  name     = "SRE Bot Warnings"
  provider = aws.core_services
  log_group_names = [
    local.api_cloudwatch_log_group
  ]

  query_string = <<-QUERY
    fields @timestamp, @message, @logStream
    | filter @message like /WARNING/
    | sort @timestamp desc
    | limit 20
  QUERY
}

resource "aws_cloudwatch_query_definition" "waf_probes" {
  name     = "SRE Bot WAF Probes"
  provider = aws.core_services
  log_group_names = [
    aws_cloudwatch_log_group.sre_bot_waf_log_group.name
  ]

  query_string = <<-QUERY
    fields @timestamp, httpRequest.clientIp, httpRequest.country, httpRequest.httpMethod, httpRequest.uri, strlen(httpRequest.args) as argLen, action, terminatingRuleId, ja4Fingerprint
    | filter action = "BLOCK" or argLen > ${var.landing_page_max_query_string_bytes} or httpRequest.args like /%22|%27|%3C/
    | sort @timestamp desc
    | limit 200
  QUERY
}
