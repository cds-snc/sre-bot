locals {
  geodb_name = "geodb_refresh_role"
}

module "gh_oidc_roles" {
  source   = "github.com/cds-snc/terraform-modules//gh_oidc_role?ref=v7.0.2"
  org_name = "cds-snc"
  roles = [
    {
      name      = local.geodb_name
      repo_name = "sre-bot"
      claim     = "ref:refs/heads/main"
    }
  ]

  billing_tag_value = var.billing_code

}

data "aws_iam_policy_document" "publish_techdocs" {
  statement {
    effect = "Allow"

    actions = [
      "s3:ListBucket",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:DeleteObjectVersion",
      "s3:GetObject",
    ]

    resources = [
      "${module.sre_bot_bucket.s3_bucket_arn}/*",
      "${module.sre_bot_bucket.s3_bucket_arn}"
    ]
  }
}

resource "aws_iam_role_policy" "geodb_refresh_policy" {
  name   = "geodb_refresh_policy"
  role   = module.gh_oidc_roles.roles[local.geodb_name].role_name
  policy = data.aws_iam_policy_document.publish_techdocs.json
}
