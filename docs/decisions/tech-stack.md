# Infrastructure

## Cloud & Networking
- **AWS**: ca-central-1 (primary), us-east-1 (secondary)
- **VPC**: SREBotVPC, 3 AZs, public/private subnets
- **Route53**: sre-bot.cdssandbox.xyz with health checks and query logging

## Compute
- **Container**: ECS Fargate (CPU 512, memory 1024, 2 tasks)
- **Cluster**: sre-bot-cluster with Container Insights
- **Image**: ECR repository `sre-bot:latest`
- **Network**: awsvpc, private subnets, no public IPs

## Load Balancing & DNS
- **ALB**: Internet-facing, HTTPS on 443
- **TLS**: ELBSecurityPolicy-TLS13-1-2-FIPS-2023-04, ACM certificate for sre-bot.cdssandbox.xyz and *.sre-bot.cdssandbox.xyz
- **Health Check**: GET /version (10s interval, 2/2 threshold)

## Security
- **WAFv2**: Regional Web ACL on ALB
  - Managed rules: Common, Known BadInputs, Linux, Reputation
  - Custom rules: 500 req/s global, 1000 req/IP, IP blocklist
- **Security Groups**: ALB (inbound 443 from 0.0.0.0/0), ECS (inbound 8000 from VPC, outbound all)
- **IAM**: ECS task role with sts:AssumeRole, SSM, DynamoDB, S3, SQS, Lambda read-only, GitHub OIDC for CI/CD

## Data Storage
- **DynamoDB**: webhooks, aws_access_requests, sre_bot_data, incidents, sre_bot_idempotency, sre_bot_audit_trail, sre_bot_retry_records
- **Backups**: KMS-encrypted, daily 6 AM UTC, 30-day retention
- **TTL**: Enabled on idempotency and audit trail tables

## Messaging
- **SNS**: sre-bot-cloudwatch-alarms-warning (KMS-encrypted) → Slack webhook
- **SQS**: sre-bot-fifo-queue.fifo with DLQ (maxReceiveCount 5)

## Observability
- **Logs**: CloudWatch /ecs/sre-bot-app (30-day retention)
- **Alarms**: Error count, warning count, ECS CPU/memory (>= 80%)
- **WAF Logs**: CloudWatch aws-waf-logs-sre-bot (30-day retention)

## Application runtime (entrypoint)
- FastAPI application created in server.handler and included API router.
- CORS middleware enabled; in production allow_origins is "*", otherwise localhost origins are allowed.
- Rate limiting set up via api.dependencies.rate_limits.
- Slack Bolt App configured with SLACK_TOKEN and Socket Mode using APP_TOKEN.
- Startup events:
	- providers_startup() activates group and command providers and registers infrastructure/event handlers.
	- main() registers Slack commands and event handlers, then connects Socket Mode.
- Scheduled tasks run when PREFIX == "".

## Python dependencies (requirements.txt)
- Web/API: fastapi, uvicorn, httpx, Jinja2, python-dotenv, pydantic-settings
- Auth/security: Authlib, PyJWT, python-jose, email-validator, itsdangerous
- AWS/Cloud: boto3, botocore, awscli, aws-sns-message-validator
- Google APIs: google-api-python-client, google-api-core, google-auth, google-auth-httplib2, google-auth-oauthlib
- Slack/notifications: slack-bolt
- Data/time: pandas, pytz, arrow
- Scheduling/rate-limiting: schedule, slowapi
- Misc: PyYAML, requests, python-i18n, structlog, trello