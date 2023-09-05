#!/bin/sh
echo "Retrieving environment parameters"
aws ssm get-parameters --region ca-central-1 --with-decryption --names sre-bot-config --query 'Parameters[*].Value' --output text > ".env"

# Running npm install
echo "Starting npm install"
npm install --prefix ../frontend

# starting npm build to generate build folder
echo "Starting npm build ..."
npm run build --prefix ../frontend

echo "Starting server ..."
exec uvicorn main:server_app --host=0.0.0.0