#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_DIR="${1:-}"
IMAGE_TAG="${2:-latest}"

if [ -z "${ENV_DIR}" ]; then
  echo "usage: $0 <terraform-environment-dir> [image-tag]" >&2
  exit 1
fi

if [ ! -d "${ENV_DIR}" ]; then
  echo "error: terraform environment directory not found: ${ENV_DIR}" >&2
  exit 1
fi

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "error: missing required command: $1" >&2
    exit 1
  fi
}

require_cmd aws
require_cmd docker
require_cmd terraform

tf_output() {
  terraform -chdir="${ENV_DIR}" output -raw "$1"
}

ECR_REPOSITORY_URL="$(tf_output ecr_repository_url)"
ECS_CLUSTER_NAME="$(tf_output ecs_cluster_name)"
ECS_SERVICE_NAME="$(tf_output ecs_service_name)"
AWS_REGION_VALUE="$(tf_output aws_region)"
ECR_REGISTRY="${ECR_REPOSITORY_URL%/*}"

AWS_ARGS=()
if [ -n "${AWS_PROFILE:-}" ]; then
  AWS_ARGS+=(--profile "${AWS_PROFILE}")
fi

echo "Logging into ECR ${ECR_REGISTRY}"
aws "${AWS_ARGS[@]}" ecr get-login-password --region "${AWS_REGION_VALUE}" | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

echo "Building API image ${ECR_REPOSITORY_URL}:${IMAGE_TAG}"
docker build -f "${REPO_ROOT}/src/api/Dockerfile" -t "${ECR_REPOSITORY_URL}:${IMAGE_TAG}" "${REPO_ROOT}"

echo "Pushing API image ${ECR_REPOSITORY_URL}:${IMAGE_TAG}"
docker push "${ECR_REPOSITORY_URL}:${IMAGE_TAG}"

if [ "${IMAGE_TAG}" != "latest" ]; then
  echo "Tagging ${IMAGE_TAG} as latest"
  docker tag "${ECR_REPOSITORY_URL}:${IMAGE_TAG}" "${ECR_REPOSITORY_URL}:latest"
  docker push "${ECR_REPOSITORY_URL}:latest"
fi

echo "Forcing a new ECS deployment for ${ECS_SERVICE_NAME}"
aws "${AWS_ARGS[@]}" ecs update-service \
  --cluster "${ECS_CLUSTER_NAME}" \
  --service "${ECS_SERVICE_NAME}" \
  --force-new-deployment \
  --region "${AWS_REGION_VALUE}" \
  >/dev/null

echo "Deployment rollout requested for ${ECS_SERVICE_NAME}"
