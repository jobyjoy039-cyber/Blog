#!/usr/bin/env bash
# Start the Claude Blog browser UI
# Usage: ./web/start.sh [port]

set -e

PORT="${1:-5000}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Check Flask is installed
if ! python3 -c "import flask" 2>/dev/null; then
  echo "Installing Flask..."
  pip install flask markdown --quiet
fi

echo ""
echo "  Claude Blog UI"
echo "  → http://localhost:${PORT}"
echo "  Press Ctrl+C to stop"
echo ""

PORT="$PORT" python3 "$ROOT/web/app.py"
