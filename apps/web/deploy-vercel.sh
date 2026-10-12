#!/usr/bin/env bash
set -euo pipefail

# Standalone Vercel Production Deployment Script for UPPSC BEO Mains Examiner Suite
# Usage:
#   export VERCEL_TOKEN="<your-vercel-token>"
#   ./deploy-vercel.sh

if [ -z "${VERCEL_TOKEN:-}" ]; then
  echo "Error: VERCEL_TOKEN environment variable is required."
  echo "Usage: VERCEL_TOKEN=<token> ./deploy-vercel.sh"
  exit 1
fi

cd "$(dirname "$0")"
echo "Building & deploying @uppsc-beo/web (Next.js 14 standalone + /api/v1/[...slug]) to Vercel Production..."
npx --yes vercel deploy --prod --yes --token "$VERCEL_TOKEN"
