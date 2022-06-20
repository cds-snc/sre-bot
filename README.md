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

