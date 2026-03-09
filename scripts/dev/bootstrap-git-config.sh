#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

git config --local core.hooksPath .githooks
git config --local fetch.prune true
git config --local pull.ff only
git config --local merge.conflictstyle zdiff3
git config --local rerere.enabled true
git config --local rerere.autoupdate true

echo "[safe:git-config] applied repo-local git defaults"
echo "[safe:git-config] core.hooksPath=.githooks"
echo "[safe:git-config] fetch.prune=true"
echo "[safe:git-config] pull.ff=only"
echo "[safe:git-config] merge.conflictstyle=zdiff3"
echo "[safe:git-config] rerere.enabled=true"
echo "[safe:git-config] rerere.autoupdate=true"
