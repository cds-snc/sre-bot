locals {
  api_cloudwatch_log_group = "/ecs/sre-bot-app"
  error_logged             = "SREBotErrorLogged"
  error_namespace          = "SREBot"
  warning_logged           = "SREBotWarningLogged"

  # Case-insensitive regex for error-worthy log lines.
  # CloudWatch metric filter matching for plain text terms is case-sensitive,
  # so each letter is expanded with a character class.
  error_logged_regex_filter = "[eE][rR][rR][oO][rR]|[eE][xX][cC][eE][pP][tT][iI][oO][nN]"
  # Regex matched against the raw log line to exclude known false positives
  # from the error metric. Extend to silence new ones.
  error_logged_skip_regex_filter = "level.{0,6}warning|level.{0,6}info"
  error_logged_pattern           = "[w=%${local.error_logged_regex_filter}% && w!=%${local.error_logged_skip_regex_filter}%]"

  # Plain-text terms that indicate a warning-level log line
  warning_logged_filters = [
    "WARNING",
  ]
  # Regexes matched against the raw log line to detect a structured warning-level log line
  warning_logged_regex_filters = [
    "level.{0,6}warning", # structlog JSON renders {"level": "warning", ...} with a space after the colon; \S excludes that space
  ]
  warning_logged_pattern = "[w=\"*${join("*\" || w=\"*", local.warning_logged_filters)}*\" || ${join(" || ", [for term in local.warning_logged_regex_filters : "w=%${term}%"])}]"
}
