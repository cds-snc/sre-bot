locals {
  api_cloudwatch_log_group = "/ecs/sre-bot-app"
  error_logged             = "SREBotErrorLogged"
  error_namespace          = "SREBot"
  warning_logged           = "SREBotWarningLogged"

  # Plain-text terms that indicate an error-worthy log line
  error_logged_filters = [
    "ERROR",
    "Exception",
  ]
  # Regexes (CloudWatch %...% syntax, no literal quotes allowed) matched against the raw log
  # line to exclude known false positives from the error metric. Extend to silence new ones.
  error_logged_skip_filters = [
    "level\\S*warning", # structlog logs at level=warning, e.g. {"level": "warning", ...}
  ]
  error_logged_pattern = "[(w=\"*${join("*\" || w=\"*", local.error_logged_filters)}*\") && ${join(" && ", [for term in local.error_logged_skip_filters : "w!=%${term}%"])}]"

  # Plain-text terms that indicate a warning-level log line
  warning_logged_filters = [
    "WARNING",
  ]
  # Regexes matched against the raw log line to detect a structured warning-level log line
  warning_logged_regex_filters = [
    "level\\S*warning", # structlog logs at level=warning, e.g. {"level": "warning", ...}
  ]
  warning_logged_pattern = "[w=\"*${join("*\" || w=\"*", local.warning_logged_filters)}*\" || ${join(" || ", [for term in local.warning_logged_regex_filters : "w=%${term}%"])}]"
}
