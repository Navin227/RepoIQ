import os
import json
import uuid
import time
from datetime import datetime, timezone, timedelta
import boto3


def lambda_handler(event, context):
    print("Start Controller invoked:", json.dumps(event))
    start_time_epoch = time.time()

    project_name = os.environ.get("PROJECT_NAME", "RepoIQ")
    environment = os.environ.get("ENVIRONMENT", "dev")
    ami_id = os.environ.get("AMI_ID")
    instance_type = os.environ.get("INSTANCE_TYPE", "t3.small")
    subnet_id = os.environ.get("SUBNET_ID")
    security_group_id = os.environ.get("SECURITY_GROUP_ID")
    instance_profile_name = os.environ.get("INSTANCE_PROFILE_NAME")
    key_name = os.environ.get("KEY_NAME")
    root_volume_size = int(os.environ.get("ROOT_VOLUME_SIZE", "20"))
    root_volume_type = os.environ.get("ROOT_VOLUME_TYPE", "gp3")
    stop_lambda_arn = os.environ.get("STOP_LAMBDA_ARN")
    scheduler_role_arn = os.environ.get("SCHEDULER_ROLE_ARN")

    body = {}
    if event.get("body"):
        try:
            body = json.loads(event["body"])
        except Exception:
            pass

    duration = body.get("duration", 30)
    if duration not in [30, 45, 60]:
        error_msg = "Invalid duration. Allowed values are 30, 45, or 60 minutes only."
        print(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "start",
            "duration": duration,
            "result": "failed",
            "error": error_msg,
        }))
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "InvalidDuration", "message": error_msg}),
        }

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
            "action": "start",
            "duration": duration,
            "result": "failed",
            "error": str(exc),
        }))
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "AWSSDKFailure", "message": str(exc)}),
        }

    existing_instance = None
    for reservation in response.get("Reservations", []):
        for instance in reservation.get("Instances", []):
            state_name = instance.get("State", {}).get("Name", "")
            # Only reusable if actively pending or running
            if state_name in ["pending", "running"]:
                existing_instance = instance
                break
        if existing_instance:
            break

    if existing_instance:
        instance_id = existing_instance.get("InstanceId")
        state_name = existing_instance.get("State", {}).get("Name", "")
        public_ip = existing_instance.get("PublicIpAddress")

        session_id = str(uuid.uuid4())
        schedule_name = f"repoiq-stop-{session_id}"
        now_utc = datetime.now(timezone.utc)
        end_time_utc = now_utc + timedelta(minutes=duration)
        schedule_expression = f"at({end_time_utc.strftime('%Y-%m-%dT%H:%M:%S')})"

        try:
            scheduler.create_schedule(
                Name=schedule_name,
                ScheduleExpression=schedule_expression,
                FlexibleTimeWindow={"Mode": "OFF"},
                Target={
                    "Arn": stop_lambda_arn,
                    "RoleArn": scheduler_role_arn,
                    "Input": json.dumps({"session_id": session_id}),
                },
                ActionAfterCompletion="DELETE",
            )
        except Exception as exc:
            print(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "start",
                "instance_id": instance_id,
                "session_id": session_id,
                "duration": duration,
                "result": "failed",
                "error": str(exc),
            }))
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "SchedulerCreationFailure", "message": str(exc)}),
            }

        print(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "start",
            "instance_id": instance_id,
            "duration": duration,
            "result": "success",
            "ec2_state": state_name,
            "message": "RepoIQ demo instance already exists",
        }))
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "state": state_name,
                "status": state_name,
                "instance_id": instance_id,
                "message": "RepoIQ infrastructure is already running" if state_name == "running" else "RepoIQ infrastructure is starting",
                "public_ip": public_ip,
                "session_id": session_id,
                "start_time": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_time": end_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "duration": duration,
            }),
        }

    run_kwargs = {
        "ImageId": ami_id,
        "InstanceType": instance_type,
        "MinCount": 1,
        "MaxCount": 1,
        "SubnetId": subnet_id,
        "SecurityGroupIds": [security_group_id],
        "IamInstanceProfile": {"Name": instance_profile_name},
        "BlockDeviceMappings": [{
            "DeviceName": "/dev/sda1",
            "Ebs": {
                "VolumeSize": root_volume_size,
                "VolumeType": root_volume_type,
                "DeleteOnTermination": True,
            },
        }],
        "TagSpecifications": [{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "Project", "Value": project_name},
                {"Key": "Environment", "Value": environment},
                {"Key": "ManagedBy", "Value": "RepoIQ-ControlPlane"},
                {"Key": "Role", "Value": "Demo"},
                {"Key": "Name", "Value": "RepoIQ-demo"},
            ],
        }],
    }
    if key_name:
        run_kwargs["KeyName"] = key_name

    try:
        run_response = ec2.run_instances(**run_kwargs)
    except Exception as exc:
        print(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "start",
            "duration": duration,
            "result": "failed",
            "error": str(exc),
        }))
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "AWSSDKFailure", "message": str(exc)}),
        }

    instance = run_response["Instances"][0]
    instance_id = instance["InstanceId"]

    session_id = str(uuid.uuid4())
    schedule_name = f"repoiq-stop-{session_id}"
    now_utc = datetime.now(timezone.utc)
    end_time_utc = now_utc + timedelta(minutes=duration)
    schedule_expression = f"at({end_time_utc.strftime('%Y-%m-%dT%H:%M:%S')})"

    try:
        scheduler.create_schedule(
            Name=schedule_name,
            ScheduleExpression=schedule_expression,
            FlexibleTimeWindow={"Mode": "OFF"},
            Target={
                "Arn": stop_lambda_arn,
                "RoleArn": scheduler_role_arn,
                "Input": json.dumps({"session_id": session_id}),
            },
            ActionAfterCompletion="DELETE",
        )
    except Exception as exc:
        try:
            ec2.terminate_instances(InstanceIds=[instance_id])
        except Exception:
            pass
        print(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "start",
            "instance_id": instance_id,
            "session_id": session_id,
            "duration": duration,
            "result": "failed",
            "error": str(exc),
        }))
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "SchedulerCreationFailure", "message": str(exc)}),
        }

    print(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "start",
        "instance_id": instance_id,
        "session_id": session_id,
        "duration": duration,
        "result": "success",
        "status": "pending",
    }))

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "status": "pending",
            "instance_id": instance_id,
            "message": "RepoIQ infrastructure is starting",
            "public_ip": None,
            "session_id": session_id,
            "start_time": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": end_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }),
    }
