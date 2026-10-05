#!/bin/bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
AWS_REGION="${aws_region}"
AWS_DEFAULT_REGION="${aws_region}"
export AWS_REGION AWS_DEFAULT_REGION

apt-get update -y
apt-get install -y ca-certificates curl awscli

BUCKET="${artifacts_bucket_name}"
SETUP_KEY="artifacts/builder_setup.sh"
SETUP_PATH="/tmp/builder_setup.sh"

echo "[bootstrap] Downloading builder setup from s3://$${BUCKET}/$${SETUP_KEY}" >&2

for attempt in 1 2 3 4 5; do
  if aws s3 cp "s3://$${BUCKET}/$${SETUP_KEY}" "$${SETUP_PATH}"; then
    break
  fi
  echo "[bootstrap] S3 download attempt $${attempt}/5 failed; retrying..." >&2
  sleep 5
done

if [ ! -s "$${SETUP_PATH}" ]; then
  echo "FATAL: Failed to download builder setup from s3://$${BUCKET}/$${SETUP_KEY}" >&2
  exit 1
fi

chmod +x "$${SETUP_PATH}"
echo "[bootstrap] Executing builder setup script" >&2
exec "$${SETUP_PATH}"
