# See here for image contents: https://github.com/microsoft/vscode-dev-containers/tree/v0.183.0/containers/python-3/.devcontainer/base.Dockerfile

ARG VARIANT="3.14"
FROM mcr.microsoft.com/devcontainers/python:3-${VARIANT}-bookworm

# Install packages
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    && apt-get autoremove -y && apt-get clean -y

COPY .devcontainer/apt-packages.txt ./
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && xargs apt-get -y install --no-install-recommends <apt-packages.txt

# Google Cloud CLI, for the Google identity a developer runs the bot with:
# gcloud auth application-default login, then impersonation of the service account
# (docs/runbooks/set-up-google-workspace-access.md, "Run the bot locally"). Google's apt repository,
# signed by its published key: https://cloud.google.com/sdk/docs/install#deb
RUN curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
    > /etc/apt/sources.list.d/google-cloud-sdk.list \
    && apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends google-cloud-cli \
    && apt-get clean -y

# Setup aliases and autocomplete
RUN echo "\n\
    complete -C /usr/local/bin/aws_completer aws\n\
    complete -C /usr/local/bin/terraform terraform\n\
    complete -C /usr/local/bin/terraform terragrunt\n\
    alias tf='terraform'\n\
    alias tg='terragrunt'\n\
    alias ll='la -la'" >> /home/vscode/.zshrc

# Setup AWS Credentials
RUN mkdir -p /home/vscode/.aws 

RUN echo "\n\
    [default]\n\
    aws_access_key_id=foo\n\
    aws_secret_access_key=bar\n\
    " >> /home/vscode/.aws/credentials

RUN echo "\n\
    [default]\n\
    region=ca-central-1\n\
    output=json\n\
    " >> /home/vscode/.aws/config
