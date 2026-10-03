#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DATE="$(date +%Y%m%d)"
ARCHIVE_DIR="$REPO_ROOT/dist"
ARCHIVE_PATH="$ARCHIVE_DIR/xiaoq-face-auth-demo-${BUILD_DATE}.zip"

cd "$REPO_ROOT"
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Refusing to package uncommitted changes. Commit or stash them first." >&2
    exit 1
fi

mkdir -p "$ARCHIVE_DIR"
git archive --format=zip --prefix="xiaoq-face-auth-demo/" --output="$ARCHIVE_PATH" HEAD
echo "Created $ARCHIVE_PATH"
