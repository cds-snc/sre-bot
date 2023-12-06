resource "aws_ecs_cluster" "sre-bot" {
  name = "sre-bot-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

data "template_file" "sre-bot" {
  template = file("./templates/sre-bot.json.tpl")

  vars = {
    awslogs-group         = aws_cloudwatch_log_group.sre-bot_group.name
    awslogs-region        = "ca-central-1"
    awslogs-stream-prefix = "ecs-sre-bot"
    image                 = "${aws_ecr_repository.sre-bot.repository_url}:latest"
    fargate_cpu           = var.fargate_cpu
    fargate_memory        = var.fargate_memory
    aws_region            = "ca-central-1"
    PICKLE_STRING         = aws_ssm_parameter.google_oauth_pickle_string.arn
  }
}

resource "aws_ecs_task_definition" "sre-bot" {
  family                   = "sre-bot-task"
  execution_role_arn       = aws_iam_role.sre-bot.arn
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.fargate_cpu
  memory                   = var.fargate_memory
  container_definitions    = data.template_file.sre-bot.rendered
  task_role_arn            = aws_iam_role.sre-bot.arn
}

resource "aws_ecs_service" "main" {
  name             = "sre-bot-service"
  cluster          = aws_ecs_cluster.sre-bot.id
  task_definition  = aws_ecs_task_definition.sre-bot.arn
  desired_count    = 1
  launch_type      = "FARGATE"
  platform_version = "1.4.0"
  propagate_tags   = "SERVICE"

  network_configuration {
    security_groups  = [aws_security_group.ecs_tasks.id]
    subnets          = module.vpc.private_subnet_ids
    assign_public_ip = false
  }

  depends_on = [
    aws_lb_listener.sre_bot_listener,
    aws_iam_role_policy_attachment.ecs_task_execution
  ]

  load_balancer {
    target_group_arn = aws_lb_target_group.sre_bot.arn
    container_name   = "sre-bot"
    container_port   = 8000
  }

  tags = {
    "CostCentre" = var.billing_code
  }
}

resource "aws_cloudwatch_log_group" "sre-bot_group" {
  name              = "/ecs/sre-bot-app"
  retention_in_days = 30

  tags = {
    Name = "sre-bot-log-group"
  }
}

resource "aws_cloudwatch_log_stream" "sre-bot_stream" {
  name           = "sre-bot-log-stream"
  log_group_name = aws_cloudwatch_log_group.sre-bot_group.name
}
