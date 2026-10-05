import os
import json
from datetime import datetime, timezone
import boto3


def lambda_handler(event, context):
    print("Stop Controller invoked:", json.dumps(event))
    project_name = os.environ.get("PROJECT_NAME", "RepoIQ")
    environment = os.environ.get("ENVIRONMENT", "dev")

    session_id = None
    if event.get("session_id"):
        session_id = event["session_id"]
    else:
        body = {}
        if event.get("body"):
            try:
                body = json.loads(event["body"])
            except Exception:
                pass
        session_id = body.get("session_id")

    ec2 = boto3.client("ec2")
    scheduler = boto3.client("scheduler")

    try:
        response = ec2.describe_instances(
            Filters=[
                {"Name": "tag:Project", "Values": [project_name]},
                {"Name": "tag:Environment", "Values": [environment]},
                {"Name": "tag:ManagedBy", "Values": ["RepoIQ-ControlPlane"]},
                {"Name": "tag:Role", "Values": ["Demo"]},
                {"Name": "tag:Name", "Values": ["RepoIQ-demo"]},
            ]
        )
    except Exception as exc:
        print(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "stop",
            "session_id": session_id,
            "result": "failed",
            "error": str(exc),
        }))
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "AWSSDKFailure", "message": str(exc)}),
        }

    instance_id = None
    # Prioritize active/stoppable instances
    for reservation in response.get("Reservations", []):
        for instance in reservation.get("Instances", []):
            state_name = instance.get("State", {}).get("Name", "")
            if state_name in ["pending", "running", "stopping", "stopped"]:
                instance_id = instance.get("InstanceId")
                break
        if instance_id:
            break

    # If no pending/running/stopping/stopped instance, check if one is currently shutting-down
    if not instance_id:
        for reservation in response.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                state_name = instance.get("State", {}).get("Name", "")
                if state_name == "shutting-down":
                    instance_id = instance.get("InstanceId")
                    break
            if instance_id:
                break

    if not instance_id:
        print(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "stop",
            "session_id": session_id,
            "result": "success",
            "message": "No active RepoIQ demo instance found",
        }))
        if session_id:
            schedule_name = f"repoiq-stop-{session_id}"
            try:
                scheduler.delete_schedule(Name=schedule_name)
            except scheduler.exceptions.ResourceNotFoundException:
                pass
            except Exception as exc:
                print(f"Warning: failed to delete schedule {schedule_name}: {exc}")
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"status": "offline", "state": "terminated", "message": "RepoIQ demo infrastructure is already offline"}),
        }

    print(f"Terminating EC2 instance {instance_id}")
    try:
        ec2.terminate_instances(InstanceIds=[instance_id])
        print("EC2 termination initiated")
    except Exception as exc:
        print(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "terminate",
            "instance_id": instance_id,
            "session_id": session_id,
            "result": "failed",
            "error": str(exc),
        }))
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "AWSSDKFailure", "message": str(exc)}),
        }

    if session_id:
        schedule_name = f"repoiq-stop-{session_id}"
        try:
            scheduler.delete_schedule(Name=schedule_name)
        except scheduler.exceptions.ResourceNotFoundException:
            print(f"Schedule {schedule_name} not found. Skipping cleanup.")
        except Exception as exc:
            print(f"Warning: failed to delete schedule {schedule_name}: {exc}")

    print(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "terminate",
        "instance_id": instance_id,
        "session_id": session_id,
        "result": "success",
        "message": "RepoIQ demo infrastructure is shutting down (terminating)",
    }))

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "state": "shutting-down",
            "status": "terminating",
            "instance_id": instance_id,
            "message": "RepoIQ demo infrastructure is shutting down",
        }),
    }
