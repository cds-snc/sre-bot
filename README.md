# SRE Bot

![SRE Bot Logo](https://user-images.githubusercontent.com/867334/156588127-aaae9fff-cd4b-4984-90f0-4d74dfaf4993.png)

**SRE Bot** is a Slack bot designed for site reliability engineering at CDS. It automates incident management, integrates with cloud and collaboration platforms, and streamlines SRE workflows for modern teams.

---

## Features

- **Incident Management**
  - Create, update, and manage incidents (status, roles, conversations, documents, folders, notifications)
  - Display and update incident information
  - Notify about stale incident channels
  - Schedule incident retrospectives
  - On-call management for incidents

- **AWS Integration & SCIM-like User/Group Management**
  - Manage AWS access requests and approvals
  - Monitor AWS account health
  - Assign and manage AWS user and group memberships (SCIM bridge functionality)
  - Manage AWS Identity Center and SSO access
  - Track AWS spending and cost reports

- **Slack Integration & Webhook Management**
  - Create, list, and manage Slack webhooks
  - Send notifications to Slack channels
  - Integrate with Slack for incident and alert workflows

- **Google Workspace Integration**
  - Manage Google Workspace users and groups (provisioning, reporting)
  - Integrate with Google for incident and workflow automation

- **Role & Talent Management**
  - Manage organizational roles, including special workflows for "Talent" roles
  - Assign and update user roles within the organization

- **Secret Management**
  - Store, retrieve, and manage secrets securely

- **SRE & Geolocation Features**
  - Geolocate users or incidents (using MaxMind or similar)
  - SRE-specific workflows and reporting

- **Notification & Alerting Integrations**
  - Integrate with external notification systems (OpsGenie, Sentinel, Trello, etc.)
  - Send and manage alerts from various sources

- **Reporting & Analytics**
  - Generate and display reports (including Google Groups, AWS spending, etc.)

- **Webhook Integrations (General)**
  - Manage and process incoming webhooks from various sources (AWS SNS, custom, etc.)
  - Route and handle webhook-based notifications

---

## Who is this for?

- SRE teams, DevOps engineers, and incident responders at CDS or similar organizations.
- Teams looking to automate cloud, incident, and collaboration workflows in Slack.

---

## Example Workflows

- `/incident create` — Start a new incident and assign roles
- `/aws access-request` — Request temporary AWS access
- `/webhook add slack` — Register a new Slack webhook for notifications
- `/role assign talent` — Assign a "Talent" role to a user

---

## Getting Started (Local Development)

This project uses [Visual Studio Code Remote - Containers](https://code.visualstudio.com/docs/remote/containers).

### Requirements

- Docker installed and running
- VS Code

### Steps

1. Clone the repo
2. Open VS Code with Dev Container ([Quick start guide](https://code.visualstudio.com/docs/remote/containers#_quick-start-open-an-existing-folder-in-a-container))
3. Install Python dependencies:

  ```sh
  cd app && pip install --no-cache-dir -r requirements.txt
  ```

4. Add a `.env` file to the `/workspace/app` folder (Contact SRE team for the project-specific .env setup)
5. Launch the dev bot:

  ```sh
  make dev
  ```

6. Test your development in the dedicated Slack channel (SRE team will confirm which channel to use)

---

## Project Structure

- `app/integrations/` — Integrations with external services (Google Workspace, Slack, AWS, etc.)
- `app/modules/` — Bot features and user-facing commands
- `app/jobs/` — Scheduled jobs (e.g., reminders, status checks)

---

## Security & Privacy

SRE Bot handles sensitive data such as secrets and user/group assignments. Please review our [security guidelines](./SECURITY.md) and ensure you follow best practices for environment configuration and access control.

---

## Getting Help

- For questions or support, contact the SRE team.
- For feature requests or bug reports, open an issue in this repository.

---

## License

[MIT License](./LICENSE)

---
