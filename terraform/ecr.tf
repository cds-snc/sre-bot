resource "aws_ecr_repository" "sre-bot" {
  name = "sre-bot"
  # <sha>-<date> tags are immutable; latest stays a movable pointer (decisions/deployment.md).
  image_tag_mutability = "IMMUTABLE_WITH_EXCLUSION"

  image_tag_mutability_exclusion_filter {
    filter      = "latest"
    filter_type = "WILDCARD"
  }

  image_scanning_configuration {
    scan_on_push = true
  }
}
