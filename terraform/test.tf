variable "secret" {
  description = "This is a secret"
  type        = string
  sensitive   = true
}


data "aws_iam_policy_document" "test_role" {
  statement {
    sid     = "AssumeRole"
    actions = ["sts:AssumeRole"]
    principals {
      type = "AWS"
      identifiers = [
        var.secret
      ]
    }
  }
}

resource "aws_iam_role" "sre_bot" {
  name               = "test_role-${var.secret}"
  assume_role_policy = data.aws_iam_policy_document.test_role.json
}
