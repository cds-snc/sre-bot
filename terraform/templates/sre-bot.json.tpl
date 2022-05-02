[
  {
    "image": "${image}",
    "linuxParameters": {
      "capabilities": {
        "drop": [
          "ALL"
        ]
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
        "containerPort": 8000
      }
    ],
    "ulimits": [
      {
        "hardLimit": 1000000,
        "name": "nofile",
        "softLimit": 1000000
      }
    ]
  }
]