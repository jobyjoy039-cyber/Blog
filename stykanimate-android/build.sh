#!/usr/bin/env bash
# Builds the StykAnimate AI Android app (debug APK).
#
#   ./build.sh                       # clones StykAnimate-App at the pinned commit
#   STYK_SRC=/path/to/StykAnimate-App ./build.sh   # use an existing checkout
#
# Needs Node.js 22+, JDK 17+, and the Android SDK (ANDROID_HOME or android/local.properties).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
UPSTREAM="https://github.com/filippocalippo/StykAnimate-App.git"
UPSTREAM_COMMIT="def97214c2b491fbce82647f625a73f78416c6d8"
WWW="$HERE/android/app/src/main/assets/www"

if [[ -z "${STYK_SRC:-}" ]]; then
  STYK_SRC="$HERE/.build/StykAnimate-App"
  if [[ ! -d "$STYK_SRC/.git" ]]; then
    mkdir -p "$(dirname "$STYK_SRC")"
    git clone --filter=blob:none "$UPSTREAM" "$STYK_SRC"
  fi
  git -C "$STYK_SRC" checkout --quiet "$UPSTREAM_COMMIT"
fi

echo "==> Building the StykAnimate web editor from $STYK_SRC"
( cd "$STYK_SRC" && npm ci --ignore-scripts --no-audit --no-fund && npm run web:build )

echo "==> Assembling app assets"
rm -rf "$WWW"
mkdir -p "$WWW"
cp -R "$HERE/studio/." "$WWW/"
cp -R "$STYK_SRC/build/web" "$WWW/editor"
rm -f "$WWW/editor/_headers"
# The app ships every file itself: drop the editor's offline worker and load the
# Android bridge (file saving) before the editor's own scripts.
node - "$WWW/editor/index.html" <<'EOF'
const fs = require('fs');
const file = process.argv[2];
let html = fs.readFileSync(file, 'utf8');
html = html.replace(/\s*<script type="module" src="\.\/src\/web-offline\.mjs"><\/script>/, '');
if (!html.includes('android-bridge.js')) html = html.replace(/<head>/i, '<head>\n    <script src="../android-bridge.js"></script>');
fs.writeFileSync(file, html);
EOF

echo "==> Building the APK"
cd "$HERE/android"
./gradlew --no-daemon assembleDebug
APK="$HERE/android/app/build/outputs/apk/debug/app-debug.apk"
mkdir -p "$HERE/dist"
cp "$APK" "$HERE/dist/StykAnimate-AI-debug.apk"
echo "==> Done: $HERE/dist/StykAnimate-AI-debug.apk ($(du -h "$APK" | cut -f1))"
