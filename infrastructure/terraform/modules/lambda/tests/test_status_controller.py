import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "status_controller.py"
SPEC = importlib.util.spec_from_file_location("status_controller", MODULE_PATH)
status_controller = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(status_controller)


def test_normalize_stage_payload_handles_real_initialization_state() -> None:
    payload = status_controller.normalize_stage_payload(
        {
            "state": "initializing",
            "stage_name": "traefik_ready",
            "status": "running",
            "message": "Waiting for Traefik...",
            "completed_stages": [
                "k3s_started",
                "node_ready",
                "backend_ready",
            ],
            "logs": [
                {
                    "timestamp": "2025-01-01T00:00:00Z",
                    "level": "info",
                    "stage": "traefik",
                    "message": "[RepoIQ][K3s] Waiting for Traefik...",
                }
            ],
        }
    )

    assert payload["state"] == "initializing"
    assert payload["stage"] == "traefik_ready"
    assert payload["message"] == "Waiting for Traefik..."
    assert payload["completed_stages"] == [
        "k3s_started",
        "node_ready",
        "backend_ready",
    ]
    assert payload["logs"][0]["message"].startswith("[RepoIQ][K3s]")


def test_build_status_response_uses_initialization_when_ec2_is_running() -> None:
    response = status_controller.build_status_response(
        {
            "InstanceId": "i-123",
            "PublicIpAddress": "203.0.113.5",
            "PrivateIpAddress": "10.0.0.42",
            "LaunchTime": None,
            "State": {"Name": "running"},
        },
        {
            "state": "initializing",
            "stage_name": "traefik_ready",
            "status": "running",
            "message": "Waiting for Traefik...",
            "completed_stages": ["k3s_started", "node_ready"],
            "logs": [{"message": "[RepoIQ][K3s] Waiting for Traefik..."}],
        },
        {"healthy": False, "reason": "not_ready"},
        "RepoIQ",
        "dev",
    )

    assert response["state"] == "running"
    assert response["status"] == "starting"
    assert response["initialization"]["state"] == "initializing"
    assert response["initialization"]["stage"] == "traefik_ready"
    assert response["readiness"]["state"] == "starting"


def test_build_status_response_handles_shutting_down_instance() -> None:
    response = status_controller.build_status_response(
        {
            "InstanceId": "i-123",
            "PublicIpAddress": "203.0.113.5",
            "PrivateIpAddress": "10.0.0.42",
            "LaunchTime": None,
            "State": {"Name": "shutting-down"},
        },
        {},
        {"healthy": False, "reason": "instance_stopping"},
        "RepoIQ",
        "dev",
    )

    assert response["state"] == "shutting-down"
    assert response["status"] == "stopping"
    assert response["health"] == "stopping"
    assert response["readiness"]["state"] == "stopping"
    assert response["application_url"] is None


def test_build_status_response_handles_terminated_instance() -> None:
    response = status_controller.build_status_response(
        {
            "InstanceId": "i-123",
            "PublicIpAddress": None,
            "PrivateIpAddress": None,
            "LaunchTime": None,
            "State": {"Name": "terminated"},
        },
        {},
        {"healthy": False, "reason": "instance_terminated"},
        "RepoIQ",
        "dev",
    )

    assert response["state"] == "terminated"
    assert response["status"] == "offline"
    assert response["health"] == "offline"
    assert response["readiness"]["state"] == "offline"
    assert response["application_url"] is None
