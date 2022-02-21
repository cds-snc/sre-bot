resource "aws_ecr_repository" "sre-bot" {
  name                 = "sre-bot"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}