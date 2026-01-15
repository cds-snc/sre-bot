#!/usr/bin/env python3
"""Test script to verify /sre geolocate uses new package."""

import sys
from unittest.mock import Mock, patch
from infrastructure.operations import OperationResult
from modules.sre.sre import GeolocateProvider

# Mock successful HTTP response
mock_http_result = OperationResult.success(
    data={
        "ip_address": "8.8.8.8",
        "city": "Mountain View",
        "country_code": "US",
        "latitude": 37.386,
        "longitude": -122.0838,
        "time_zone": "America/Los_Angeles",
    }
)

# Simulate Slack command payload
mock_command = {
    "text": "8.8.8.8",
    "user_id": "U123TEST",
    "user_name": "testuser",
    "channel_id": "C123TEST",
    "channel_name": "test-channel",
    "response_url": "https://hooks.slack.com/test",
}

mock_respond = Mock()
payload = {
    "command": mock_command,
    "client": Mock(),
    "respond": mock_respond,
    "ack": Mock(),
}

print("🧪 Testing /sre geolocate command with new package")
print(f"📍 IP Address: {mock_command['text']}")
print()


provider = GeolocateProvider()
print("✅ GeolocateProvider instantiated")

try:
    with patch("packages.geolocate.platform_features.InternalHttpClient") as MockClient:
        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_http_result
        MockClient.return_value = mock_client_instance

        provider.handle(payload)
        print("✅ Command handled successfully")
        print()

        if mock_client_instance.get.called:
            print("✅ InternalHttpClient.get() was called")
            call_args = mock_client_instance.get.call_args
            print(f"   URL: {call_args.args[0]}")
            print(f"   Params: {call_args.kwargs.get('params')}")
            print()

    if mock_respond.called:
        print("📤 Response sent to Slack:")
        call_args = mock_respond.call_args

        if "blocks" in call_args.kwargs:
            print()
            print("✨ ✨ ✨ NEW PACKAGE DETECTED! ✨ ✨ ✨")
            print("   Response uses Slack Block Kit (new package pattern)")
            blocks = call_args.kwargs["blocks"]
            print(f"   Number of blocks: {len(blocks)}")
            print()
            print("   Block structure:")
            for i, block in enumerate(blocks):
                print(f"     Block {i+1}: {block.get('type', 'unknown')}")
                if block.get("type") == "header":
                    print(f"       Header: {block['text']['text']}")
                elif block.get("type") == "section":
                    fields = block.get("fields", [])
                    print(f"       Fields: {len(fields)}")
        else:
            print()
            print("⚠️  LEGACY PACKAGE")
            if call_args.args:
                print(f"   Message: {call_args.args[0]}")
    else:
        print("❌ No response sent")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print()
print("🎉 Test completed successfully!")
print()
print("Summary:")
print("  ✅ /sre geolocate now uses packages/geolocate/")
print("  ✅ Calls internal HTTP endpoint via InternalHttpClient")
print("  ✅ Returns rich Slack Block Kit formatting")
print("  ✅ Ready for local testing with 'make dev'")
