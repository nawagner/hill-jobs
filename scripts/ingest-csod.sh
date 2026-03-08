#!/usr/bin/env bash
# Run CSOD ingest locally (requires agent-browser + DATABASE_URL).
# Intended for weekly cron/launchd scheduling.
#
# Usage:
#   DATABASE_URL="postgresql+psycopg://..." ./scripts/ingest-csod.sh
#
# Or set DATABASE_URL in apps/api/.env and run without args.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
API_DIR="$PROJECT_DIR/apps/api"

cd "$API_DIR"

# Use uv to run within the API's virtual environment
exec uv run python "$SCRIPT_DIR/ingest_csod.py"
