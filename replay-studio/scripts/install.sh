#!/usr/bin/env bash
# Install Replay Studio as two systemd services on Debian/Ubuntu. Run from the repository folder:
#   sudo ./scripts/install.sh
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Run with sudo"; exit 1; }
SRC="$(cd "$(dirname "$0")/.." && pwd)"
apt-get update && apt-get install -y ffmpeg python3-venv python3-pip fonts-dejavu-core
id replaystudio >/dev/null 2>&1 || useradd --system --home /var/lib/replay-studio --shell /usr/sbin/nologin replaystudio
install -d -o replaystudio -g replaystudio -m 700 /var/lib/replay-studio /var/lib/replay-studio/data
install -d -o replaystudio -g replaystudio -m 750 /var/lib/replay-studio/media
install -d -m 755 /etc/replay-studio
if [ ! -f "$SRC/backend/replay_studio/static/index.html" ]; then
  command -v npm >/dev/null || apt-get install -y nodejs npm
  (cd "$SRC/frontend" && npm ci && npm run build)
fi
mkdir -p /opt/replay-studio
rm -rf /opt/replay-studio/backend
cp -r "$SRC/backend" "$SRC/pyproject.toml" /opt/replay-studio/
python3 -m venv /opt/replay-studio/.venv
/opt/replay-studio/.venv/bin/pip install -q /opt/replay-studio
if [ ! -f /etc/replay-studio/config.toml ]; then
  sed -e 's#^data_dir = .*#data_dir = "/var/lib/replay-studio/data"#' \
      -e 's#^media_dir = .*#media_dir = "/var/lib/replay-studio/media"#' \
      "$SRC/config.example.toml" > /etc/replay-studio/config.toml
  chown root:replaystudio /etc/replay-studio/config.toml
  chmod 640 /etc/replay-studio/config.toml
fi
cp "$SRC/deploy/replay-studio-api.service" "$SRC/deploy/replay-studio-worker.service" /etc/systemd/system/
systemctl daemon-reload
echo
echo "Next:"
echo "  1. sudo nano /etc/replay-studio/config.toml   (public_url, Google client_id/client_secret)"
echo "  2. sudo -u replaystudio env REPLAY_STUDIO_CONFIG=/etc/replay-studio/config.toml /opt/replay-studio/.venv/bin/replay-studio set-password"
echo "  3. sudo systemctl enable --now replay-studio-api replay-studio-worker"
