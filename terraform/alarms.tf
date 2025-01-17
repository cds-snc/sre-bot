resource "aws_cloudwatch_log_metric_filter" "sre_bot_error" {
  name           = local.error_logged
  pattern        = "?ERROR ?Exception"
  log_group_name = local.api_cloudwatch_log_group

  metric_transformation {
    name      = local.error_logged
    namespace = local.error_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "sre_bot_error" {
  alarm_name          = "SRE Bot Errors"
  alarm_description   = "Errors logged by the SRE Bot"
  comparison_operator = "GreaterThanOrEqualToThreshold"

  metric_name        = aws_cloudwatch_log_metric_filter.sre_bot_error.metric_transformation[0].name
  namespace          = aws_cloudwatch_log_metric_filter.sre_bot_error.metric_transformation[0].namespace
  period             = "60"
  evaluation_periods = "1"
  statistic          = "Sum"
  threshold          = var.error_threshold
  treat_missing_data = "notBreaching"

  alarm_actions = [aws_sns_topic.cloudwatch_warning.arn]
  ok_actions    = [aws_sns_topic.cloudwatch_warning.arn]
}

resource "aws_cloudwatch_log_metric_filter" "sre_bot_warning" {
  name           = local.warning_logged
  pattern        = "WARNING"
  log_group_name = local.api_cloudwatch_log_group

  metric_transformation {
    name      = local.warning_logged
    namespace = local.error_namespace
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "sre_bot_warning" {
  alarm_name          = "SRE Bot Warnings"
  alarm_description   = "Warnings logged by the SRE Bot"
  comparison_operator = "GreaterThanOrEqualToThreshold"

  metric_name        = aws_cloudwatch_log_metric_filter.sre_bot_warning.metric_transformation[0].name
  namespace          = aws_cloudwatch_log_metric_filter.sre_bot_warning.metric_transformation[0].namespace
  period             = "60"
  evaluation_periods = "1"
  statistic          = "Sum"
  threshold          = var.warning_threshold
  treat_missing_data = "notBreaching"

  alarm_actions = [aws_sns_topic.cloudwatch_warning.arn]
  ok_actions    = [aws_sns_topic.cloudwatch_warning.arn]
}

resource "aws_cloudwatch_metric_alarm" "sre_bot_high_cpu" {
  alarm_name          = "SRE Bot ECS High CPU Utilization"
  alarm_description   = "ECS High CPU Utilization has been detected"
  comparison_operator = "GreaterThanOrEqualToThreshold"

  metric_name               = "CPUUtilization"
  namespace                 = "AWS/ECS"
  period                    = "60" # for 1 minute period
  evaluation_periods        = "5"
  statistic                 = "Maximum"
  threshold                 = "80" # trigger if cpu usage is above 80%
  insufficient_data_actions = []
  treat_missing_data        = "notBreaching"
  dimensions = {
    ClusterName = "sre-bot-cluster"
    ServiceName = "sre-bot-service"
  }

  alarm_actions = [aws_sns_topic.cloudwatch_warning.arn]
  ok_actions    = [aws_sns_topic.cloudwatch_warning.arn]
}

resource "aws_cloudwatch_metric_alarm" "sre_bot_high_memory" {
  alarm_name          = "SRE Bot ECS High Memory Utilization"
  alarm_description   = "ECS High Memory Utilization has been detected"
  comparison_operator = "GreaterThanOrEqualToThreshold"

  metric_name               = "MemoryUtilization"
  namespace                 = "AWS/ECS"
  period                    = "60"
  evaluation_periods        = "5"
  statistic                 = "Maximum"
  threshold                 = "80" # trigger if memory usage is > 80% for 60 seconds period. 
  insufficient_data_actions = []
  treat_missing_data        = "notBreaching"
  dimensions = {
    ClusterName = "sre-bot-cluster"
    ServiceName = "sre-bot-service"
  }

  alarm_actions = [aws_sns_topic.cloudwatch_warning.arn]
  ok_actions    = [aws_sns_topic.cloudwatch_warning.arn]
}
