#!/data/data/com.termux/files/usr/bin/bash
# Install Replay Studio on an Android phone inside Termux (tested target: arm64 phones such as the
# Redmi Note 8 Pro). Run from the replay-studio folder:  bash scripts/termux-install.sh
set -euo pipefail
cd "$(dirname "$0")/.."
APP="$PWD"
echo "== Termux packages"
pkg update -y
pkg install -y python ffmpeg nodejs-lts termux-api openssl libffi
# Prebuilt Python wheels if Termux has them; otherwise pip compiles them with Rust below.
pkg install -y python-cryptography 2>/dev/null || true
pkg install -y python-pydantic-core 2>/dev/null || pkg install -y rust binutils 2>/dev/null || true
pkg install -y ttf-dejavu 2>/dev/null || true   # overlay font (falls back to Android's Roboto)

echo "== Storage access (allow it in the popup) so the app can read your Movies folder"
[ -d "$HOME/storage" ] || termux-setup-storage || true

echo "== Python environment"
export ANDROID_API_LEVEL="$(getprop ro.build.version.sdk)"   # needed when Rust wheels are compiled
python -m venv --system-site-packages .venv
. .venv/bin/activate
pip install --upgrade pip wheel
pip install -e .            # may take 10-30 minutes the first time if pydantic-core/cryptography compile

echo "== Dashboard"
if [ ! -f backend/replay_studio/static/index.html ]; then
  (cd frontend && npm ci && npm run build)
fi

[ -f config.toml ] || cp config.android.toml config.toml
mkdir -p "$HOME/replay-studio-data"
export REPLAY_STUDIO_CONFIG="$APP/config.toml"
if ! python - <<'PY'
from replay_studio.config import load_config; from replay_studio.db import DB
c = load_config(); import sys; sys.exit(0 if DB(c.db_path).get_setting("password_hash") else 1)
PY
then
  echo "== Choose a dashboard password"
  replay-studio set-password
fi

echo "== Start on boot (requires the Termux:Boot app from F-Droid, opened once)"
mkdir -p "$HOME/.termux/boot"
cat > "$HOME/.termux/boot/replay-studio" <<BOOT
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
bash "$APP/scripts/termux-start.sh"
BOOT
chmod +x "$HOME/.termux/boot/replay-studio"

echo
replay-studio check || true
echo
echo "Next: edit $APP/config.toml (Google client_id/client_secret), then run:"
echo "   bash scripts/termux-start.sh"
echo "and open http://localhost:8787 in Chrome on this phone."
