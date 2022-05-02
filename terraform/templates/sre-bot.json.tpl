[
  {
    "environment": [
      {
        "name": "SRE_DRIVE_ID",
        "value": "${sre_drive_id}"
      },
      {
        "name": "SRE_INCIDENT_FOLDER",
        "value": "${sre_incident_folder}"
      },
      {
        "name": "INCIDENT_TEMPLATE",
        "value": "${incident_template}"
      },
      {
        "name": "INCIDENT_LIST",
        "value": "${incident_list}"
      },
      {
        "name": "INCIDENT_CHANNEL",
        "value": "${incident_channel}"
      }
    ],
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