#!/bin/sh
echo "Retrieving environment parameters"
aws ssm get-parameter --region ca-central-1 --with-decryption --name sre-bot-config --query 'Parameter.Value' --output text > ".env"
aws ssm get-parameter --region ca-central-1 --with-decryption --name sre-bot-config-infrastructure --query 'Parameter.Value' --output text >> ".env"

echo "Starting server ..."
exec uvicorn main:server_app --host=0.0.0.0