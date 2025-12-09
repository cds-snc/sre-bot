# AWS ElastiCache (Valkey/Redis) for circuit breaker state persistence
#
# Creates a single-node ElastiCache cluster for storing application state
# that needs to survive restarts and be shared across ECS instances.
#
# Features:
# - Valkey 7.2 (AWS's open-source Redis replacement)
# - Single-node configuration (cost-effective for state storage)
# - Multi-AZ with automatic failover (high availability)
# - Encryption in-transit and at-rest
# - Automatic backups
# - Private subnet placement (no public access)

# Subnet group for ElastiCache cluster
resource "aws_elasticache_subnet_group" "sre_bot" {
  name       = "${var.product_name}-elasticache-subnet-group"
  subnet_ids = module.vpc.private_subnet_ids

  tags = {
    CostCentre = var.billing_code
    Terraform  = "true"
    Product    = var.product_name
  }
}

# Security group for ElastiCache
resource "aws_security_group" "elasticache" {
  name        = "${var.product_name}-elasticache"
  description = "Security group for ElastiCache cluster"
  vpc_id      = module.vpc.vpc_id

  # Allow inbound from ECS tasks only
  ingress {
    description     = "Redis/Valkey from ECS tasks"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name       = "${var.product_name}-elasticache-sg"
    CostCentre = var.billing_code
    Terraform  = "true"
    Product    = var.product_name
  }
}

# Parameter group for Valkey/Redis configuration
resource "aws_elasticache_parameter_group" "sre_bot" {
  name        = "${var.product_name}-valkey72"
  family      = "valkey7"
  description = "Parameter group for SRE Bot ElastiCache (Valkey 7.2)"

  # Optimize for state storage workload
  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru" # Evict least recently used keys when memory is full
  }

  parameter {
    name  = "timeout"
    value = "300" # Close idle connections after 5 minutes
  }

  tags = {
    CostCentre = var.billing_code
    Terraform  = "true"
    Product    = var.product_name
  }
}

# ElastiCache Replication Group (single-node with Multi-AZ)
resource "aws_elasticache_replication_group" "sre_bot" {
  replication_group_id = "${var.product_name}-cache"
  description          = "ElastiCache cluster for SRE Bot state persistence"
  engine               = "valkey"
  engine_version       = "7.2"
  node_type            = "cache.t4g.micro" # 2 vCPU, 0.5 GB memory
  port                 = 6379
  parameter_group_name = aws_elasticache_parameter_group.sre_bot.name
  subnet_group_name    = aws_elasticache_subnet_group.sre_bot.name
  security_group_ids   = [aws_security_group.elasticache.id]

  # High availability configuration
  automatic_failover_enabled = true
  multi_az_enabled           = true
  num_cache_clusters         = 2 # Primary + 1 replica for failover

  # Encryption
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token_enabled         = false # Simplified auth for private VPC

  # Backup configuration
  snapshot_retention_limit = 5                     # Keep 5 days of backups
  snapshot_window          = "03:00-05:00"         # UTC backup window
  maintenance_window       = "sun:05:00-sun:07:00" # UTC maintenance window

  # Auto-upgrade to minor versions
  auto_minor_version_upgrade = true

  # Logging
  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.elasticache_slow_log.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "slow-log"
  }

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.elasticache_engine_log.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "engine-log"
  }

  tags = {
    CostCentre = var.billing_code
    Terraform  = "true"
    Product    = var.product_name
  }

  depends_on = [
    aws_cloudwatch_log_group.elasticache_slow_log,
    aws_cloudwatch_log_group.elasticache_engine_log,
  ]
}

# CloudWatch Log Groups for ElastiCache logs
resource "aws_cloudwatch_log_group" "elasticache_slow_log" {
  name              = "/aws/elasticache/${var.product_name}/slow-log"
  retention_in_days = 7

  tags = {
    CostCentre = var.billing_code
    Terraform  = "true"
    Product    = var.product_name
  }
}

resource "aws_cloudwatch_log_group" "elasticache_engine_log" {
  name              = "/aws/elasticache/${var.product_name}/engine-log"
  retention_in_days = 7

  tags = {
    CostCentre = var.billing_code
    Terraform  = "true"
    Product    = var.product_name
  }
}

# SSM Parameter for ElastiCache endpoint
resource "aws_ssm_parameter" "elasticache_endpoint" {
  name        = "/${var.product_name}/elasticache/endpoint"
  description = "ElastiCache primary endpoint"
  type        = "String"
  value       = aws_elasticache_replication_group.sre_bot.primary_endpoint_address

  tags = {
    CostCentre = var.billing_code
    Terraform  = "true"
    Product    = var.product_name
  }
}

# Outputs
output "elasticache_endpoint" {
  description = "ElastiCache primary endpoint address"
  value       = aws_elasticache_replication_group.sre_bot.primary_endpoint_address
}

output "elasticache_port" {
  description = "ElastiCache port"
  value       = aws_elasticache_replication_group.sre_bot.port
}

output "elasticache_reader_endpoint" {
  description = "ElastiCache reader endpoint address (for read replicas)"
  value       = aws_elasticache_replication_group.sre_bot.reader_endpoint_address
}
