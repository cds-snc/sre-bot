#!/bin/sh
echo "Retrieving environment parameters"
aws ssm get-parameters --region ca-central-1 --with-decryption --names sre-bot-config --query 'Parameters[*].Value' --output text > ".env"

# starting npm build to generate build folder
echo "Starting npm build ..."
exec npm run build

echo "Starting server ..."
exec uvicorn main:server_app --host=0.0.0.0