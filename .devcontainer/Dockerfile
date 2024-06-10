# See here for image contents: https://github.com/microsoft/vscode-dev-containers/tree/v0.183.0/containers/python-3/.devcontainer/base.Dockerfile
ARG VARIANT="3.11"
FROM mcr.microsoft.com/devcontainers/python:1-${VARIANT}

# Install additional packages if necessary
COPY .devcontainer/apt-packages.txt ./
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && xargs apt-get -y install --no-install-recommends <apt-packages.txt \
    && apt-get autoremove -y && apt-get clean -y

# Setup aliases and autocomplete if still needed
RUN echo "\n\
    alias ll='ls -la'" >> /home/vscode/.zshrc