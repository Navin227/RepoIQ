import os
import json
import socket
import urllib.request
import urllib.error
from datetime import datetime, timezone


RESPONSE_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Admin-Token",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}

HEALTH_CHECK_TIMEOUT_SECONDS = 3
INIT_STAGE_S3_PREFIX = os.environ.get(
    "REPOIQ_INIT_STAGE_PREFIX",
    "artifacts/demo-init",
)
INIT_STAGE_ARTIFACTS_BUCKET = os.environ.get(
    "REPOIQ_ARTIFACTS_BUCKET",
)


def read_s3_json_or_none(bucket, key):
    if not bucket or not key:
        return None
    s3 = boto3_client_safe("s3")
    if s3 is None:
        return None
    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
        body = resp.get("Body")
        if body is None:
            return None
        raw = body.read()
        if not raw:
            return None
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        error_type = type(exc).__name__
        error_code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        error_message = getattr(exc, "response", {}).get("Error", {}).get("Message") or str(exc)
        print(
            json.dumps(
                {
                    "action": "s3_get_object",
                    "bucket": bucket,
                    "key": key,
                    "error_type": error_type,
                    "error_code": error_code,
                    "error_message": error_message,
                }
            )
        )
        if error_code in {"NoSuchKey", "404"}:
            return {"_error": {"code": error_code, "message": "stage.json not found"}}
        if error_code in {"AccessDenied", "Forbidden"}:
            return {"_error": {"code": error_code, "message": "Access denied reading stage.json"}}
        return {"_error": {"code": error_code or error_type, "message": error_message}}


def fetch_init_stages(instance_id):
    if not instance_id or not INIT_STAGE_ARTIFACTS_BUCKET:
        return None
    key = f"{INIT_STAGE_S3_PREFIX}/{instance_id}/stage.json"
    payload = read_s3_json_or_none(INIT_STAGE_ARTIFACTS_BUCKET, key)
    if not isinstance(payload, dict):
        return None
    if payload.get("_error"):
        error = payload["_error"]
        error_msg = f"{error.get('code', 'UnknownS3Error')}: {error.get('message', 'unknown S3 error')}"
        return {
            "state": "unknown",
            "status": "unknown",
            "stage_name": None,
            "message": "Initialization telemetry unavailable.",
            "completed_stages": [],
            "logs": [],
            "error": error_msg,
            "telemetry": {
                "available": False,
                "source": "s3",
                "bucket": INIT_STAGE_ARTIFACTS_BUCKET,
                "key": key,
                "last_updated": None,
                "error": error_msg,
            },
        }
    if "telemetry" not in payload:
        payload["telemetry"] = {
            "available": True,
            "source": "s3",
            "bucket": INIT_STAGE_ARTIFACTS_BUCKET,
            "key": key,
            "last_updated": payload.get("timestamp"),
            "error": None,
        }
    return payload


def normalize_stage_payload(stage_payload):
    if not isinstance(stage_payload, dict):
        stage_payload = {}

    raw_state = stage_payload.get("state") or stage_payload.get("status")
    normalized_state = str(raw_state or "unknown").strip().lower()

    if normalized_state in {"failed", "error", "failure"}:
        init_state = "failed"
    elif normalized_state in {"completed", "ready", "success"}:
        init_state = "ready"
    elif normalized_state in {"running", "starting", "initializing", "pending", "in_progress", "active"}:
        init_state = "initializing"
    elif stage_payload.get("stage_name") or stage_payload.get("stage"):
        init_state = "initializing"
    else:
        init_state = "unknown"

    stage_name = (
        stage_payload.get("stage_name")
        or stage_payload.get("stage")
        or stage_payload.get("current_stage")
        or None
    )

    message = (
        stage_payload.get("message")
        or stage_payload.get("detail")
        or stage_payload.get("status_message")
        or None
    )

    completed_stages = stage_payload.get("completed_stages") or []
    if isinstance(completed_stages, str):
        completed_stages = [completed_stages]
    elif not isinstance(completed_stages, list):
        completed_stages = []

    logs = stage_payload.get("logs") or []
    if not isinstance(logs, list):
        logs = []

    telemetry = stage_payload.get("telemetry") or {
        "available": True,
        "source": "s3",
        "key": None,
        "last_updated": stage_payload.get("timestamp"),
        "error": None,
    }
    if not isinstance(telemetry, dict):
        telemetry = {
            "available": True,
            "source": "s3",
            "key": None,
            "last_updated": stage_payload.get("timestamp"),
            "error": None,
        }

    return {
        "state": init_state,
        "status": normalized_state,
        "stage": stage_name,
        "stage_name": stage_name,
        "message": message,
        "completed_stages": completed_stages,
        "logs": logs,
        "error": stage_payload.get("error") or stage_payload.get("failure") or None,
        "telemetry": {
            "available": bool(telemetry.get("available", True)),
            "source": telemetry.get("source") or "s3",
            "key": telemetry.get("key"),
            "last_updated": telemetry.get("last_updated"),
            "error": telemetry.get("error"),
        },
    }


def build_status_response(instance, stage_payload, health_result, project_name, environment):
    if not isinstance(instance, dict):
        instance = {}

    state = str(instance.get("State", {}).get("Name") or "").strip().lower()
    instance_id = instance.get("InstanceId")
    public_ip = instance.get("PublicIpAddress")
    private_ip = instance.get("PrivateIpAddress")
    launch_time = instance.get("LaunchTime")
    application_url = f"http://{public_ip}" if public_ip else None

    initialization = normalize_stage_payload(stage_payload)
    telemetry = initialization.get("telemetry") or {
        "available": True,
        "source": "s3",
        "key": None,
        "last_updated": None,
        "error": None,
    }
    health_reason = health_result.get("reason") if isinstance(health_result, dict) else None
    message = initialization.get("message") or health_reason
    if not message:
        message = "RepoIQ demo instance is starting."

    if state == "terminated":
        return {
            "state": "terminated",
            "status": "offline",
            "health": "offline",
            "instance_id": instance_id,
            "public_ip": None,
            "private_ip": None,
            "launch_time": launch_time.isoformat() if launch_time else None,
            "application_url": None,
            "readiness": {"state": "offline"},
            "initialization": {
                "state": "stopped",
                "stage": None,
                "stage_name": None,
                "message": "RepoIQ demo infrastructure is terminated.",
                "completed_stages": [],
                "logs": [],
                "error": None,
            },
            "telemetry": {
                "available": False,
                "source": "s3",
                "key": None,
                "last_updated": None,
                "error": None,
            },
            "message": "RepoIQ demo infrastructure is terminated.",
            "error": None,
        }

    if state in {"stopped", "stopping", "shutting-down"}:
        response_state = "shutting-down" if state == "shutting-down" else state
        health_value = "unknown" if state == "stopped" else "stopping"
        readiness_state = "stopped" if state == "stopped" else "stopping"
        return {
            "state": response_state,
            "status": "stopped" if state == "stopped" else "stopping",
            "health": health_value,
            "instance_id": instance_id,
            "public_ip": public_ip if state != "shutting-down" else None,
            "private_ip": private_ip if state != "shutting-down" else None,
            "launch_time": launch_time.isoformat() if launch_time else None,
            "application_url": application_url if state not in {"stopped", "shutting-down"} else None,
            "readiness": {"state": readiness_state},
            "initialization": {
                "state": "stopped" if state == "stopped" else "stopping",
                "stage": initialization.get("stage"),
                "stage_name": initialization.get("stage_name"),
                "message": message,
                "completed_stages": initialization.get("completed_stages", []),
                "logs": initialization.get("logs", []),
                "error": initialization.get("error"),
            },
            "telemetry": telemetry,
            "message": message,
            "error": initialization.get("error"),
        }

    if state == "pending":
        return {
            "state": "pending",
            "status": "starting",
            "health": "starting",
            "instance_id": instance_id,
            "public_ip": public_ip,
            "private_ip": private_ip,
            "launch_time": launch_time.isoformat() if launch_time else None,
            "application_url": application_url,
            "readiness": {"state": "starting"},
            "initialization": {
                **initialization,
                "state": "initializing",
            },
            "telemetry": telemetry,
            "message": message,
            "error": initialization.get("error"),
        }

    if state == "running":
        if initialization.get("state") == "failed":
            failure_message = initialization.get("message") or "K3s initialization failed."
            return {
                "state": "running",
                "status": "failed",
                "health": "failed",
                "instance_id": instance_id,
                "public_ip": public_ip,
                "private_ip": private_ip,
                "launch_time": launch_time.isoformat() if launch_time else None,
                "application_url": application_url,
                "readiness": {
                    "state": "failed",
                    "message": failure_message,
                    "health_check": health_result if isinstance(health_result, dict) else {"healthy": False},
                },
                "initialization": {
                    **initialization,
                    "state": "failed",
                    "message": failure_message,
                },
                "telemetry": telemetry,
                "message": failure_message,
                "error": initialization.get("error") or failure_message,
            }

        if initialization.get("state") == "ready" and health_result.get("healthy"):
            return {
                "state": "running",
                "status": "running",
                "health": "healthy",
                "instance_id": instance_id,
                "public_ip": public_ip,
                "private_ip": private_ip,
                "launch_time": launch_time.isoformat() if launch_time else None,
                "application_url": application_url,
                "readiness": {
                    "state": "ready",
                    "health_check": health_result if isinstance(health_result, dict) else {"healthy": True},
                },
                "initialization": {
                    **initialization,
                    "state": "ready",
                    "message": initialization.get("message") or "RepoIQ application ready.",
                },
                "telemetry": telemetry,
                "message": initialization.get("message") or "RepoIQ application ready.",
                "error": None,
            }

        if initialization.get("state") in {"initializing", "unknown"}:
            status_value = "starting"
            health_value = "starting"
            readiness_value = "starting"
            readiness_payload = {
                "state": readiness_value,
                "health_check": health_result if isinstance(health_result, dict) else {"healthy": False},
            }
            if health_result.get("healthy"):
                status_value = "running"
                health_value = "healthy"
                readiness_value = "ready"
                readiness_payload = {
                    "state": readiness_value,
                    "health_check": health_result,
                }
            return {
                "state": "running",
                "status": status_value,
                "health": health_value,
                "instance_id": instance_id,
                "public_ip": public_ip,
                "private_ip": private_ip,
                "launch_time": launch_time.isoformat() if launch_time else None,
                "application_url": application_url,
                "readiness": readiness_payload,
                "initialization": {
                    **initialization,
                    "state": "initializing" if readiness_value == "starting" else "ready",
                },
                "telemetry": telemetry,
                "message": initialization.get("message") or message,
                "error": initialization.get("error"),
            }

    return {
        "state": state or "unknown",
        "status": "starting",
        "health": "starting",
        "instance_id": instance_id,
        "public_ip": public_ip,
        "private_ip": private_ip,
        "launch_time": launch_time.isoformat() if launch_time else None,
        "application_url": application_url,
        "readiness": {"state": "starting"},
        "initialization": {
            **initialization,
            "state": initialization.get("state") or "initializing",
        },
        "telemetry": initialization.get("telemetry") or {
            "available": True,
            "source": "s3",
            "key": None,
            "last_updated": None,
            "error": None,
        },
        "message": message,
        "error": initialization.get("error"),
    }


def json_response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": RESPONSE_HEADERS,
        "body": json.dumps(payload),
    }


def run_http_health_check(public_ip):
    if not public_ip:
        return {
            "healthy": False,
            "reason": "no_public_ip",
        }

    url = f"http://{public_ip}/health"

    original_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(HEALTH_CHECK_TIMEOUT_SECONDS)

    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as resp:
            http_status = resp.getcode()
            if http_status == 200:
                return {
                    "healthy": True,
                    "http_status": http_status,
                }
            return {
                "healthy": False,
                "http_status": http_status,
                "reason": "non_200",
            }
    except urllib.error.HTTPError as exc:
        return {
            "healthy": False,
            "http_status": exc.code,
            "reason": "http_error",
        }
    except urllib.error.URLError as exc:
        reason_str = str(exc.reason)
        if "Connection refused" in reason_str:
            reason = "connection_refused"
        elif "timed out" in reason_str or "timeout" in reason_str.lower():
            reason = "timeout"
        elif "Name or service not known" in reason_str or "getaddrinfo" in reason_str:
            reason = "dns_error"
        else:
            reason = "url_error"
        return {
            "healthy": False,
            "reason": reason,
            "detail": reason_str[:200],
        }
    except (TimeoutError, socket.timeout) as exc:
        return {
            "healthy": False,
            "reason": "timeout",
            "detail": str(exc)[:200],
        }
    except ConnectionRefusedError as exc:
        return {
            "healthy": False,
            "reason": "connection_refused",
            "detail": str(exc)[:200],
        }
    except OSError as exc:
        return {
            "healthy": False,
            "reason": "network_error",
            "detail": str(exc)[:200],
        }
    except Exception as exc:
        return {
            "healthy": False,
            "reason": "unexpected_error",
            "detail": str(exc)[:200],
        }
    finally:
        socket.setdefaulttimeout(original_timeout)


def lambda_handler(event, context):
    project_name = os.environ.get(
        "PROJECT_NAME",
        "RepoIQ",
    )

    environment = os.environ.get(
        "ENVIRONMENT",
        "dev",
    )

    ec2 = boto3_client_safe("ec2")
    if ec2 is None:
        return json_response(
            200,
            {
                "state": "offline",
                "status": "offline",
                "health": "unavailable",
                "instance_id": None,
                "public_ip": None,
                "private_ip": None,
                "launch_time": None,
                "application_url": None,
                "readiness": {
                    "state": "unknown"
                },
                "error": "AWSSDKFailure",
                "message": (
                    "Demo control plane is temporarily unavailable."
                ),
            },
        )

    try:
        response = ec2.describe_instances(
            Filters=[
                {
                    "Name": "tag:Project",
                    "Values": [project_name],
                },
                {
                    "Name": "tag:Environment",
                    "Values": [environment],
                },
            ]
        )

        print(
            json.dumps(
                {
                    "DEBUG_REGION": ec2.meta.region_name,
                    "DEBUG_PROJECT_NAME": project_name,
                    "DEBUG_ENVIRONMENT": environment,
                    "DEBUG_RESERVATION_COUNT": len(
                        response.get("Reservations", [])
                    ),
                }
            )
        )

    except Exception as exc:
        print(
            json.dumps(
                {
                    "action": "describe_instances",
                    "error": str(exc),
                    "region": ec2.meta.region_name,
                    "project_name": project_name,
                    "environment": environment,
                }
            )
        )

        return json_response(
            200,
            {
                "state": "offline",
                "status": "offline",
                "health": "unavailable",
                "instance_id": None,
                "public_ip": None,
                "private_ip": None,
                "launch_time": None,
                "application_url": None,
                "readiness": {
                    "state": "unknown"
                },
                "error": "AWSSDKFailure",
                "message": (
                    "Demo control plane is temporarily unavailable."
                ),
            },
        )

    candidates = []

    for reservation in response.get(
        "Reservations",
        [],
    ):
        for candidate in reservation.get(
            "Instances",
            [],
        ):
            state = candidate.get(
                "State",
                {},
            ).get(
                "Name",
                "",
            )

            if state not in {
                "pending",
                "running",
                "stopping",
                "stopped",
                "shutting-down",
                "terminated",
            }:
                continue

            tags = {
                tag.get("Key"): tag.get("Value")
                for tag in candidate.get(
                    "Tags",
                    [],
                )
            }

            print(
                json.dumps(
                    {
                        "action": "candidate_instance",
                        "instance_id": candidate.get(
                            "InstanceId"
                        ),
                        "state": state,
                        "tags": tags,
                    }
                )
            )

            if tags.get("ManagedBy") != "RepoIQ-ControlPlane":
                continue

            if tags.get("Role") != "Demo":
                continue

            if tags.get("Name") != "RepoIQ-demo":
                continue

            candidates.append(candidate)

    print(
        json.dumps(
            {
                "action": "matched_instances",
                "count": len(candidates),
                "instances": [
                    {
                        "instance_id": c.get("InstanceId"),
                        "state": c.get(
                            "State",
                            {},
                        ).get("Name"),
                    }
                    for c in candidates
                ],
            }
        )
    )

    # Prioritize active / transitioning instances over terminated ones
    active_candidates = [
        c for c in candidates
        if c.get("State", {}).get("Name", "") in {"pending", "running", "stopping", "shutting-down"}
    ]
    if active_candidates:
        instance = max(
            active_candidates,
            key=lambda c: c.get("LaunchTime") or datetime.min.replace(tzinfo=timezone.utc),
        )
    elif candidates:
        instance = max(
            candidates,
            key=lambda c: c.get("LaunchTime") or datetime.min.replace(tzinfo=timezone.utc),
        )
    else:
        instance = None

    if not instance:
        return json_response(
            200,
            {
                "state": "stopped",
                "status": "stopped",
                "health": "unknown",
                "instance_id": None,
                "public_ip": None,
                "private_ip": None,
                "launch_time": None,
                "application_url": None,
                "readiness": {
                    "state": "offline"
                },
            },
        )

    state = instance.get(
        "State",
        {},
    ).get(
        "Name",
        "",
    )

    instance_id = instance.get(
        "InstanceId"
    )

    public_ip = instance.get(
        "PublicIpAddress"
    )

    private_ip = instance.get(
        "PrivateIpAddress"
    )

    launch_time = instance.get(
        "LaunchTime"
    )

    state_value = (
        "stopping"
        if state == "shutting-down"
        else state
    )

    application_url = (
        f"http://{public_ip}"
        if public_ip
        else None
    )

    stage_data = fetch_init_stages(instance_id)
    if state == "stopped":
        return json_response(
            200,
            build_status_response(
                instance,
                stage_data,
                {"healthy": False, "reason": "ec2_stopped"},
                project_name,
                environment,
            ),
        )

    if state == "pending":
        return json_response(
            200,
            build_status_response(
                instance,
                stage_data,
                {"healthy": False, "reason": "instance_pending"},
                project_name,
                environment,
            ),
        )

    if state in ("stopping", "shutting-down"):
        return json_response(
            200,
            build_status_response(
                instance,
                stage_data,
                {"healthy": False, "reason": "instance_stopping"},
                project_name,
                environment,
            ),
        )

    if state == "terminated":
        return json_response(
            200,
            build_status_response(
                instance,
                stage_data,
                {"healthy": False, "reason": "instance_terminated"},
                project_name,
                environment,
            ),
        )

    health_result = run_http_health_check(public_ip)

    print(
        json.dumps(
            {
                "action": "http_health_check",
                "instance_id": instance_id,
                "public_ip": public_ip,
                "result": health_result,
            }
        )
    )

    return json_response(
        200,
        build_status_response(
            instance,
            stage_data,
            health_result,
            project_name,
            environment,
        ),
    )


def boto3_client_safe(service):
    try:
        import boto3
        return boto3.client(service)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "action": "boto3_client_safe",
                    "service": service,
                    "error": str(exc),
                }
            )
        )
        return None
