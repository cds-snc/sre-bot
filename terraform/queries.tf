resource "aws_cloudwatch_query_definition" "api_errors" {
  name = "SRE Bot Errors"

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
  name = "SRE Bot Warnings"

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

resource "aws_cloudwatch_query_definition" "scheduled_tasks_errors" {
  name = "SRE Bot Scheduled Tasks Logged"

  log_group_names = [
    local.api_cloudwatch_log_group
  ]

  query_string = <<-QUERY
    fields @timestamp, @message, @logStream
    | filter @message like /Scheduler is running at/
    | sort @timestamp desc
    | limit 20
  QUERY
}
