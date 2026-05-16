#!/usr/bin/env bash
# Claude Blog — Local Runner (macOS / Linux)
# Usage: ./web/start.sh [port]

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${1:-5000}"

echo ""
echo "  Claude Blog Local Runner"
echo "  ========================"

# Python check
if ! command -v python3 &>/dev/null; then
  echo "  ✗ python3 not found. Install Python 3.11+ from python.org"
  exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python $PY_VER"

# Install deps
echo "  Installing dependencies..."
pip install -q -r "$ROOT/web/requirements.txt"

# .env setup
if [ ! -f "$ROOT/.env" ]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo ""
  echo "  ⚠  Created .env from .env.example"
  echo "  Add your ANTHROPIC_API_KEY to $ROOT/.env"
  echo "  Or configure it at http://localhost:$PORT/settings after launch"
fi

echo ""
echo "  → http://localhost:$PORT"
echo "  → Press Ctrl+C to stop"
echo ""

PORT="$PORT" python3 "$ROOT/web/app.py"
