# See here for image contents: https://github.com/microsoft/vscode-dev-containers/tree/v0.183.0/containers/python-3/.devcontainer/base.Dockerfile

# [Choice] Python version: 3, 3.9, 3.8, 3.7, 3.6
ARG VARIANT="3.9"
FROM mcr.microsoft.com/vscode/devcontainers/python:0-${VARIANT}

# Install packages
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    && apt-get autoremove -y && apt-get clean -y

# Install Checkov
RUN pip3 install --upgrade requests setuptools \
    && pip3 install --upgrade botocore checkov

COPY .devcontainer/apt-packages.txt ./
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && xargs apt-get -y install --no-install-recommends <apt-packages.txt

# Setup aliases and autocomplete
RUN echo "\n\
complete -C /usr/bin/aws_completer aws\n\
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

# [Optional] If your pip requirements rarely change, uncomment this section to add them to the image.
# COPY requirements.txt /tmp/pip-tmp/
# RUN pip3 --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
#    && rm -rf /tmp/pip-tmp
