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
        "name": "PICKLE_STRING",
        "valueFrom": "${PICKLE_STRING}"
      },
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
    "environment": [],
    "essential": true,
    "mountPoints": [],
    "systemControls": [],
    "volumesFrom": [] 
  }
]