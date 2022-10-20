data "aws_iam_policy_document" "sre-bot" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "sre-bot_secrets_manager" {
  statement {
    effect = "Allow"
    actions = [
      "sts:AssumeRole",
    ]
    resources = [
      "arn:aws:iam::659087519042:role/sre_bot_role"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "ssm:GetParameters",
    ]
    resources = [
      "arn:aws:ssm:ca-central-1:${data.aws_caller_identity.current.account_id}:parameter/sre-bot-config"
    ]
  }

  statement {
    effect = "Allow"

    actions = [
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem"
    ]

    resources = [
      aws_dynamodb_table.aws_access_requests_table.arn,
      aws_dynamodb_table.webhooks_table.arn,
    ]

  }
}

resource "aws_iam_policy" "sre-bot_secrets_manager" {
  name   = "sre-botSecretsManagerKeyRetrieval"
  path   = "/"
  policy = data.aws_iam_policy_document.sre-bot_secrets_manager.json
}

resource "aws_iam_role" "sre-bot" {
  name = "sre-bot-ecs-role"

  assume_role_policy = data.aws_iam_policy_document.sre-bot.json

  tags = {
    "CostCentre" = var.billing_code
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.sre-bot.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy_attachment" "secrets_manager" {
  role       = aws_iam_role.sre-bot.name
  policy_arn = aws_iam_policy.sre-bot_secrets_manager.arn
}
