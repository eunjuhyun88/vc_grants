#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

git config core.hooksPath .githooks
chmod +x .githooks/pre-push
chmod +x .githooks/post-merge

echo "Installed local hooks path: .githooks"
echo "pre-push and post-merge hooks are now active for this repository."
echo "context auto snapshots are enabled through hook pipeline (ctx:auto)."
