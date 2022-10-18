variable "secret" {
  description = "This is a secret"
  type        = string
  sensitive   = true
}


resource "aws_iam_role" "sre_bot" {
  name               = "test_role-${var.secret}"
  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "${var.secret}"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
}
