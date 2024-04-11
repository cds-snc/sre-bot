# SRE Bot

![image](https://user-images.githubusercontent.com/867334/156588127-aaae9fff-cd4b-4984-90f0-4d74dfaf4993.png)

A slack bot for site reliability engineering at CDS. 

This bot is using the Bolt framework in python (https://slack.dev/bolt-python/) and uses a web socket connection to Slack.

## Local Development with Containers

This project uses [Visual Studio Code Remote - Containers](https://code.visualstudio.com/docs/remote/containers).

Here are the instructions to get started with developing locally.

Requirements:

- Docker installed and running
- VS Code

Steps:

1. Clone the repo
2. Open VS Code with Dev Container (see [Quick start: Open an existing folder in a container](https://code.visualstudio.com/docs/remote/containers#_quick-start-open-an-existing-folder-in-a-container))
3. Install Python dependencies

```
cd app && pip install --no-cache-dir -r requirements.txt
```

4. Add a ``.env`` file to the ``/workspace/app`` folder (Contact SRE team for the project specific .env setup)
5. Launch the dev bot with ```make dev```
6. Test your development in the dedicated channel (SRE team will confirm which channel to point to)

## Refactoring

The bot is currently being refactored to separate the integration concerns from the bot's features and commands. The goal is to make the bot more modular and easier to maintain.

### Integrations

The `app/integrations` will contain the bot's interactions with external services (e.g. Google Workspace, Slack, etc.)

The integrations will be responsible for handling the bot's interactions with the external services. They will be responsible for sending and receiving messages, and handling any other interactions with the external services.

From a design perspective, they should be as simple as possible, and should not contain any business logic. They should be responsible for handling the interactions with the external services, and should delegate any business logic to the features.

### Features (aka modules)

The `app/modules` will contain the bot's features and commands. Each feature will have its own directory and will be responsible for handling the bot's interactions with the user.

The features may end up needing to interact with the integrations to perform their tasks.

### Jobs

The `app/jobs` will contain the bot's scheduled jobs. Each job will have its own directory and will be responsible for handling the bot's scheduled tasks.

Examples may include sending daily reminders, checking the status of a service, etc.