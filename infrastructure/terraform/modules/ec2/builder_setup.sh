#!/bin/bash
set -Eeuo pipefail

export DEBIAN_FRONTEND=noninteractive
AWS_REGION="${aws_region}"
AWS_DEFAULT_REGION="${aws_region}"

export AWS_REGION
export AWS_DEFAULT_REGION

READY_DIR="/var/lib/repoiq"
READY_FILE="$${READY_DIR}/golden-image-ready"
LOG_DIR="/var/log/repoiq"
REPOIQ_ETC="/etc/repoiq"
LOG_FILE="/var/log/cloud-init-output.log"

mkdir -p "$${READY_DIR}" "$${LOG_DIR}" "$${REPOIQ_ETC}"
chmod 0755 "$${READY_DIR}" "$${LOG_DIR}" "$${REPOIQ_ETC}"
echo "${artifacts_bucket_name}" > "$${REPOIQ_ETC}/artifacts_bucket"
echo "${aws_region}" > "$${REPOIQ_ETC}/aws_region"
chmod 0644 "$${REPOIQ_ETC}/artifacts_bucket" "$${REPOIQ_ETC}/aws_region"

echo "AWS CLI present: $(aws --version)" >&2

# ---------------------------------------------------------------------------
# Get EC2 instance ID from IMDSv2
# ---------------------------------------------------------------------------
METADATA_BASE_URL="http://169.254.169.254/latest"

get_instance_id() {
  local token

  token="$(curl -fsS -X PUT "$${METADATA_BASE_URL}/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")"

  curl -fsS \
    -H "X-aws-ec2-metadata-token: $${token}" \
    "$${METADATA_BASE_URL}/meta-data/instance-id"
}

INSTANCE_ID=""

for attempt in 1 2 3 4 5; do
  if INSTANCE_ID="$(get_instance_id)"; then
    break
  fi

  echo "IMDS not ready yet (attempt $${attempt}/5), retrying..." >&2
  sleep 5
done

if [ -z "$${INSTANCE_ID}" ]; then
  echo "FATAL: Could not resolve instance ID from IMDS" >&2
  exit 1
fi

echo "Instance ID: $${INSTANCE_ID}" >&2

BUCKET="${artifacts_bucket_name}"

READY_S3_KEY="golden-image-ready/$${INSTANCE_ID}"
FAILED_S3_KEY="golden-image-failed/$${INSTANCE_ID}"

# ---------------------------------------------------------------------------
# Failure reporting
# ---------------------------------------------------------------------------
on_error() {
  local exit_code=$?
  local line_no="$${1:-unknown}"

  {
    echo "RepoIQ golden image build FAILED"
    echo "instance_id=$${INSTANCE_ID}"
    echo "failed_at_line=$${line_no}"
    echo "exit_code=$${exit_code}"
    echo "---- tail of $${LOG_FILE} ----"
    tail -n 200 "$${LOG_FILE}" 2>/dev/null || echo "(log unavailable)"
  } > /tmp/golden-image-failure.txt 2>/dev/null || true

  if aws s3 cp \
    /tmp/golden-image-failure.txt \
    "s3://$${BUCKET}/$${FAILED_S3_KEY}"; then
    echo "[RepoIQ][GoldenImage][WARN] Golden image build failed and telemetry upload succeeded." >&2
  else
    local upload_exit_code=$?
    echo "[RepoIQ][GoldenImage][ERROR] Failed to upload golden image failure telemetry to S3 bucket=$${BUCKET} key=$${FAILED_S3_KEY} exit_code=$${upload_exit_code}" >&2
  fi
}

trap 'on_error $LINENO' ERR

# ---------------------------------------------------------------------------
# Install base dependencies
# ---------------------------------------------------------------------------
echo "Installing base system dependencies..." >&2

apt-get install -y \
  wget \
  unzip \
  git \
  software-properties-common \
  python3 \
  python3-pip \
  python3-venv \
  python3-dev \
  build-essential \
  libpq-dev

# Ubuntu 22.04 ships Python 3.10 as its default runtime.
# RepoIQ requires Python 3.11+.
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update

apt-get install -y \
  python3.11 \
  python3.11-venv \
  python3.11-dev

# ---------------------------------------------------------------------------
# Install Docker
# ---------------------------------------------------------------------------
echo "Installing Docker..." >&2

install -m 0755 -d /etc/apt/keyrings

curl -fsSL \
  https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc

chmod a+r /etc/apt/keyrings/docker.asc

echo \
"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
$(. /etc/os-release && echo "$${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" \
| tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update

apt-get install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

systemctl enable docker
systemctl start docker

echo "Docker installed: $(docker --version)" >&2

# ---------------------------------------------------------------------------
# Install K3s (without starting a cluster on the builder)
# ---------------------------------------------------------------------------
echo "Installing K3s..." >&2

curl -sfL https://get.k3s.io | INSTALL_K3S_SKIP_START=true sh -

systemctl disable --now k3s || true

echo "K3s installed without starting a builder cluster" >&2

# ---------------------------------------------------------------------------
# Install the RepoIQ source into the golden image
# ---------------------------------------------------------------------------
REPO_DIR="/opt/repoiq"
SOURCE_ARCHIVE="/tmp/repoiq-source.zip"

rm -rf "$${REPO_DIR}"
mkdir -p "$${REPO_DIR}"

if ! aws s3 cp \
  "s3://${artifacts_bucket_name}/${source_artifact_key}" \
  "$${SOURCE_ARCHIVE}"; then
  echo "FATAL: Failed to download RepoIQ source artifact" >&2
  exit 1
fi

if ! unzip -q "$${SOURCE_ARCHIVE}" -d "$${REPO_DIR}"; then
  echo "FATAL: Failed to extract RepoIQ source artifact" >&2
  exit 1
fi

rm -f "$${SOURCE_ARCHIVE}"

for required_file in \
  "$${REPO_DIR}/backend/Dockerfile" \
  "$${REPO_DIR}/backend/app/main.py" \
  "$${REPO_DIR}/Frontend/Dockerfile" \
  "$${REPO_DIR}/Frontend/package.json" \
  "$${REPO_DIR}/infrastructure/terraform/modules/ec2/repoiq-k3s-init.sh" \
  "$${REPO_DIR}/infrastructure/terraform/modules/ec2/repoiq-k3s-init.service"; do
  if [ ! -f "$${required_file}" ]; then
    echo "FATAL: Extracted RepoIQ source is missing $${required_file}" >&2
    exit 1
  fi
done

python3.11 -m venv "$${REPO_DIR}/.venv"

if [ -f "$${REPO_DIR}/requirements.txt" ]; then
  "$${REPO_DIR}/.venv/bin/pip" install --no-cache-dir \
    -r "$${REPO_DIR}/requirements.txt"
fi

"$${REPO_DIR}/.venv/bin/pip" install --no-cache-dir \
  -r "$${REPO_DIR}/backend/requirements.txt"

echo "Verifying RepoIQ Python runtime..." >&2

"$${REPO_DIR}/.venv/bin/python" --version

if ! "$${REPO_DIR}/.venv/bin/python" -c \
  'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "FATAL: RepoIQ virtual environment requires Python 3.11 or newer" >&2
  exit 1
fi

if ! "$${REPO_DIR}/.venv/bin/python" -c \
  "from enum import StrEnum; print('StrEnum OK')"; then
  echo "FATAL: Python enum.StrEnum verification failed" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Build RepoIQ images in Docker
# ---------------------------------------------------------------------------
echo "Building RepoIQ Docker images..." >&2

docker build -t repoiq-backend:latest "$${REPO_DIR}/backend"
docker build -t repoiq-frontend:latest "$${REPO_DIR}/Frontend"

# ---------------------------------------------------------------------------
# Download and verify RepoIQ Kubernetes manifests from S3 artifacts.
# Single source of truth: files Terraform uploaded to artifacts/k8s/*.yaml,
# NOT whatever happened to be in the source zip at zip-creation time.
# ---------------------------------------------------------------------------
K8S_DIR="$${REPO_DIR}/k8s"
K8S_S3_PREFIX="artifacts/k8s"

mkdir -p "$${K8S_DIR}"

download_manifest() {
  local s3_key="$${1}"
  local dest="$${2}"
  for attempt in 1 2 3 4 5; do
    if aws s3 cp "s3://${artifacts_bucket_name}/$${s3_key}" "$${dest}" >&2; then
      return 0
    fi
    sleep 2
  done
  echo "FATAL: Failed to download manifest s3://${artifacts_bucket_name}/$${s3_key} after 5 attempts" >&2
  return 1
}

download_manifest "$${K8S_S3_PREFIX}/configmap.yaml"              "$${K8S_DIR}/configmap.yaml"
download_manifest "$${K8S_S3_PREFIX}/secret.yaml"                 "$${K8S_DIR}/secret.yaml"
download_manifest "$${K8S_S3_PREFIX}/postgres-pvc.yaml"           "$${K8S_DIR}/postgres-pvc.yaml"
download_manifest "$${K8S_S3_PREFIX}/postgres-deployment.yaml"    "$${K8S_DIR}/postgres-deployment.yaml"
download_manifest "$${K8S_S3_PREFIX}/postgres-service.yaml"       "$${K8S_DIR}/postgres-service.yaml"
download_manifest "$${K8S_S3_PREFIX}/backend-deployment.yaml"     "$${K8S_DIR}/backend-deployment.yaml"
download_manifest "$${K8S_S3_PREFIX}/backend-service.yaml"        "$${K8S_DIR}/backend-service.yaml"
download_manifest "$${K8S_S3_PREFIX}/frontend-deployment.yaml"    "$${K8S_DIR}/frontend-deployment.yaml"
download_manifest "$${K8S_S3_PREFIX}/frontend-service.yaml"       "$${K8S_DIR}/frontend-service.yaml"
download_manifest "$${K8S_S3_PREFIX}/ingress.yaml"                "$${K8S_DIR}/ingress.yaml"

for manifest in \
  "configmap.yaml" \
  "secret.yaml" \
  "postgres-pvc.yaml" \
  "postgres-deployment.yaml" \
  "postgres-service.yaml" \
  "backend-deployment.yaml" \
  "backend-service.yaml" \
  "frontend-deployment.yaml" \
  "frontend-service.yaml" \
  "ingress.yaml"; do
  if [ ! -f "$${K8S_DIR}/$${manifest}" ]; then
    echo "FATAL: Kubernetes manifest copy failed for $${K8S_DIR}/$${manifest}" >&2
    exit 1
  fi
done

# ---------------------------------------------------------------------------
# Install the first-boot cluster initializer from S3 artifacts (single
# source of truth: the same files Terraform uploaded to artifacts/ and hashes
# in the triggers). Never use copies embedded inside the source zip, which
# could drift.
# ---------------------------------------------------------------------------
download_builder_artifact() {
  local s3_key="$${1}"
  local dest="$${2}"
  local mode="$${3:-0644}"
  for attempt in 1 2 3 4 5; do
    if aws s3 cp "s3://${artifacts_bucket_name}/$${s3_key}" "$${dest}" >&2; then
      chmod "$${mode}" "$${dest}"
      return 0
    fi
    sleep 2
  done
  echo "FATAL: Failed to download s3://${artifacts_bucket_name}/$${s3_key}" >&2
  return 1
}

download_builder_artifact \
  "artifacts/repoiq-k3s-init.sh" \
  /usr/local/sbin/repoiq-k3s-init.sh \
  0755
download_builder_artifact \
  "artifacts/repoiq-k3s-init.service" \
  /etc/systemd/system/repoiq-k3s-init.service \
  0644

systemctl daemon-reload
systemctl enable repoiq-k3s-init.service

# ---------------------------------------------------------------------------
# Prepare RepoIQ runtime directory
# ---------------------------------------------------------------------------
mkdir -p "$${READY_DIR}"
chmod 0755 "$${READY_DIR}"

# ---------------------------------------------------------------------------
# Create readiness marker locally
# ---------------------------------------------------------------------------
echo "Creating readiness marker at: $${READY_FILE}" >&2

# Keep the AMI clone-safe: a K3s cluster must only ever be initialized on the
# eventual demo instance, never on this builder. Aggressively remove any
# leftover rancher/K3s state created (even accidentally) during install.
if systemctl is-active --quiet k3s; then
  echo "FATAL: K3s is unexpectedly active on the image builder" >&2
  exit 1
fi

if [ -x /usr/local/bin/k3s-killall.sh ]; then
  /usr/local/bin/k3s-killall.sh || true
fi

# Explicitly delete any rancher paths created on the builder, so they cannot
# be captured in the AMI snapshot. Docker state is intentionally preserved.
if [ -d /var/lib/rancher ]; then
  rm -rf /var/lib/rancher || true
fi
if [ -d /etc/rancher ]; then
  rm -rf /etc/rancher || true
fi

for builder_state in \
  /var/lib/rancher/k3s \
  /var/lib/rancher/k3s/server \
  /var/lib/rancher/k3s/server/db \
  /var/lib/rancher/k3s/server/token \
  /var/lib/rancher/k3s/server/node-token \
  /var/lib/rancher/k3s/agent \
  /var/lib/rancher/agent \
  /etc/rancher \
  /etc/rancher/node; do
  if [ -e "$${builder_state}" ]; then
    echo "FATAL: Builder K3s state exists at $${builder_state} and would be captured in the AMI" >&2
    exit 1
  fi
done

for required_file in \
  "$${REPO_DIR}/k8s/configmap.yaml" \
  "$${REPO_DIR}/k8s/secret.yaml" \
  "$${REPO_DIR}/k8s/postgres-deployment.yaml" \
  "$${REPO_DIR}/k8s/backend-deployment.yaml" \
  "$${REPO_DIR}/k8s/frontend-deployment.yaml" \
  "$${REPO_DIR}/k8s/ingress.yaml" \
  "/usr/local/sbin/repoiq-k3s-init.sh" \
  "/etc/systemd/system/repoiq-k3s-init.service"; do
  if [ ! -s "$${required_file}" ]; then
    echo "FATAL: Required golden image file is missing: $${required_file}" >&2
    exit 1
  fi
done

docker image inspect repoiq-backend:latest >/dev/null
docker image inspect repoiq-frontend:latest >/dev/null
/usr/local/bin/k3s --version >/dev/null

if ! systemctl is-enabled --quiet repoiq-k3s-init.service; then
  echo "FATAL: RepoIQ first-boot initialization service is not enabled" >&2
  exit 1
fi

if systemctl is-enabled --quiet k3s; then
  echo "FATAL: K3s must remain disabled until first-boot initialization" >&2
  exit 1
fi

cat > "$${READY_FILE}" <<'READY'
RepoIQ golden image setup complete
Docker installed
K3s installed without builder cluster state
RepoIQ Docker images validated
First-boot K3s initialization installed
Python runtime installed
System dependencies installed
READY

if [ ! -f "$${READY_FILE}" ]; then
  echo "FATAL: Failed to create readiness marker" >&2
  exit 1
fi

echo "Readiness marker created successfully" >&2
echo "File size: $(stat -c%s "$${READY_FILE}" 2>/dev/null || echo 'unknown') bytes" >&2

# ---------------------------------------------------------------------------
# Upload readiness marker to S3
# ---------------------------------------------------------------------------
echo "Uploading readiness marker to S3..." >&2
echo "Bucket: $${BUCKET}" >&2
echo "Key: $${READY_S3_KEY}" >&2
echo "Instance ID: $${INSTANCE_ID}" >&2

if aws s3 cp \
  "$${READY_FILE}" \
  "s3://$${BUCKET}/$${READY_S3_KEY}" \
  2>&1; then

  echo "SUCCESS: Readiness marker uploaded to S3" >&2

else
  UPLOAD_EXIT_CODE=$?

  echo "FAILED: S3 upload exited with code $${UPLOAD_EXIT_CODE}" >&2

  exit $${UPLOAD_EXIT_CODE}
fi

sync

echo "REPOIQ_GOLDEN_IMAGE_READY"
echo "Golden image builder completed successfully."
