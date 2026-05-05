#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUTPUT_PATH="${1:-${REPO_ROOT}/iac/terraform/modules/app_ingestion/lambda.zip}"
WORK_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "${WORK_DIR}"
}

trap cleanup EXIT

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "error: missing required command: $1" >&2
    exit 1
  fi
}

require_cmd docker
require_cmd uv
require_cmd zip

echo "Building ingestion Lambda artifact at ${OUTPUT_PATH}"

(
  cd "${REPO_ROOT}/src"
  uv export --package ingestion-lambda --no-hashes --format requirements-txt > "${WORK_DIR}/requirements.txt"
)

grep -vE '^(shared|ingestion-lambda)([[:space:]=@].*)?$' "${WORK_DIR}/requirements.txt" > "${WORK_DIR}/requirements.filtered.txt"

docker run --rm \
  -v "${REPO_ROOT}:/workspace" \
  -v "${WORK_DIR}:/out" \
  public.ecr.aws/lambda/python:3.11 \
  /bin/sh -lc '
    set -eu
    mkdir -p /out/package
    python -m pip install --upgrade pip
    python -m pip install --no-cache-dir --target /out/package -r /out/requirements.filtered.txt
    cp -R /workspace/src/ingestion/lambda_handler /out/package/
    cp -R /workspace/src/shared/shared /out/package/shared
    find /out/package -type d -name "__pycache__" -exec rm -rf {} +
    find /out/package -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete
  '

mkdir -p "$(dirname "${OUTPUT_PATH}")"
rm -f "${OUTPUT_PATH}"

(
  cd "${WORK_DIR}/package"
  zip -qr "${OUTPUT_PATH}" .
)

echo "Wrote ${OUTPUT_PATH}"
