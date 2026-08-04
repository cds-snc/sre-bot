[
  {
    "image": "${image}",
    "linuxParameters": {
      "capabilities": {
        "drop": [
          "ALL"
        ],
        "add": [] 
      }
    },
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "${awslogs-group}",
        "awslogs-region": "${awslogs-region}",
        "awslogs-stream-prefix": "${awslogs-stream-prefix}"
      }
    },
    "healthCheck": {
      "command": [
        "CMD-SHELL",
        "python -c \"import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)\""
      ],
      "interval": 30,
      "timeout": 5,
      "retries": 3,
      "startPeriod": 10
    },
    "name": "sre-bot",
    "portMappings": [
      {
        "containerPort": 8000,
        "hostPort": 8000,
        "protocol": "tcp"
      }
    ],
    "secrets": [
      {
        "name": "GCP_SRE_SERVICE_ACCOUNT_KEY_FILE",
        "valueFrom": "${GCP_SRE_SERVICE_ACCOUNT_KEY_FILE}"
      }
    ],
    "ulimits": [
      {
        "hardLimit": 1000000,
        "name": "nofile",
        "softLimit": 1000000
      }
    ],
    "cpu": 0,
    "environment": [
      {
        "name": "BACKEND_URL",
        "value": "${backend_url}"
      },
      {
        "name": "ENVIRONMENT",
        "value": "production"
      },
      {
        "name": "CORS_ALLOWED_ORIGINS",
        "value": "${cors_allowed_origins}"
      },
      {
        "name": "SLACK__COMMAND_PREFIX",
        "value": ""
      }
    ],
    "essential": true,
    "mountPoints": [],
    "systemControls": [],
    "volumesFrom": [] 
  }
]
