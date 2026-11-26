#!/usr/bin/env bash
# Offline demo: runs the dashboard + worker against the local fake YouTube API and a local RTMP
# receiver. Nothing is sent to YouTube. Open http://127.0.0.1:8790 (password: demo-password-123).
set -euo pipefail
cd "$(dirname "$0")/.."
DEMO=${DEMO_DIR:-./data-demo}
mkdir -p "$DEMO/media"
cat > "$DEMO/config.toml" <<CFG
[server]
host = "0.0.0.0"
port = 8790
public_url = "http://127.0.0.1:8790"
[paths]
data_dir = "data"
media_dir = "media"
[google]
client_id = "demo"
client_secret = "demo"
auth_uri = "http://127.0.0.1:9100/o/oauth2/auth"
token_uri = "http://127.0.0.1:9100/token"
revoke_uri = "http://127.0.0.1:9100/revoke"
api_base = "http://127.0.0.1:9100"
[encoder]
ingest_protocol = "rtmp"
[worker]
youtube_poll_seconds = 5
metrics_poll_seconds = 10
CFG
export REPLAY_STUDIO_CONFIG="$DEMO/config.toml"
if [ ! -f "$DEMO/media/demo.mp4" ]; then
  ffmpeg -hide_banner -loglevel error -y -f lavfi -i "testsrc2=size=1280x720:rate=30:duration=20" \
    -f lavfi -i "sine=frequency=440:duration=20" -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest "$DEMO/media/demo.mp4"
fi
python -m replay_studio set-password --password demo-password-123 >/dev/null
python -m replay_studio fake-youtube --port 9100 --rtmp-port 19350 --record-dir "$DEMO/fake-ingest" &
FAKE=$!
python -m replay_studio worker &
WORKER=$!
trap 'kill $FAKE $WORKER 2>/dev/null' EXIT
python -m replay_studio api
