# Purpose

Orchestrator for organization tooling and operational workflows.

## Key Features

- Incident management
- Group membership sync from primary IdP to third-party applications (AWS, planned: others)
- Operational tools for admin tasks
- Reporting: pull and process data from third-party integrations

## Interaction Modes

- **Primary**: Slack integration (Socket Mode)
- **Secondary**: FastAPI routes
- **Webhooks**: Receive and process external events (e.g., GitHub)
- **Planned**: MS Teams integration

## Route Access

- Routes accessed via Backstage (dev portal) only
- Custom Backstage plugins interact with SRE Bot routes
- Webhooks endpoint validates payloads and posts results to Slack channels
