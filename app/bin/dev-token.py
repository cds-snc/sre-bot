#!/usr/bin/env python3
"""Local development JWT token generator.

Generates a self-signed EC key pair, serves the public key as a JWKS endpoint
on a background HTTP server, and prints a signed JWT that the running SRE Bot
will accept when ISSUER_CONFIG points at this local server.

Usage:
    python3 bin/dev-token.py

Then in a separate terminal, configure your .env and start the app:
    DEV_JWKS_PORT defaults to 8001.

.env snippet (add or replace ISSUER_CONFIG):
    ISSUER_CONFIG={"http://127.0.0.1:8001": {"jwks_uri": "http://127.0.0.1:8001/.well-known/jwks.json", "algorithms": ["ES256"], "audience": "sre-bot-dev"}}

Then smoke test:
    curl -s -X POST http://localhost:8000/api/v1/access/sync-runs \\
        -H "Authorization: Bearer <printed-token>" \\
        -H "Content-Type: application/json" \\
        -d '{"sync_type":"user","user_email":"you@example.com","platform":"aws"}'

To test the FastAPI endpoints via the /docs Swagger UI, use the "Authorize" button to enter the token as a Bearer token (just the token string, without the "Bearer " prefix).

The script runs until you press Ctrl-C. It generates a new key pair each time it
starts, so the printed token is only valid while this script is running.
"""

import base64
import http.server
import json
import os
import socket
import sys
import threading
import time
from datetime import UTC, datetime

try:
    import jwt as pyjwt
    from cryptography.hazmat.primitives.asymmetric.ec import (
        SECP256R1,
        generate_private_key,
    )
except ImportError:
    print(
        "ERROR: cryptography and PyJWT are required.\n       pip install cryptography PyJWT",
        file=sys.stderr,
    )
    sys.exit(1)


PORT = int(os.environ.get("DEV_JWKS_PORT", "8001"))
ISSUER = f"http://127.0.0.1:{PORT}"
BIND_HOST = "127.0.0.1"
AUDIENCE = "sre-bot-dev"
SUBJECT = "dev-user"
EMAIL = os.environ.get("DEV_TOKEN_EMAIL", "dev@local")
SCOPE = "sre-bot:access-sync sre-bot:access-catalog sre-bot:access-requests"
TTL_SECONDS = 3600


def _int_to_bytes(n: int) -> bytes:
    length = (n.bit_length() + 7) // 8
    return n.to_bytes(length, "big")


def generate_keypair():
    """Generate an EC P-256 key pair and return (private_key, JWK dict)."""
    private_key = generate_private_key(SECP256R1())
    pub = private_key.public_key()
    pub_numbers = pub.public_numbers()

    def _b64url_int(n: int) -> str:
        raw = _int_to_bytes(n).rjust(32, b"\x00")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    jwk = {
        "kty": "EC",
        "crv": "P-256",
        "use": "sig",
        "alg": "ES256",
        "kid": "dev-key-1",
        "x": _b64url_int(pub_numbers.x),
        "y": _b64url_int(pub_numbers.y),
    }
    return private_key, jwk


def mint_token(private_key, kid: str = "dev-key-1") -> str:
    now = int(datetime.now(UTC).timestamp())
    payload = {
        "iss": ISSUER,
        "sub": SUBJECT,
        "aud": AUDIENCE,
        "email": EMAIL,
        "name": "Dev User",
        "scope": SCOPE,
        "iat": now,
        "exp": now + TTL_SECONDS,
    }
    token = pyjwt.encode(
        payload,
        private_key,
        algorithm="ES256",
        headers={"kid": kid},
    )
    return token


def _check_port_free(port: int) -> None:
    """Exit immediately if the port is already in use."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((BIND_HOST, port))
        except OSError:
            print(
                f"\nERROR: Port {port} is already in use.\n"
                f"       A previous dev-token.py is still running.\n"
                f"       Kill it first:\n"
                f"         kill $(lsof -ti tcp:{port})\n"
                f"       Then re-run this script.",
                file=sys.stderr,
            )
            sys.exit(1)


def make_jwks_server(jwk: dict, port: int) -> http.server.HTTPServer:
    """Create (but do not start) the JWKS HTTP server."""
    jwks_response = json.dumps({"keys": [jwk]}).encode()

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/.well-known/jwks.json", "/jwks.json"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(jwks_response)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, fmt, *args):
            pass  # silence access logs

    # Subclass so allow_reuse_address is set before server_bind() is called
    # in HTTPServer.__init__. Setting it as an instance attribute after
    # construction is too late — the socket has already been bound.
    class _Server(http.server.HTTPServer):
        allow_reuse_address = True

    return _Server((BIND_HOST, port), _Handler)


def main() -> None:
    _check_port_free(PORT)

    private_key, jwk = generate_keypair()
    token = mint_token(private_key)

    server = make_jwks_server(jwk, PORT)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.1)  # let the server finish binding

    issuer_config = json.dumps(
        {
            ISSUER: {
                "jwks_uri": f"{ISSUER}/.well-known/jwks.json",
                "algorithms": ["ES256"],
                "audience": AUDIENCE,
            }
        }
    )

    print()
    print("=" * 70)
    print("  Local JWKS server running on port", PORT)
    print("=" * 70)
    print()
    print("1. Add this to your .env (replace any existing ISSUER_CONFIG):")
    print()
    print(f"   ISSUER_CONFIG='{issuer_config}'")
    print()
    print("2. Start the app in another terminal:")
    print()
    print("   make dev")
    print()
    print("3. Smoke test the access-sync endpoint:")
    print()
    print("   curl -s -X POST http://localhost:8000/api/v1/access/sync-runs \\")
    print(f'     -H "Authorization: Bearer {token}" \\')
    print('     -H "Content-Type: application/json" \\')
    print("""     -d '{"sync_type":"platform","platform":"aws","dry_run":true}'""")
    print()
    print(f"   Token expires in {TTL_SECONDS // 60} minutes.")
    print("   Press Ctrl-C to stop the JWKS server (token becomes invalid).")
    print("=" * 70)
    print()
    print(f"{token}")
    print()
    print("=" * 70)
    print()

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.shutdown()  # stops serve_forever()
        server.server_close()  # closes the socket — port released immediately
        print("\nJWKS server stopped.")


if __name__ == "__main__":
    main()
