import sys
import time
import io

import boto3
import botocore

# Configure stdout/stderr for UTF-8 to prevent UnicodeEncodeError on Windows.
# This allows diagnostic output to print safely even if it contains Unicode.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
else:
    # Fallback for older Python versions
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


if len(sys.argv) != 4:
    raise SystemExit(
        "Usage: python wait_for_builder_ready.py <bucket_name> <instance_id> <region>"
    )

bucket_name = sys.argv[1]
instance_id = sys.argv[2]
region = sys.argv[3]

READY_KEY = f"golden-image-ready/{instance_id}"
FAILED_KEY = f"golden-image-failed/{instance_id}"
DEADLINE_SECONDS = 1800

s3 = boto3.client("s3", region_name=region)
deadline = time.time() + DEADLINE_SECONDS


def is_not_found(exc):
    code = exc.response.get("Error", {}).get("Code")
    return code in ("404", "NoSuchKey", "NotFound")


print(f"Waiting for golden image readiness marker s3://{bucket_name}/{READY_KEY}")

while time.time() < deadline:
    try:
        s3.head_object(Bucket=bucket_name, Key=READY_KEY)
        print("Golden image readiness marker found in S3.")
        print(f"Builder {instance_id} is ready.")
        break

    except botocore.exceptions.ClientError as exc:
        if not is_not_found(exc):
            raise

        try:
            obj = s3.get_object(Bucket=bucket_name, Key=FAILED_KEY)
            details = obj["Body"].read().decode("utf-8", errors="replace")
            print("Golden image build FAILED on the instance:")
            print(details)
            raise SystemExit(
                f"Builder {instance_id} reported a failure. "
                f"See s3://{bucket_name}/{FAILED_KEY} for the full log tail."
            )
        except botocore.exceptions.ClientError as fexc:
            if not is_not_found(fexc):
                raise
            print("Readiness marker not present yet.")
            time.sleep(10)
            continue
else:
    raise SystemExit("Timed out waiting for golden image readiness marker in S3.")