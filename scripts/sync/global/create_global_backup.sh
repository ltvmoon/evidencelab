#!/usr/bin/env bash
#
# Create a global Evidence Lab backup bundle using canonical db sync scripts.
# Secrets are excluded by default.
#
# Usage:
#   scripts/sync/global/create_global_backup.sh --data-source wfp
#
# Optional upload:
#   ... --gcp-bucket evidencelab-storage --gcp-prefix db/backups
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage:
  create_global_backup.sh --data-source <slug> [options]

Required:
  --data-source <slug>       Datasource slug (e.g. wfp)

Optional:
  --output-dir <path>        Parent dir for backup bundle (default: /mnt/data/backup)
  --prefix <prefix>          Dump directory prefix (default: global_)
  --bundle-name <name>       Top-level bundle dir name (default: evidencelab_global_<timestamp>)
  --tar-name <name>          Tarball filename (default: <bundle-name>.tar.gz)
  --gcp-bucket <bucket>      Upload tarball to this GCS bucket
  --gcp-prefix <prefix>      GCS object prefix (default: db/backups)
  --include-env              Include .env in bundle as credentials.env (default: excluded)
EOF
}

OUTPUT_PARENT="/mnt/data/backup"
PREFIX="global_"
DATA_SOURCE=""
BUNDLE_NAME=""
TAR_NAME=""
GCP_BUCKET=""
GCP_PREFIX="db/backups"
INCLUDE_ENV=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --data-source)
      DATA_SOURCE="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_PARENT="${2:-}"
      shift 2
      ;;
    --prefix)
      PREFIX="${2:-}"
      shift 2
      ;;
    --bundle-name)
      BUNDLE_NAME="${2:-}"
      shift 2
      ;;
    --tar-name)
      TAR_NAME="${2:-}"
      shift 2
      ;;
    --gcp-bucket)
      GCP_BUCKET="${2:-}"
      shift 2
      ;;
    --gcp-prefix)
      GCP_PREFIX="${2:-}"
      shift 2
      ;;
    --include-env)
      INCLUDE_ENV=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$DATA_SOURCE" ]]; then
  echo "error: --data-source is required" >&2
  usage
  exit 1
fi

DATA_SOURCE_SLUG="$(echo "$DATA_SOURCE" | tr '[:upper:]' '[:lower:]' | tr ' ' '_')"
if [[ -z "$BUNDLE_NAME" ]]; then
  TS="$(date +%Y%m%d_%H%M%S)"
  BUNDLE_NAME="evidencelab_global_${TS}"
fi
if [[ -z "$TAR_NAME" ]]; then
  TAR_NAME="${BUNDLE_NAME}.tar.gz"
fi

BUNDLE_DIR="${OUTPUT_PARENT}/${BUNDLE_NAME}"
mkdir -p "$BUNDLE_DIR"/{postgres,qdrant,data,repo}

DATA_SOURCE_PATH="$(readlink -f "$ROOT_DIR/data/$DATA_SOURCE_SLUG" 2>/dev/null || true)"
if [[ ! -d "$DATA_SOURCE_PATH" ]]; then
  echo "error: datasource path not found: $ROOT_DIR/data/$DATA_SOURCE_SLUG" >&2
  exit 1
fi

echo "[1/7] Postgres dump via scripts/sync/db/dump_postgres.py"
python3 scripts/sync/db/dump_postgres.py \
  --output "$BUNDLE_DIR/postgres" \
  --prefix "$PREFIX"

echo "[2/7] Qdrant dump via scripts/sync/db/dump_qdrant.py (api container)"
docker compose exec -T api mkdir -p /app/data/_backup_scratch
docker compose exec -T api python scripts/sync/db/dump_qdrant.py \
  --output /app/data/_backup_scratch \
  --data-source "$DATA_SOURCE" \
  --prefix "$PREFIX"

SCRATCH_HOST="$(readlink -f "$ROOT_DIR/data/_backup_scratch")"
QDRANT_DIR="$(find "$SCRATCH_HOST" -maxdepth 1 -type d -name "${PREFIX}qdrant_dump_${DATA_SOURCE_SLUG}_*" | sort | tail -1)"
if [[ -z "$QDRANT_DIR" || ! -d "$QDRANT_DIR" ]]; then
  echo "error: could not find qdrant dump under $SCRATCH_HOST" >&2
  exit 1
fi
sudo cp -a "$QDRANT_DIR" "$BUNDLE_DIR/qdrant/"
sudo chown -R "$(id -u):$(id -g)" "$BUNDLE_DIR/qdrant/$(basename "$QDRANT_DIR")"
sudo rm -rf "$SCRATCH_HOST"

echo "[3/7] Copy data/$DATA_SOURCE_SLUG"
rsync -aH --info=progress2 "$DATA_SOURCE_PATH/" "$BUNDLE_DIR/data/$DATA_SOURCE_SLUG/"

echo "[4/7] Snapshot repo (secrets excluded)"
rsync -a \
  --exclude=".env" \
  --exclude="gcp.key.json" \
  --exclude="gcp.key.json.*" \
  --exclude="*.pem" \
  --exclude="*.p12" \
  --exclude=".venv" \
  --exclude=".mypy_cache" \
  --exclude="data" \
  "$ROOT_DIR/" "$BUNDLE_DIR/repo/"

mkdir -p "$BUNDLE_DIR/repo/data"
cat >"$BUNDLE_DIR/repo/data/README_FROM_BACKUP.txt" <<EOF
Pipeline files live at ../../data/${DATA_SOURCE_SLUG}/ in this bundle.
EOF

echo "[5/7] Write metadata and docs"
cp -a "$ROOT_DIR/config.json" "$BUNDLE_DIR/config.json"
if [[ "$INCLUDE_ENV" == "1" ]]; then
  install -m 600 "$ROOT_DIR/.env" "$BUNDLE_DIR/credentials.env"
fi
git -C "$ROOT_DIR" rev-parse HEAD >"$BUNDLE_DIR/GIT_COMMIT.txt"
git -C "$ROOT_DIR" ls-files >"$BUNDLE_DIR/CODE_MANIFEST_git_tracked.txt"

POSTGRES_DIR="$(ls -1d "$BUNDLE_DIR/postgres/${PREFIX}"postgres_dump_* | head -1)"
QDRANT_BASENAME="$(basename "$BUNDLE_DIR/qdrant/$(basename "$QDRANT_DIR")")"

cat >"$BUNDLE_DIR/BUNDLE_PATHS.txt" <<EOF
BACKUP_ROOT=$BUNDLE_DIR
DATA_SUBDIR=$DATA_SOURCE
DATA_SUBDIR_SLUG=$DATA_SOURCE_SLUG
POSTGRES_DIR=$POSTGRES_DIR
QDRANT_DIR=$BUNDLE_DIR/qdrant/$QDRANT_BASENAME
REPO_SNAPSHOT=$BUNDLE_DIR/repo
EXCLUDED_FROM_REPO_SNAPSHOT=.env; gcp.key.json*; *.pem; *.p12; data; .venv; .mypy_cache
EOF

cat >"$BUNDLE_DIR/REFRESH.md" <<EOF
# Evidence Lab Global Backup

This bundle contains:
- \`repo/\` source snapshot (**secrets excluded**)
- \`data/$DATA_SOURCE_SLUG/\`
- Postgres dump under \`postgres/\`
- Qdrant snapshots under \`qdrant/\`

Restore helpers:
- Postgres: \`python3 scripts/sync/db/restore_postgres.py --source <postgres_dump_dir> --dev --clean\`
- Qdrant: \`python3 scripts/sync/db/restore_qdrant.py --source <qdrant_dump_dir> --dev\`
- Data: \`rsync -aH data/$DATA_SOURCE_SLUG/ <DATA_MOUNT_PATH>/$DATA_SOURCE_SLUG/\`

If you need env credentials, provide them separately or re-run with \`--include-env\`.
EOF

echo "[6/7] Build tarball"
TAR_PATH="${OUTPUT_PARENT}/${TAR_NAME}"
rm -f "$TAR_PATH"
tar -C "$OUTPUT_PARENT" -czf "$TAR_PATH" "$BUNDLE_NAME"

echo "[7/7] Optional upload to GCS"
if [[ -n "$GCP_BUCKET" ]]; then
  gcloud storage cp "$TAR_PATH" "gs://${GCP_BUCKET}/${GCP_PREFIX}/${TAR_NAME}"
fi

echo "Done"
echo "Bundle: $BUNDLE_DIR"
echo "Tarball: $TAR_PATH"
