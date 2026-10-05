import sys

import boto3


if len(sys.argv) != 3:
    raise SystemExit("Usage: python terminate_builder.py <instance_id> <region>")

instance_id = sys.argv[1]
region = sys.argv[2]

ec2 = boto3.client("ec2", region_name=region)

ec2.terminate_instances(
    InstanceIds=[instance_id]
)

print(f"Termination requested for builder instance {instance_id}.")