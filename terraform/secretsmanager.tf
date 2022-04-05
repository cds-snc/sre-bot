resource "random_string" "random" {
  length  = 6
  special = false
  upper   = false
}

resource "aws_secretsmanager_secret" "slack_token" {
  name = "slack-token-${random_string.random.result}"
}

resource "aws_secretsmanager_secret_version" "slack_token" {
  secret_id     = aws_secretsmanager_secret.slack_token.id
  secret_string = var.slack_token
}

resource "aws_secretsmanager_secret" "app_token" {
  name = "app-token-${random_string.random.result}"
}

resource "aws_secretsmanager_secret_version" "app_token" {
  secret_id     = aws_secretsmanager_secret.app_token.id
  secret_string = var.app_token
}

resource "aws_secretsmanager_secret" "pickle_string" {
  name = "pickle-string-${random_string.random.result}"
}

resource "aws_secretsmanager_secret_version" "pickle_string" {
  secret_id     = aws_secretsmanager_secret.pickle_string.id
  secret_string = var.pickle_string
}

resource "aws_secretsmanager_secret" "opsgenie_key" {
  name = "opsgenie-key-${random_string.random.result}"
}

resource "aws_secretsmanager_secret_version" "opsgenie_key" {
  secret_id     = aws_secretsmanager_secret.opsgenie_key.id
  secret_string = var.opsgenie_key
}
