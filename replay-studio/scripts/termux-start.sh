#!/data/data/com.termux/files/usr/bin/bash
# Start Replay Studio in the background on Android (Termux) and keep both services running.
# Holds a wake lock so Android does not suspend streaming while the screen is off.
set -u
cd "$(dirname "$0")/.."
APP="$PWD"
export REPLAY_STUDIO_CONFIG="$APP/config.toml"
RUN="$HOME/replay-studio-data/run"; LOG="$HOME/replay-studio-data/logs"
mkdir -p "$RUN" "$LOG"
command -v termux-wake-lock >/dev/null && termux-wake-lock

if [ "${1:-}" = "--supervise" ]; then   # restart a service if it exits (crash, OOM kill)
  name="$2"
  while [ ! -f "$RUN/stopping" ]; do
    "$APP/.venv/bin/replay-studio" "$name" >>"$LOG/$name.log" 2>&1
    [ -f "$RUN/stopping" ] && break
    echo "$(date) $name exited; restarting in 3 s" >>"$LOG/$name.log"
    sleep 3
  done
  exit 0
fi

for name in worker api; do
  if [ -f "$RUN/$name.sup" ] && kill -0 "$(cat "$RUN/$name.sup")" 2>/dev/null; then
    echo "$name already running"
    continue
  fi
  rm -f "$RUN/stopping"
  nohup bash "$APP/scripts/termux-start.sh" --supervise "$name" </dev/null >/dev/null 2>&1 &
  echo $! >"$RUN/$name.sup"
  echo "started $name"
done
# keep each log under ~5 MB
for f in "$LOG"/*.log; do [ -f "$f" ] && [ "$(stat -c %s "$f")" -gt 5000000 ] && tail -c 2000000 "$f" >"$f.tmp" && mv "$f.tmp" "$f"; done
echo "Dashboard: http://localhost:8787  (from a computer on the same Wi-Fi: http://$(ip -4 addr show wlan0 2>/dev/null | awk '/inet /{sub(/\/.*/,"",$2);print $2}'):8787)"
echo "Logs: $LOG    Stop services: bash scripts/termux-stop.sh"
