#!/usr/bin/env bash
set -euo pipefail

DATASET_DIR="${1:-dataset}"
BACKUP_ROOT="${2:-${DATASET_DIR}/backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${BACKUP_ROOT}/dataset_backup_${TIMESTAMP}"

FILES=(
  "host_logs.parquet"
  "ground_truth.parquet"
  "ground_truth.csv"
  "syscall-lookup-linux-v3_13.csv"
)

if [[ ! -d "${DATASET_DIR}" ]]; then
  echo "Dataset directory not found: ${DATASET_DIR}" >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"

for file in "${FILES[@]}"; do
  source_path="${DATASET_DIR}/${file}"
  if [[ -f "${source_path}" ]]; then
    cp -p "${source_path}" "${BACKUP_DIR}/${file}"
    echo "Backed up: ${source_path}"
  else
    echo "Skipped missing file: ${source_path}"
  fi
done

echo "Backup complete: ${BACKUP_DIR}"
