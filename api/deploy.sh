#!/bin/bash
# Deploy the extraction API to Fly.io
#
# Prerequisites:
#   1. flyctl installed: curl -L https://fly.io/install.sh | sh
#   2. Authenticated: flyctl auth login
#   3. First deploy: flyctl launch (creates the app)
#
# Usage:
#   cd api && ./deploy.sh
#
# The script copies claim_graphs package and prompts into the api/
# directory for Docker build, deploys, then cleans up the copies.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXTRACT_SRC="${EXTRACT_SRC:-$(cd "$(dirname "$0")/../extract" && pwd)}"

echo "Copying extraction package for build..."
cp -r "$EXTRACT_SRC/claim_graphs" "$SCRIPT_DIR/claim_graphs"
cp -r "$EXTRACT_SRC/prompts" "$SCRIPT_DIR/prompts"

echo "Deploying to Fly.io..."
cd "$SCRIPT_DIR"
flyctl deploy

echo "Cleaning up build copies..."
rm -rf "$SCRIPT_DIR/claim_graphs" "$SCRIPT_DIR/prompts"

echo "Done. API at: https://claim-graphs-api.fly.dev"
