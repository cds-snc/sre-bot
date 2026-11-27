# Webhook instances, keyed by the URL token. instance_ref is the internal reference the sweeper and
# the control plane address an instance by, never the token; items without it stay out of
# the by_instance_ref index, which is sparse (app/capabilities/webhooks/store.py, decisions/webhooks.md section 3).
resource "aws_dynamodb_table" "webhooks_table" {
  name         = "webhooks"
  hash_key     = "id"
  billing_mode = "PAY_PER_REQUEST"

  on_demand_throughput {
    max_read_request_units  = var.dynamodb_max_read_request_units
    max_write_request_units = var.dynamodb_max_write_request_units
  }

  attribute {
    name = "id"
    type = "S"
  }

  attribute {
    name = "instance_ref"
    type = "S"
  }

  global_secondary_index {
    name            = "by_instance_ref"
    projection_type = "ALL"

    key_schema {
      attribute_name = "instance_ref"
      key_type       = "HASH"
    }
  }
}

# Webhook inbox: one item per accepted delivery, keyed 'webhooks:<instance_ref>:<delivery id>'
# (app/capabilities/webhooks/store.py, decisions/webhooks.md section 3). Items expire through
# expires_at (epoch seconds, [webhooks] inbox_ttl_seconds, default 7 days). due is set only while an
# item is processing or awaiting a retry, so by_due holds only the items the sweeper must look at;
# by_instance lists an instance's deliveries by received_at (epoch milliseconds).
# The recovery window equals the item TTL: the inbox's retention is its TTL, so it is also left out
# of the AWS Backup selection below (decisions/deployment.md Tables).
resource "aws_dynamodb_table" "sre_bot_webhook_inbox" {
  name                        = "sre_bot_webhook_inbox"
  hash_key                    = "item_key"
  billing_mode                = "PAY_PER_REQUEST"
  deletion_protection_enabled = true

  on_demand_throughput {
    max_read_request_units  = var.dynamodb_max_read_request_units
    max_write_request_units = var.dynamodb_max_write_request_units
  }

  attribute {
    name = "item_key"
    type = "S"
  }

  attribute {
    name = "due"
    type = "S"
  }

  attribute {
    name = "due_at"
    type = "N"
  }

  attribute {
    name = "instance_ref"
    type = "S"
  }

  attribute {
    name = "received_at"
    type = "N"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled                 = true
    recovery_period_in_days = 7
  }

  global_secondary_index {
    name            = "by_due"
    projection_type = "ALL"

    key_schema {
      attribute_name = "due"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "due_at"
      key_type       = "RANGE"
    }
  }

  global_secondary_index {
    name            = "by_instance"
    projection_type = "ALL"

    key_schema {
      attribute_name = "instance_ref"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "received_at"
      key_type       = "RANGE"
    }
  }
}

resource "aws_dynamodb_table" "aws_access_requests_table" {
  name           = "aws_access_requests"
  hash_key       = "account_id"
  range_key      = "created_at"
  read_capacity  = 1
  write_capacity = 1

  attribute {
    name = "account_id"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "N"
  }
}

resource "aws_dynamodb_table" "sre_bot_access" {
  name           = "sre_bot_access"
  hash_key       = "PK"
  range_key      = "SK"
  read_capacity  = 2
  write_capacity = 2

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }
}

# Dedicated table for Access Requests lifecycle records.
# Key scheme: PK = ACCESS_REQUEST#{request_id}, SK = REQUEST | DECISION#... | AUDIT#...
# Kept separate from sre_bot_access (Access Sync audit runs) to allow independent
# scaling, access policies, and retention settings.
resource "aws_dynamodb_table" "sre_bot_access_requests" {
  name           = "sre_bot_access_requests"
  hash_key       = "PK"
  range_key      = "SK"
  read_capacity  = 2
  write_capacity = 2

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }
}


# One item per incident status update: PK INCIDENT#<incident uuid>, SK UPDATE#<sequence>
resource "aws_dynamodb_table" "sre_bot_incident_status_updates" {
  name           = "sre_bot_incident_status_updates"
  hash_key       = "PK"
  range_key      = "SK"
  read_capacity  = 2
  write_capacity = 2

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }
}

resource "aws_dynamodb_table" "incidents_table" {
  name           = "incidents"
  hash_key       = "id"
  read_capacity  = 2
  write_capacity = 2

  attribute {
    name = "id"
    type = "S"
  }

  attribute {
    name = "channel_id"
    type = "S"
  }

  attribute {
    name = "open_bucket"
    type = "S"
  }

  attribute {
    name = "opened_at"
    type = "S"
  }

  # Look up the incident of a Slack channel.
  # Write capacity matches the table's: with projection ALL every incident write is also written here.
  global_secondary_index {
    name            = "by_channel"
    projection_type = "ALL"
    read_capacity   = 1
    write_capacity  = 2

    key_schema {
      attribute_name = "channel_id"
      key_type       = "HASH"
    }
  }

  # Sparse index of open incidents, oldest first.
  # open_bucket is set to OPEN only while the incident is open; items without it are absent from the index.
  # opened_at is fixed-width ISO-8601 UTC with microseconds and +00:00, so it sorts as text.
  global_secondary_index {
    name            = "open"
    projection_type = "ALL"
    read_capacity   = 1
    write_capacity  = 2

    key_schema {
      attribute_name = "open_bucket"
      key_type       = "HASH"
    }
    key_schema {
      attribute_name = "opened_at"
      key_type       = "RANGE"
    }
  }
}

# Incident timeline: one item per timeline entry.
# entry_key is '<posted_at ISO-8601>#<entry_id>', so entries sort by posting time.
resource "aws_dynamodb_table" "sre_bot_incident_timeline" {
  name           = "sre_bot_incident_timeline"
  hash_key       = "incident_id"
  range_key      = "entry_key"
  read_capacity  = 2
  write_capacity = 2

  attribute {
    name = "incident_id"
    type = "S"
  }

  attribute {
    name = "entry_key"
    type = "S"
  }
}

# Incident bindings: one item per place responders work an incident (a chat conversation now,
# a Backstage page later). binding_key is '<kind>#<system>#<tenant>#<vendor_id>'.
# conversation_id is set only on chat bindings, so the by_conversation index is sparse.
resource "aws_dynamodb_table" "sre_bot_incident_bindings" {
  name           = "sre_bot_incident_bindings"
  hash_key       = "incident_id"
  range_key      = "binding_key"
  read_capacity  = 2
  write_capacity = 2

  attribute {
    name = "incident_id"
    type = "S"
  }

  attribute {
    name = "binding_key"
    type = "S"
  }

  attribute {
    name = "conversation_id"
    type = "S"
  }

  # Find the incident bound to a chat conversation.
  # Write capacity matches the table's: with projection ALL every chat binding write is also written here.
  global_secondary_index {
    name            = "by_conversation"
    projection_type = "ALL"
    read_capacity   = 1
    write_capacity  = 2

    key_schema {
      attribute_name = "conversation_id"
      key_type       = "HASH"
    }
  }
}

# Dedicated table for idempotency cache
# Stores cached API responses with automatic TTL-based expiration
resource "aws_dynamodb_table" "sre_bot_idempotency" {
  name           = "sre_bot_idempotency"
  hash_key       = "idempotency_key"
  read_capacity  = 5
  write_capacity = 5

  attribute {
    name = "idempotency_key"
    type = "S"
  }

  # Enable TTL for automatic expiration of cached responses (default 1 hour)
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

}

# Audit trail table for operational queries
resource "aws_dynamodb_table" "sre_bot_audit_trail" {
  name           = "sre_bot_audit_trail"
  hash_key       = "resource_id"
  range_key      = "timestamp_correlation_id"
  read_capacity  = 2
  write_capacity = 2

  attribute {
    name = "resource_id"
    type = "S"
  }

  attribute {
    name = "timestamp_correlation_id"
    type = "S"
  }

  attribute {
    name = "user_email"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "correlation_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl_timestamp"
    enabled        = true
  }

  global_secondary_index {
    name            = "user_email-timestamp-index"
    projection_type = "ALL"
    read_capacity   = 1
    write_capacity  = 1

    key_schema {
      attribute_name = "user_email"
      key_type       = "HASH"
    }
    key_schema {
      attribute_name = "timestamp"
      key_type       = "RANGE"
    }
  }

  global_secondary_index {
    name            = "correlation_id-index"
    projection_type = "ALL"
    read_capacity   = 1
    write_capacity  = 1

    key_schema {
      attribute_name = "correlation_id"
      key_type       = "HASH"
    }
  }
}

# Every DynamoDB table goes in this list: it feeds both the backup selection below
# and the task role's table statement in iam.tf, so a new table is backed up and reachable.
locals {
  dynamodb_table_arns = [
    aws_dynamodb_table.webhooks_table.arn,
    aws_dynamodb_table.aws_access_requests_table.arn,
    aws_dynamodb_table.sre_bot_access.arn,
    aws_dynamodb_table.sre_bot_access_requests.arn,
    aws_dynamodb_table.sre_bot_incident_status_updates.arn,
    aws_dynamodb_table.incidents_table.arn,
    aws_dynamodb_table.sre_bot_incident_timeline.arn,
    aws_dynamodb_table.sre_bot_incident_bindings.arn,
    aws_dynamodb_table.sre_bot_idempotency.arn,
    aws_dynamodb_table.sre_bot_audit_trail.arn,
    aws_dynamodb_table.sre_bot_webhook_inbox.arn,
  ]
}

# The following code adds a backup configuration to the DynamoDB table.

# Define a KMS key to encrypt the backup.
resource "aws_kms_key" "sre_bot_backup_vault_key" {
  provider            = aws.core_services
  description         = "KMS key for DynamoDB backup"
  enable_key_rotation = true
}

# Create the backup vault.
resource "aws_backup_vault" "sre_bot_backup_vault" {
  provider    = aws.core_services
  name        = "sre-bot-dynamodb-backup-vault"
  kms_key_arn = aws_kms_key.sre_bot_backup_vault_key.arn
}

# Define a backup plan to back up the data. Backups will be performed daily at 1:00 AM Eastern Time, which is 6:00am UTC.
resource "aws_backup_plan" "sre_bot_backup_plan" {
  provider = aws.core_services
  name     = "sre-bot-dynamodb-backup-plan"
  rule {
    rule_name         = "sre-bot-dynamodb-backup-rule"
    target_vault_name = aws_backup_vault.sre_bot_backup_vault.name
    schedule          = "cron(0 6 * * ? *)"
    start_window      = "60"  # Start within one hour 
    completion_window = "120" # Complete within two hours

    lifecycle {
      delete_after = 30 # Retain backups for 30 days
    }
  }
}

# Assign/Associate the backup plan to the DynamoDB table.
resource "aws_backup_selection" "sre_bot_backup_selection" {
  provider     = aws.core_services
  iam_role_arn = aws_iam_role.sre_bot_backup_role.arn
  name         = "sre-bot-dynamodb-backup-selection"
  plan_id      = aws_backup_plan.sre_bot_backup_plan.id

  resources = local.dynamodb_table_arns

  # Left out on purpose: the webhook inbox is a delivery log whose retention is its 7-day item TTL,
  # and its point-in-time recovery covers the same window; 30-day backups would keep envelopes past it.
  not_resources = [aws_dynamodb_table.sre_bot_webhook_inbox.arn]
}

# Create an IAM role to allow AWS Backup to perform backups.
resource "aws_iam_role" "sre_bot_backup_role" {
  provider = aws.core_services
  name     = "sre-bot-dynamodb-backup-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "backup.amazonaws.com"
        },
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# Attach the default AWS Backup policy to the IAM Role 
resource "aws_iam_policy_attachment" "sre_bot_backup_role_policy" {
  name       = "sre-bot-dynamodb-backup-role-policy"
  provider   = aws.core_services
  roles      = [aws_iam_role.sre_bot_backup_role.name]
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

