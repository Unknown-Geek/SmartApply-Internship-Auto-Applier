#!/bin/bash
# =============================================================================
# SmartApply — Start Script
# =============================================================================
# Starts the SmartApply FastAPI server with Cerebras + Playwright.
#
# Usage:
#   chmod +x start.sh
#   ./start.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== SmartApply — Internship Auto-Applier ===${NC}"

# ---- Load .env ----
if [ -f .env ]; then
    echo -e "${GREEN}Loading .env...${NC}"
    set -a; source .env; set +a
else
    echo -e "${YELLOW}No .env found — copy .env.smartapply to .env and set your CEREBRAS_API_KEY${NC}"
    exit 1
fi

echo -e "Python:           $(python3 --version 2>/dev/null | awk '{print $2}')"
echo -e "Cerebras model:   ${CEREBRAS_MODEL:-gpt-oss-120b}"
echo -e "Cerebras key:     ${CEREBRAS_API_KEY:+set}"
echo -e "Telegram bot:     ${TELEGRAM_BOT_TOKEN:+configured}${TELEGRAM_BOT_TOKEN:-not set}"
echo -e "Database:         ${SQLITE_DB_PATH:-$SCRIPT_DIR/app/db/smartapply.db}"

# ---- Create data dirs ----
mkdir -p "$SCRIPT_DIR/app/db"

# ---- Start FastAPI ----
echo -e "\n${BLUE}Starting SmartApply API server on port ${PORT:-8000}...${NC}"
echo -e "Docs: http://0.0.0.0:${PORT:-8000}/docs\n"

exec uvicorn app.main:app \
    --host "${HOST:-0.0.0.0}" \
    --port "${PORT:-8000}" \
    --log-level info
