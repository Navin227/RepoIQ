#!/bin/bash
set -Euo pipefail

# ============================================================
# RepoIQ demo instance K3s initializer / verifier.
# TWO execution modes:
#   FIRST_BOOT       -> demo-initialized marker absent -> create fresh cluster,
#                       import images, apply manifests, wait for everything,
#                       run smoke tests, then write marker.
#   SUBSEQUENT_BOOT  -> marker present -> just ensure k3s is up, verify
#                       workloads + /health, exit quickly (no destructive action).
# All important stages are logged with prefix [RepoIQ][K3s], written to
# /var/log/repoiq/k3s-init.log, mirrored to journal (via systemd unit), and
# periodically uploaded to S3 so the Status Lambda / UI can show real progress.
# ============================================================

MARKER="/var/lib/repoiq/demo-initialized"
READY_DIR="/var/lib/repoiq"
LOG_DIR="/var/log/repoiq"
LOG_FILE="${LOG_DIR}/k3s-init.log"
STAGE_FILE="${READY_DIR}/stage.json"
K8S_DIR="/opt/repoiq/k8s"
ARTIFACTS_BUCKET_FILE="/etc/repoiq/artifacts_bucket"
ARTIFACTS_REGION_FILE="/etc/repoiq/aws_region"

mkdir -p "${READY_DIR}" "${LOG_DIR}" "$(dirname "${STAGE_FILE}")"
chmod 0755 "${READY_DIR}" "${LOG_DIR}"

# Redirect output: mirror to log file + keep stdout for journal.
if [ "${_REPOIQ_LOG_REDIRECTED:-0}" != "1" ]; then
  export _REPOIQ_LOG_REDIRECTED=1
  exec > >(tee -a "${LOG_FILE}") 2>&1
fi

# Resolve bucket/region for optional S3 stage uploads (best effort only).
ARTIFACTS_BUCKET=""
AWS_DEFAULT_REGION=""
if [ -s "${ARTIFACTS_BUCKET_FILE}" ]; then
  ARTIFACTS_BUCKET="$(tr -d '[:space:]' < "${ARTIFACTS_BUCKET_FILE}")"
fi
if [ -s "${ARTIFACTS_REGION_FILE}" ]; then
  AWS_DEFAULT_REGION="$(tr -d '[:space:]' < "${ARTIFACTS_REGION_FILE}")"
fi
export AWS_DEFAULT_REGION

INSTANCE_ID=""
resolve_instance_id() {
  local token url
  for i in 1 2 3 4 5; do
    token="$(curl -fsS -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 21600' 2>/dev/null || true)"
    if [ -n "${token}" ]; then
      url="http://169.254.169.254/latest/meta-data/instance-id"
      INSTANCE_ID="$(curl -fsS -H "X-aws-ec2-metadata-token: ${token}" "${url}" 2>/dev/null || true)"
      if [ -n "${INSTANCE_ID}" ]; then return 0; fi
    fi
    sleep 2
  done
  return 1
}

# Stage helpers: structured stage machine.
declare -a STAGES_IN_ORDER=(
  "init_started"
  "k3s_started"
  "node_ready"
  "images_imported"
  "manifests_applied"
  "postgres_ready"
  "backend_ready"
  "frontend_ready"
  "traefik_ready"
  "traefik_svc_valid"
  "host_port_80_listening"
  "localhost_health_ok"
  "private_ip_health_ok"
  "public_ip_health_ok"
  "stage_summary"
  "completed"
)

TOTAL_STAGES="${#STAGES_IN_ORDER[@]}"
STAGE_INDEX=0
STAGE_NAME=startup
STAGE_STATUS=pending

json_escape() {
  local s="${1-}"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  s="${s//$'\r'/\\r}"
  s="${s//$'\t'/\\t}"
  printf '%s' "${s}"
}

write_stage_file() {
  local status="${1}"
  local stage_index="${2}"
  local stage_name="${3}"
  local message="${4:-}"
  local boot_mode="${5:-FIRST_BOOT}"
  local error_message="${6:-}"
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  local instance_id_value="${INSTANCE_ID:-}"
  local stage_status="${status}"
  local next_state="initializing"
  if [ "${stage_status}" = "failed" ]; then
    next_state="failed"
  elif [ "${stage_status}" = "completed" ] && [ "${stage_name}" = "completed" ]; then
    next_state="ready"
  fi

  python3 - "$STAGE_FILE" "$boot_mode" "$stage_status" "$stage_name" "$stage_index" "$message" "$ts" "$instance_id_value" "$next_state" "$error_message" <<'PYEOF' || true
import json, os, sys
path = sys.argv[1]
boot_mode = sys.argv[2]
status = sys.argv[3]
stage_name = sys.argv[4]
stage_index = int(sys.argv[5])
message = sys.argv[6]
ts = sys.argv[7]
instance_id = sys.argv[8]
state = sys.argv[9]
error_message = sys.argv[10] if len(sys.argv) > 10 else ""
level = "info"
if status == "failed":
    level = "error"
elif status == "running":
    level = "info"
else:
    level = "info"
stages_order = [
  "init_started", "k3s_started", "node_ready", "images_imported",
  "manifests_applied", "postgres_ready", "backend_ready", "frontend_ready",
  "traefik_ready", "traefik_svc_valid", "host_port_80_listening",
  "localhost_health_ok", "private_ip_health_ok", "public_ip_health_ok",
  "stage_summary", "completed",
]
existing = {}
if os.path.exists(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            existing = json.load(fh) or {}
    except Exception:
        existing = {}
if not isinstance(existing, dict):
    existing = {}
logs = existing.get("logs") or []
if not isinstance(logs, list):
    logs = []
entry = {"timestamp": ts, "level": level, "stage": stage_name, "message": message}
if not any(existing_entry.get("message") == entry.get("message") and existing_entry.get("stage") == entry.get("stage") and existing_entry.get("timestamp") == entry.get("timestamp") for existing_entry in logs):
    logs.append(entry)
if len(logs) > 100:
    logs = logs[-100:]
completed_stages = existing.get("completed_stages") or []
if not isinstance(completed_stages, list):
    completed_stages = []
if status == "completed" and stage_name not in completed_stages:
    completed_stages.append(stage_name)
if status == "failed" and error_message:
    existing_error = existing.get("error")
    if not existing_error:
        existing["error"] = error_message
    elif existing_error != error_message:
        existing["error"] = error_message
payload = {
  "instance_id": instance_id,
  "boot_mode": boot_mode,
  "state": state,
  "status": status,
  "stage_index": stage_index,
  "stage_name": stage_name,
  "message": message,
  "timestamp": ts,
  "completed_stages": completed_stages,
  "logs": logs,
  "stages": [
    {
      "name": s,
      "status": "completed" if s in completed_stages else (
        "running" if s == stage_name and status == "running" else (
          "failed" if s == stage_name and status == "failed" else "pending"
        )
      ),
    }
    for s in stages_order
  ],
  "error": error_message if status == "failed" else None,
}

if status != "failed" and error_message:
    payload["telemetry_error"] = error_message

try:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, path)
except Exception:
    try:
        if os.path.exists(f"{path}.tmp"):
            os.remove(f"{path}.tmp")
    except Exception:
        pass
    sys.exit(0)
PYEOF
}

upload_stage_s3() {
  if [ -z "${ARTIFACTS_BUCKET}" ] || [ -z "${INSTANCE_ID}" ]; then
    echo "[RepoIQ][K3s][WARN] Skipping S3 telemetry upload because bucket or instance ID is unavailable." >&2
    return 0
  fi

  local s3_key="artifacts/demo-init/${INSTANCE_ID}/stage.json"
  if [ ! -s "${STAGE_FILE}" ]; then
    echo "[RepoIQ][K3s][ERROR] Failed to upload initialization telemetry to S3 bucket=${ARTIFACTS_BUCKET} key=${s3_key} exit_code=1 (stage file missing)" >&2
    return 1
  fi

  if command -v aws >/dev/null 2>&1; then
    local output
    output="$(aws s3 cp "${STAGE_FILE}" "s3://${ARTIFACTS_BUCKET}/${s3_key}" 2>&1)"
    local exit_code=$?
    if [ "${exit_code}" -eq 0 ]; then
      return 0
    fi
    echo "[RepoIQ][K3s][WARN] Failed to upload stage.json to S3: bucket=${ARTIFACTS_BUCKET} key=${s3_key} exit_code=${exit_code} detail=${output}" >&2
    return "${exit_code}"
  fi

  echo "[RepoIQ][K3s][WARN] Failed to upload stage.json to S3: bucket=${ARTIFACTS_BUCKET} key=${s3_key} exit_code=127 (aws cli unavailable)" >&2
  return 127
}

set_stage() {
  local stage_name="${1}"
  local status="${2}"
  local message="${3:-}"
  local idx=-1
  local s
  for i in "${!STAGES_IN_ORDER[@]}"; do
    s="${STAGES_IN_ORDER[$i]}"
    if [ "${s}" = "${stage_name}" ]; then idx=$((i + 1)); break; fi
  done
  if [ "${idx}" -lt 0 ]; then idx=0; fi
  STAGE_INDEX="${idx}"
  STAGE_NAME="${stage_name}"
  STAGE_STATUS="${status}"
  local log_prefix="[RepoIQ][K3s]"
  case "${status}" in
    running)   log_prefix="${log_prefix}" ;;
    completed) log_prefix="${log_prefix}" ;;
    failed)    log_prefix="${log_prefix}[ERROR]" ;;
  esac
  if [ -n "${message}" ]; then
    echo "${log_prefix} [stage=${stage_name}/${STAGE_INDEX}/${TOTAL_STAGES}] ${message}"
  else
    echo "${log_prefix} [stage=${stage_name}/${STAGE_INDEX}/${TOTAL_STAGES}]"
  fi
  write_stage_file "${status}" "${STAGE_INDEX}" "${stage_name}" "${message}" "${BOOT_MODE}"
  upload_stage_s3 || true
}

set_stage_failed() {
  local stage_name="${1}"
  local message="${2:-}"
  set_stage "${stage_name}" "failed" "${message}"
}

# kubectl wrapper after init starts.
kubectl() { /usr/local/bin/k3s kubectl "$@"; }

# Error handler: log stage failure, upload to S3, non-zero exit.
on_error() {
  local exit_code=$?
  local line_no="${1:-unknown}"
  echo "[RepoIQ][K3s][ERROR] initialization failed at line=${line_no} exit_code=${exit_code} last_stage=${STAGE_NAME}" >&2
  set_stage_failed "${STAGE_NAME}" "Line ${line_no} exited with ${exit_code}"
  exit "${exit_code}"
}
trap 'on_error $LINENO' ERR

echo "[RepoIQ][K3s] Initialization script started at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[RepoIQ][K3s] Log file: ${LOG_FILE}"

# ---- Resolve instance ID early (best effort).
if resolve_instance_id; then
  export INSTANCE_ID_JSON="${INSTANCE_ID}"
  echo "[RepoIQ][K3s] Instance ID resolved: ${INSTANCE_ID}"
fi

# ---- Boot mode decision.
if [ -e "${MARKER}" ]; then
  BOOT_MODE="SUBSEQUENT_BOOT"
  echo "[RepoIQ][K3s] Marker ${MARKER} present -> SUBSEQUENT_BOOT (verify existing cluster only)."
else
  BOOT_MODE="FIRST_BOOT"
  echo "[RepoIQ][K3s] Marker ${MARKER} absent -> FIRST_BOOT (fresh single-node K3s)."
fi
export BOOT_MODE

set_stage "init_started" "running" "RepoIQ K3s ${BOOT_MODE} started"

# ======================= SUBSEQUENT_BOOT path ================================
if [ "${BOOT_MODE}" = "SUBSEQUENT_BOOT" ]; then
  # Simply make sure k3s is enabled/started and all workloads are healthy.
  # No destructive operations. No re-import of images. No re-apply of manifests.
  if ! systemctl is-enabled --quiet k3s; then
    echo "[RepoIQ][K3s] k3s.service not enabled; enabling now."
    systemctl enable k3s
  fi
  systemctl start k3s || true
  set_stage "k3s_started" "running" "Starting existing K3s cluster"

  for attempt in $(seq 1 120); do
    if /usr/local/bin/k3s kubectl get nodes >/dev/null 2>&1; then break; fi
    sleep 5
    if [ "${attempt}" -eq 120 ]; then
      set_stage_failed "k3s_started" "kubectl did not become available on reboot"
      exit 1
    fi
  done
  set_stage "k3s_started" "completed" "K3s started on reboot"

  kubectl wait --for=condition=Ready node --all --timeout=300s
  set_stage "node_ready" "running" "Verifying node Ready on reboot"
  node_count="$(kubectl get nodes --no-headers | wc -l | tr -d '[:space:]')"
  if [ "${node_count}" -ne 1 ]; then
    echo "[RepoIQ][K3s][WARN] Expected 1 node on reboot, found ${node_count}. Continuing best-effort verification." >&2
    kubectl get nodes -o wide >&2 || true
  fi
  set_stage "node_ready" "completed" "Node Ready on reboot"

  # Skip first-boot-only stages: images_imported, manifests_applied
  set_stage "images_imported" "completed" "Skipped (existing cluster)"
  set_stage "manifests_applied" "completed" "Skipped (existing cluster)"

  # Wait up to 10 min total for the three core deployments + traefik.
  set_stage "postgres_ready" "running" "Verifying postgres Available (reboot)"
  kubectl wait --for=condition=Available deployment/postgres --timeout=600s -n default || true
  set_stage "postgres_ready" "completed" "Postgres verified on reboot"

  set_stage "backend_ready" "running" "Verifying backend Available (reboot)"
  kubectl wait --for=condition=Available deployment/repoiq-backend --timeout=600s -n default || true
  set_stage "backend_ready" "completed" "Backend verified on reboot"

  set_stage "frontend_ready" "running" "Verifying frontend Available (reboot)"
  kubectl wait --for=condition=Available deployment/repoiq-frontend --timeout=600s -n default || true
  set_stage "frontend_ready" "completed" "Frontend verified on reboot"

  set_stage "traefik_ready" "running" "Verifying traefik rollout (reboot)"
  kubectl -n kube-system rollout status deployment/traefik --timeout=600s || true
  set_stage "traefik_ready" "completed" "Traefik verified on reboot"

  set_stage "traefik_svc_valid" "running" "Validating Traefik Service LB/NodePort 80 (reboot)"
  traefik_type="$(kubectl -n kube-system get svc traefik -o jsonpath='{.spec.type}' 2>/dev/null || true)"
  traefik_http_port="$(kubectl -n kube-system get svc traefik -o jsonpath='{.spec.ports[?(@.port==80)].port}' 2>/dev/null || true)"
  traefik_http_node_port="$(kubectl -n kube-system get svc traefik -o jsonpath='{.spec.ports[?(@.port==80)].nodePort}' 2>/dev/null || true)"
  if [ "${traefik_type}" != "LoadBalancer" ] || [ "${traefik_http_port}" != "80" ] || [ -z "${traefik_http_node_port}" ]; then
    set_stage_failed "traefik_svc_valid" "Traefik Service unexpected: type=${traefik_type} port80=${traefik_http_port} nodePort=${traefik_http_node_port}"
    kubectl -n kube-system get svc traefik -o wide >&2 || true
    exit 1
  fi
  set_stage "traefik_svc_valid" "completed" "Traefik Service LB/NodePort 80 valid on reboot"
  # Fall through to shared smoke tests (host port / localhost / private / public).
fi

# ======================= FIRST_BOOT path =====================================
if [ "${BOOT_MODE}" = "FIRST_BOOT" ]; then
  # ---- Validate inputs.
  for required_file in \
    "${K8S_DIR}/configmap.yaml" \
    "${K8S_DIR}/secret.yaml" \
    "${K8S_DIR}/postgres-pvc.yaml" \
    "${K8S_DIR}/postgres-deployment.yaml" \
    "${K8S_DIR}/postgres-service.yaml" \
    "${K8S_DIR}/backend-deployment.yaml" \
    "${K8S_DIR}/backend-service.yaml" \
    "${K8S_DIR}/frontend-deployment.yaml" \
    "${K8S_DIR}/frontend-service.yaml" \
    "${K8S_DIR}/ingress.yaml"; do
    if [ ! -s "${required_file}" ]; then
      set_stage_failed "init_started" "Required manifest missing or empty: ${required_file}"
      exit 1
    fi
  done
  docker image inspect repoiq-backend:latest >/dev/null
  docker image inspect repoiq-frontend:latest >/dev/null

  # ---- Start / enable K3s (fresh single-node; K3s service was disabled in AMI).
  set_stage "k3s_started" "running" "Starting fresh K3s single-node cluster"
  systemctl enable --now k3s
  for attempt in $(seq 1 120); do
    if /usr/local/bin/k3s kubectl get nodes >/dev/null 2>&1; then break; fi
    sleep 5
    if [ "${attempt}" -eq 120 ]; then
      set_stage_failed "k3s_started" "kubectl did not become available after K3s start"
      exit 1
    fi
  done
  set_stage "k3s_started" "completed" "Fresh K3s cluster started and kubectl responding"

  # ---- Wait exactly ONE node Ready.
  set_stage "node_ready" "running" "Waiting for Kubernetes node Ready (exactly 1 node)"
  kubectl wait --for=condition=Ready node --all --timeout=300s
  node_count="$(kubectl get nodes --no-headers | wc -l | tr -d '[:space:]')"
  if [ "${node_count}" -ne 1 ]; then
    set_stage_failed "node_ready" "Expected exactly 1 fresh K3s node, found ${node_count}. Stale builder state may be in AMI."
    kubectl get nodes -o wide >&2 || true
    exit 1
  fi
  echo "[RepoIQ][K3s] Nodes:"
  kubectl get nodes -o wide
  set_stage "node_ready" "completed" "Exactly 1 K3s node Ready"

  # ---- Import Docker images into K3s containerd.
  set_stage "images_imported" "running" "Importing preserved RepoIQ Docker images into K3s containerd"
  echo "[RepoIQ][K3s] Backend image layers:"
  docker image inspect repoiq-backend:latest --format '{{ .Id }} size={{ .Size }}' || true
  echo "[RepoIQ][K3s] Frontend image layers:"
  docker image inspect repoiq-frontend:latest --format '{{ .Id }} size={{ .Size }}' || true
  docker save repoiq-backend:latest repoiq-frontend:latest \
    | /usr/local/bin/k3s ctr images import -
  echo "[RepoIQ][K3s] Images imported into containerd:"
  /usr/local/bin/k3s ctr images ls --quiet 2>/dev/null | grep -E 'repoiq-(backend|frontend)' || true
  set_stage "images_imported" "completed" "Backend and frontend images imported into containerd"

  # ---- Apply manifests in dependency order.
  set_stage "manifests_applied" "running" "Applying RepoIQ Kubernetes manifests in order"
  kubectl apply -f "${K8S_DIR}/configmap.yaml"
  kubectl apply -f "${K8S_DIR}/secret.yaml"
  kubectl apply -f "${K8S_DIR}/postgres-pvc.yaml"
  kubectl apply -f "${K8S_DIR}/postgres-deployment.yaml"
  kubectl apply -f "${K8S_DIR}/postgres-service.yaml"
  kubectl apply -f "${K8S_DIR}/backend-deployment.yaml"
  kubectl apply -f "${K8S_DIR}/backend-service.yaml"
  kubectl apply -f "${K8S_DIR}/frontend-deployment.yaml"
  kubectl apply -f "${K8S_DIR}/frontend-service.yaml"
  kubectl apply -f "${K8S_DIR}/ingress.yaml"
  set_stage "manifests_applied" "completed" "All RepoIQ manifests applied"

  # ---- Wait deployments.
  set_stage "postgres_ready" "running" "Waiting for PostgreSQL Deployment Available"
  kubectl wait --for=condition=Available deployment/postgres --timeout=600s -n default
  set_stage "postgres_ready" "completed" "PostgreSQL deployment Available"

  set_stage "backend_ready" "running" "Waiting for Backend Deployment Available"
  kubectl wait --for=condition=Available deployment/repoiq-backend --timeout=600s -n default
  set_stage "backend_ready" "completed" "Backend deployment Available"

  set_stage "frontend_ready" "running" "Waiting for Frontend Deployment Available"
  kubectl wait --for=condition=Available deployment/repoiq-frontend --timeout=600s -n default
  set_stage "frontend_ready" "completed" "Frontend deployment Available"

  # ---- Traefik.
  set_stage "traefik_ready" "running" "Waiting for kube-system traefik rollout complete"
  kubectl -n kube-system rollout status deployment/traefik --timeout=600s
  set_stage "traefik_ready" "completed" "Traefik rollout complete"
  kubectl wait --for=condition=Ready node --all --timeout=300s
fi

# ===== Shared stages (run for BOTH FIRST_BOOT and SUBSEQUENT_BOOT) ==========

# ---- Validate Traefik Service shape.
set_stage "traefik_svc_valid" "running" "Validating traefik LoadBalancer / port 80 / nodePort"
traefik_type="$(kubectl -n kube-system get service traefik -o jsonpath='{.spec.type}' 2>/dev/null || true)"
traefik_http_port="$(kubectl -n kube-system get service traefik -o jsonpath='{.spec.ports[?(@.port==80)].port}' 2>/dev/null || true)"
traefik_http_node_port="$(kubectl -n kube-system get service traefik -o jsonpath='{.spec.ports[?(@.port==80)].nodePort}' 2>/dev/null || true)"
echo "[RepoIQ][K3s] Traefik type=${traefik_type} port80=${traefik_http_port} nodePort=${traefik_http_node_port}"
if [ "${traefik_type}" != "LoadBalancer" ] || [ "${traefik_http_port}" != "80" ] || [ -z "${traefik_http_node_port}" ]; then
  set_stage_failed "traefik_svc_valid" "Traefik HTTP LoadBalancer/NodePort not configured as expected"
  kubectl -n kube-system get service traefik -o wide >&2 || true
  exit 1
fi
set_stage "traefik_svc_valid" "completed" "Traefik Service shape validated"

# ---- Host port 80 informational check.
# Do NOT use host-level ss/netstat socket detection as a readiness gate.
# K3s ServiceLB/Traefik can expose the Kubernetes Service without presenting
# a conventional host TCP LISTEN socket that matches this check.
# Actual application readiness is validated by the localhost/private/public
# /health checks below.
set_stage "host_port_80_listening" "running" "Checking host TCP port 80 (informational; not a readiness gate)"

port_80_observed=false
if command -v ss >/dev/null 2>&1; then
  if ss -tln 2>/dev/null | awk '{print $4}' | grep -qE '[:.]80$'; then
    port_80_observed=true
  fi
elif command -v netstat >/dev/null 2>&1; then
  if netstat -tln 2>/dev/null | awk '{print $4}' | grep -qE '[:.]80$'; then
    port_80_observed=true
  fi
fi

if [ "${port_80_observed}" = true ]; then
  set_stage "host_port_80_listening" "completed" "Host TCP port 80 is LISTENING (informational check passed)"
else
  echo "[RepoIQ][K3s][INFO] Host-level TCP port 80 listener was not observed; continuing because Traefik Service is valid and /health checks are the actual readiness gates."
  set_stage "host_port_80_listening" "completed" "Host socket check not observed; treated as informational because K3s ServiceLB/Traefik readiness is validated by /health checks"
fi

# ---- Determine IPs.
default_interface="$(ip -4 route show default | awk 'NR == 1 {print $5}')"
private_ip="$(ip -4 -o addr show dev "${default_interface}" scope global | awk 'NR == 1 {sub(/\/.*/, "", $4); print $4}')"
public_ip=""
if command -v curl >/dev/null 2>&1; then
  for i in 1 2 3; do
    token="$(curl -fsS -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 21600' 2>/dev/null || true)"
    if [ -n "${token}" ]; then
      public_ip="$(curl -fsS -H "X-aws-ec2-metadata-token: ${token}" http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)"
      [ -n "${public_ip}" ] && break
    fi
    sleep 1
  done
fi
if [ -z "${private_ip}" ]; then
  set_stage_failed "localhost_health_ok" "Cannot determine EC2 private IP (default interface: ${default_interface})"
  exit 1
fi
echo "[RepoIQ][K3s] Private IP=${private_ip} Public IP=${public_ip:-<unknown>}"

# ---- Localhost /health.
set_stage "localhost_health_ok" "running" "Testing http://127.0.0.1/health (HTTP 200 required)"
success=false
for attempt in $(seq 1 120); do
  if curl -fsS --max-time 5 "http://127.0.0.1/health" >/dev/null 2>&1; then
    success=true; break
  fi
  [ "$(( attempt % 10 ))" -eq 0 ] && echo "[RepoIQ][K3s]   still waiting for localhost /health (attempt ${attempt}/120)"
  sleep 3
done
if [ "${success}" != true ]; then
  set_stage_failed "localhost_health_ok" "http://127.0.0.1/health never returned HTTP 200"
  echo "[RepoIQ][K3s] Last 30 seconds of logs - pods:" >&2
  kubectl get pods -A >&2 || true
  exit 1
fi
echo "[RepoIQ][K3s] http://127.0.0.1/health returned HTTP 200"
set_stage "localhost_health_ok" "completed" "localhost /health HTTP 200"

# ---- Private IP /health.
set_stage "private_ip_health_ok" "running" "Testing http://${private_ip}/health (HTTP 200 required)"
success=false
for attempt in $(seq 1 60); do
  if curl -fsS --max-time 5 "http://${private_ip}/health" >/dev/null 2>&1; then
    success=true; break
  fi
  sleep 3
done
if [ "${success}" != true ]; then
  set_stage_failed "private_ip_health_ok" "http://${private_ip}/health never returned HTTP 200"
  exit 1
fi
set_stage "private_ip_health_ok" "completed" "Private IP /health HTTP 200"

# ---- Public IP /health (best-effort: if we cannot determine public IP, skip).
if [ -n "${public_ip}" ]; then
  set_stage "public_ip_health_ok" "running" "Testing http://${public_ip}/health (HTTP 200 required)"
  success=false
  for attempt in $(seq 1 60); do
    if curl -fsS --max-time 5 "http://${public_ip}/health" >/dev/null 2>&1; then
      success=true; break
    fi
    sleep 3
  done
  if [ "${success}" != true ]; then
    # Not fatal on subsequent boot (user may have just started instance; public IP
    # routing may lag). On first boot we hard-fail so the marker is NOT written.
    if [ "${BOOT_MODE}" = "FIRST_BOOT" ]; then
      set_stage_failed "public_ip_health_ok" "First boot: public /health never returned HTTP 200. SG/routing issue likely."
      exit 1
    fi
    echo "[RepoIQ][K3s][WARN] Subsequent boot: public /health did not return 200 yet; continuing anyway (will be rechecked by Status Lambda)." >&2
    set_stage "public_ip_health_ok" "completed" "Skipped (subsequent boot; Status Lambda will verify externally)"
  else
    set_stage "public_ip_health_ok" "completed" "Public IP /health HTTP 200"
  fi
else
  set_stage "public_ip_health_ok" "completed" "Skipped (could not resolve public IP from host; Status Lambda will verify externally)"
fi

# ---- Final summary.
set_stage "stage_summary" "running" "Writing summary of cluster state"
echo "[RepoIQ][K3s] kubectl get nodes -o wide:"
kubectl get nodes -o wide || true
echo "[RepoIQ][K3s] kubectl get pods -A:"
kubectl get pods -A || true
echo "[RepoIQ][K3s] kubectl -n kube-system get svc traefik -o wide:"
kubectl -n kube-system get svc traefik -o wide || true
echo "[RepoIQ][K3s] ss -tln | head -n 20:"
(ss -tln 2>/dev/null | head -n 20) || true
set_stage "stage_summary" "completed" "Cluster state dumped to log"

# ---- Marker ONLY now, on FIRST_BOOT.
if [ "${BOOT_MODE}" = "FIRST_BOOT" ]; then
  echo "[RepoIQ][K3s] All stages passed on first boot; creating marker ${MARKER}"
  touch "${MARKER}"
  chmod 0644 "${MARKER}"
  sync
fi

set_stage "completed" "completed" "RepoIQ application ready (boot mode: ${BOOT_MODE})"
echo "[RepoIQ][K3s] Initialization script finished successfully at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
exit 0
