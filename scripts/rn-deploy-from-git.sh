#!/bin/sh
# Deploy rescue_net to production FROM A CLEAN CHECKOUT OF origin/main — not from
# the working tree. Run by the OWNER (never by the agent), see docs/PHASE0_ENV_SEPARATION.md.
#
#   sh scripts/rn-deploy-from-git.sh [commit-sha]     # default: origin/main
#
# 1. fresh clone of the pushed commit into a temp dir (uncommitted edits can never ship)
# 2. refuses unless the commit is on origin/main
# 3. hands that clone to rn-deploy-app.sh (backup -> copy -> migrate -> restart -> probe)
set -eu
REPO=$(cd "$(dirname "$0")/.." && pwd)
REF=${1:-origin/main}
TMP=$(mktemp -d /tmp/rn-deploy-src.XXXXXX)
trap 'rm -rf "$TMP"' EXIT

git -C "$REPO" fetch origin main
SHA=$(git -C "$REPO" rev-parse "$REF")
git -C "$REPO" merge-base --is-ancestor "$SHA" origin/main || { echo "REFUSED: $SHA is not on origin/main" >&2; exit 1; }
echo "deploying $SHA ($(git -C "$REPO" log -1 --format=%s "$SHA"))"
git clone -q "$REPO" "$TMP/src" && git -C "$TMP/src" checkout -q "$SHA"
sh "$TMP/src/scripts/rn-deploy-app.sh"
echo "deployed $SHA"
