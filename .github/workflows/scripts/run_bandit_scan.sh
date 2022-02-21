#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

# Make sure we are using the latest version
docker pull cytopia/bandit:latest

# Scan source code and only report on high severity issues
docker run --rm -v "$(pwd)":/data cytopia/bandit -r /data -ll