resource "aws_wafv3_web_acl" "sre-bot"
{
    name        = "sre-bot"
    scope       = "REGIONAL"
    description = "WAF Web ACL for SRE Bot"
    default_action {
        allow {}
    }
    rule {
    name     = "APIRatesEvaluation"
    priority = 0

    action {
      count {}
    }

    statement {
      rate_based_statement {
        limit               = 5000
        aggregate_key_type  = "CONSTANT"

        scope_down_statement {
          byte_match_statement {
            search_string         = "/"
            field_to_match {
              uri_path {}
            }
            text_transformation {
              priority = 0
              type     = "NONE"
            }
            positional_constraint = "STARTS_WITH"
          }
        }
      }
    }
     visibility_config {
      sampled_requests_enabled    = true
      cloudwatch_metrics_enabled  = true
      metric_name                 = "APIRatesEvaluation"
    }
    }
    rule {
    name     = "AWS-AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesCommonRuleSet"
      }
    }

    visibility_config {
      sampled_requests_enabled    = true
      cloudwatch_metrics_enabled  = true
      metric_name                 = "AWS-AWSManagedRulesCommonRuleSet"
    }
  }
    rule {
    name     = "AWS-AWSManagedRulesKnownBadInputsRuleSet"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
      }
    }

    visibility_config {
      sampled_requests_enabled    = true
      cloudwatch_metrics_enabled  = true
      metric_name                 = "AWS-AWSManagedRulesKnownBadInputsRuleSet"
    }
  }


    
  rule {
    name     = "AWSManagedRulesLinuxRuleSet"
    priority = 3

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesLinuxRuleSet"
      }
    }

    visibility_config {
      sampled_requests_enabled    = true
      cloudwatch_metrics_enabled  = true
      metric_name                 = "AWSManagedRulesLinuxRuleSet"
    }
  }
    rule {
    name     = "AWS-AWSManagedRulesAmazonIpReputationList"
    priority = 4

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesAmazonIpReputationList"
      }
    }

    visibility_config {
      sampled_requests_enabled    = true
      cloudwatch_metrics_enabled  = true
      metric_name                 = "AWS-AWSManagedRulesAmazonIpReputationList"
    }
  }
  rule {
    name     = "Blocked_ips"
    priority = 5

    action {
      block {}
    }

    statement {
      ip_set_reference_statement {
        arn = var.blocked_ips_arn 
      }
    }

    visibility_config {
      sampled_requests_enabled    = true
      cloudwatch_metrics_enabled  = true
      metric_name                 = "Blocked_ips"
    }
  }
rule {
    name     = "AuthorizedEndpoints"
    priority = 6

    action {
      count {}
    }

    statement {
      and_statement {
        statements {
          not_statement {
            statement {
              byte_match_statement {
                search_string = "/login"
                field_to_match {
                  uri_path {}
                }
                text_transformation {
                  priority = 0
                  type     = "NORMALIZE_PATH"
                }
                positional_constraint = "STARTS_WITH"
              }
            }
          }
        }

        statements {
          not_statement {
            statement {
              byte_match_statement {
                search_string = "/logout"
                field_to_match {
                  uri_path {}
                }
                text_transformation {
                  priority = 0
                  type     = "NONE"
                }
                positional_constraint = "STARTS_WITH"
              }
            }
          }
        }

        statements {
          not_statement {
            statement {
              byte_match_statement {
                search_string = "/auth"
                field_to_match {
                  uri_path {}
                }
                text_transformation {
                  priority = 0
                  type     = "NONE"
                }
                positional_constraint = "STARTS_WITH"
              }
            }
          }
        }

        statements {
          not_statement {
            statement {
              byte_match_statement {
                search_string = "/geolocate"
                field_to_match {
                  uri_path {}
                }
                text_transformation {
                  priority = 0
                  type     = "NONE"
                }
                positional_constraint = "STARTS_WITH"
              }
            }
          }
        }

        statements {
          not_statement {
            statement {
              byte_match_statement {
                search_string = "/hook"
                field_to_match {
                  uri_path {}
                }
                text_transformation {
                  priority = 0
                  type     = "NONE"
                }
                positional_constraint = "STARTS_WITH"
              }
            }
          }
        }

        statements {
          not_statement {
            statement {
              byte_match_statement {
                search_string = "/version"
                field_to_match {
                  uri_path {}
                }
                text_transformation {
                  priority = 0
                  type     = "NONE"
                }
                positional_constraint = "STARTS_WITH"
              }
            }
          }
        }
      }
    }

    visibility_config {
      sampled_requests_enabled    = true
      cloudwatch_metrics_enabled  = true
      metric_name                 = "AuthorizedEndpoints"
    }


    visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = "sre-bot"
        sampled_requests_enabled    = true
    }
    tags = {
        Name = "sre-bot"
    }
}
}
resource "aws_wafv2_ip_set" "blocked_ips" {
  name        = "sre-bot-blocked-ips"
  description = "List of IP addresses for the SRE bot that are blocked due to attacks"
  scope       = "REGIONAL" 

  ip_address_version = "IPV4"

  addresses = [
    "222.180.82.37/32",
    "180.158.42.112/32",
    "103.121.39.54/32",
    "144.126.228.231/32"
  ]

}

resource "aws_wafv3_web_acl_association" "sre-bot"
{
    resource_arn = aws_lb.sre-bot.arn
    web_acl_arn  = aws_wafv3_web_acl.sre-bot.arn
}

resource "aws_cloudwatch_log_group" "sre_bot_waf_log_group"
{
    name = "sre-bot-waf-log-group"
}
resource "aws_wafv2_web_acl_logging_configuration" "sre-bot"
{
    resource_arn = aws_wafv3_web_acl.sre-bot.arn
    log_destination_configs = [aws_cloudwatch_log_group.sre_bot_waf_log_group.arn]
}