resource "aws_dynamodb_table" "webhooks_table" {
  name           = "webhooks"
  hash_key       = "id"
  read_capacity  = 1
  write_capacity = 1

  attribute {
    name = "id"
    type = "S"
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

resource "aws_dynamodb_table" "sre_bot_data" {
  name           = "sre_bot_data"
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
}

# The following code adds a backup configuration to the DynamoDB table.

# Define a KMS key to encrypt the backup.
resource "aws_kms_key" "sre_bot_backup_vault_key" {
  description         = "KMS key for DynamoDB backup"
  enable_key_rotation = true
}

# Create the backup vault.
resource "aws_backup_vault" "sre_bot_backup_vault" {
  name        = "sre-bot-dynamodb-backup-vault"
  kms_key_arn = aws_kms_key.sre_bot_backup_vault_key.arn
}

# Define a backup plan to back up the data. Backups will be performed daily at 1:00 AM Eastern Time, which is 6:00am UTC.
resource "aws_backup_plan" "sre_bot_backup_plan" {
  name = "sre-bot-dynamodb-backup-plan"
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
  iam_role_arn = aws_iam_role.sre_bot_backup_role.arn
  name         = "sre-bot-dynamodb-backup-selection"
  plan_id      = aws_backup_plan.sre_bot_backup_plan.id

  # Add all the tables we have created to the backup plan.
  resources = [
    aws_dynamodb_table.sre_bot_data.arn,
    aws_dynamodb_table.webhooks_table.arn,
    aws_dynamodb_table.aws_access_requests_table.arn,
    aws_dynamodb_table.incidents_table.arn,
  ]
}

# Create an IAM role to allow AWS Backup to perform backups.
resource "aws_iam_role" "sre_bot_backup_role" {
  name = "sre-bot-dynamodb-backup-role"

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
  roles      = [aws_iam_role.sre_bot_backup_role.name]
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

