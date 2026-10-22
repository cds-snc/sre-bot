#!/bin/bash
# Fails unless the service runs the task definition this deploy registered and its
# PRIMARY deployment completed. The services-stable waiter also succeeds after a
# circuit breaker or alarm rollback, since the service settles on the old revision
# (decisions/deployment.md).
#
# Usage: verify-ecs-deployment.sh <registered task definition ARN> <describe-services JSON file>

set -euo pipefail

registered="${1:-}"
services_json="${2:?usage: verify-ecs-deployment.sh <task definition ARN> <describe-services JSON file>}"

if [[ -z "$registered" ]]; then
  echo "No task definition was registered, so the deployment did not start." >&2
  exit 1
fi

current=$(jq -r '.services[0].taskDefinition' "$services_json")
rollout=$(jq -r '[.services[0].deployments[] | select(.status == "PRIMARY")][0].rolloutState // "UNKNOWN"' "$services_json")
reason=$(jq -r '[.services[0].deployments[] | select(.status == "PRIMARY")][0].rolloutStateReason // ""' "$services_json")

if [[ "$current" != "$registered" ]]; then
  echo "Deployment rolled back (circuit breaker or alarm): the service runs ${current##*/}, not ${registered##*/}. ${reason}" >&2
  exit 1
fi

if [[ "$rollout" != "COMPLETED" ]]; then
  echo "Deployment of ${registered##*/} is ${rollout}, not COMPLETED. ${reason}" >&2
  exit 1
fi

echo "The service runs ${registered##*/} and its deployment completed."
