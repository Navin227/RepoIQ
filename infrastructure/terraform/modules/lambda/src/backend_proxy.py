import base64
import json
import logging
import os
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import boto3
from botocore.exceptions import BotoCoreError, ClientError


logger = logging.getLogger()
logger.setLevel(logging.INFO)

ec2 = boto3.client("ec2")

PROJECT_NAME = os.environ.get("PROJECT_NAME", "RepoIQ")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "80"))
STANDARD_TIMEOUT_SECONDS = 30
ANALYSIS_TIMEOUT_SECONDS = 840


def _response(status_code: int, body: dict | str, content_type: str = "application/json") -> dict:
    if isinstance(body, dict):
        body = json.dumps(body)
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": content_type},
        "body": body,
    }


def _is_allowed_route(method: str, path: str) -> bool:
    if method == "GET" and path in {"/health", "/search"}:
        return True
    if method == "POST" and path == "/analyze":
        return True
    return method == "GET" and (
        path == "/api/repositories"
        or re.fullmatch(r"/api/repositories/[0-9]+", path) is not None
    )


def _running_instance_public_ip() -> str | None:
    demo_filters = [
        {"Name": "tag:Project", "Values": [PROJECT_NAME]},
        {"Name": "tag:ManagedBy", "Values": ["RepoIQ-ControlPlane"]},
        {"Name": "tag:Role", "Values": ["Demo"]},
        {"Name": "tag:Name", "Values": ["RepoIQ-demo"]},
        {"Name": "instance-state-name", "Values": ["running"]},
    ]

    def find_instances(filters: list[dict]) -> list[dict]:
        response = ec2.describe_instances(Filters=filters)
        return [
            instance
            for reservation in response.get("Reservations", [])
            for instance in reservation.get("Instances", [])
        ]

    instances = find_instances(
        [{"Name": "tag:Environment", "Values": [ENVIRONMENT]}, *demo_filters]
    )
    if not instances:
        instances = find_instances(demo_filters)
        if instances:
            logger.warning(
                "Found running RepoIQ demo instance despite Environment tag mismatch "
                "(proxy_environment=%s).",
                ENVIRONMENT,
            )

    instances = [instance for instance in instances if instance.get("PublicIpAddress")]
    if not instances:
        return None
    if len(instances) > 1:
        instances.sort(key=lambda instance: instance.get("LaunchTime"), reverse=True)
        logger.warning("Multiple running RepoIQ demo instances found; using the newest instance.")
    return instances[0]["PublicIpAddress"]


def _request_body(event: dict) -> bytes | None:
    body = event.get("body")
    if body is None:
        return None
    if not isinstance(body, str):
        raise ValueError("Request body must be a string.")
    if event.get("isBase64Encoded"):
        return base64.b64decode(body, validate=True)
    return body.encode("utf-8")


def _forward_headers(event: dict) -> dict[str, str]:
    request_headers = event.get("headers") or {}
    allowed_headers = {"accept", "authorization", "content-type", "origin"}
    return {
        key: value
        for name, value in request_headers.items()
        if name.lower() in allowed_headers and isinstance(value, str)
        for key in [name]
    }


def _backend_response(upstream_response, status_code: int | None = None) -> dict:
    response_headers = upstream_response.headers
    content_type = response_headers.get("Content-Type", "application/json")
    body = upstream_response.read()
    try:
        decoded_body = body.decode("utf-8")
        is_base64_encoded = False
    except UnicodeDecodeError:
        decoded_body = base64.b64encode(body).decode("ascii")
        is_base64_encoded = True

    result = {
        "statusCode": status_code or upstream_response.status,
        "headers": {"Content-Type": content_type},
        "body": decoded_body,
    }
    if is_base64_encoded:
        result["isBase64Encoded"] = True
    for header in ("Cache-Control", "Retry-After"):
        if response_headers.get(header):
            result["headers"][header] = response_headers[header]
    return result


def lambda_handler(event, context):
    request_context = event.get("requestContext") or {}
    http = request_context.get("http") or {}
    method = str(http.get("method") or event.get("httpMethod") or "").upper()
    path = event.get("rawPath") or event.get("path") or ""

    if not _is_allowed_route(method, path):
        return _response(404, {"detail": "Backend route not found."})

    try:
        body = _request_body(event)
    except (ValueError, TypeError):
        return _response(400, {"detail": "Invalid request body."})

    try:
        public_ip = _running_instance_public_ip()
    except (BotoCoreError, ClientError):
        logger.exception("Failed to find the running RepoIQ demo instance.")
        return _response(502, {"detail": "Could not resolve the running RepoIQ backend."})

    if not public_ip:
        logger.error(
            "Backend unavailable: no running demo instance with a public IP matched "
            "proxy configuration (project=%s, environment=%s, route=%s).",
            PROJECT_NAME,
            ENVIRONMENT,
            path,
        )
        return _response(503, {"detail": "RepoIQ demo server is not running."})

    raw_query = event.get("rawQueryString") or ""
    url = f"http://{public_ip}:{BACKEND_PORT}{path}"
    if raw_query:
        url = f"{url}?{raw_query}"

    request = Request(
        url,
        data=body,
        headers=_forward_headers(event),
        method=method,
    )
    timeout = (
        ANALYSIS_TIMEOUT_SECONDS
        if method == "POST" and path == "/analyze"
        else STANDARD_TIMEOUT_SECONDS
    )

    try:
        with urlopen(request, timeout=timeout) as upstream_response:
            logger.info(
                "Backend request completed (method=%s, route=%s, upstream_status=%s).",
                method,
                path,
                upstream_response.status,
            )
            return _backend_response(upstream_response)
    except HTTPError as error:
        with error:
            logger.error(
                "Backend returned HTTP error (method=%s, route=%s, upstream_status=%s).",
                method,
                path,
                error.code,
            )
            return _backend_response(error, error.code)
    except URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            return _response(504, {"detail": "RepoIQ backend request timed out."})
        logger.error("RepoIQ backend connection failed: %s", error.reason)
        return _response(502, {"detail": "Could not connect to the RepoIQ backend."})
    except (TimeoutError, socket.timeout):
        return _response(504, {"detail": "RepoIQ backend request timed out."})
