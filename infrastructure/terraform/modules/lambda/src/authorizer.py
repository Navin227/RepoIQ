import os
import json


def lambda_handler(event, context):
    print("Authorizer invoked:", json.dumps(event))
    headers = event.get("headers", {})

    auth_header = headers.get("authorization") or headers.get("Authorization")
    admin_token = os.environ.get("ADMIN_TOKEN")

    if not auth_header or not admin_token:
        print("Authorization header or ADMIN_TOKEN environment variable is missing.")
        return {"isAuthorized": False}

    token = auth_header
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()

    if token == admin_token:
        print("Authorization successful.")
        return {"isAuthorized": True}

    print("Authorization failed: Token mismatch.")
    return {"isAuthorized": False}
