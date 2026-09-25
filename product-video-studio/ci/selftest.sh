#!/usr/bin/env bash
# Runs on an emulator in CI: installs the APK, renders a sample product video through the
# real pipeline (analysis -> director -> background render service) and pulls the results.
set -u
APK="$1"
OUT="$2"
PKG=com.productvideostudio
FILES=/sdcard/Android/data/$PKG/files
mkdir -p "$OUT"

adb install -r -g "$APK"
adb logcat -c
adb shell am start -n $PKG/.ui.MainActivity --ez selftest true --ei duration 12 --ei fps 30

status=timeout
for i in $(seq 1 180); do
  sleep 5
  listing=$(adb shell ls $FILES 2>/dev/null || true)
  if echo "$listing" | grep -q selftest.done; then status=passed; break; fi
  if echo "$listing" | grep -q selftest.error; then status=failed; break; fi
  adb logcat -d -s SelfTest:I | tail -n 1
done
echo "self-test: $status"

for f in selftest.mp4 selftest.done selftest.error selftest-plan.json; do
  adb pull "$FILES/$f" "$OUT/$f" 2>/dev/null || true
done
# The gallery copy doubles as a check that saving to Movies worked.
mkdir -p "$OUT/gallery"
adb pull "/sdcard/Movies/Product Video Studio/." "$OUT/gallery/" || true
if [ ! -f "$OUT/selftest.mp4" ]; then cp "$OUT"/gallery/*.mp4 "$OUT/selftest.mp4" 2>/dev/null || true; fi
adb logcat -d -v time SelfTest:V RenderService:V VideoRenderer:V SceneAssets:V VoiceOver:V AudioComposer:V VisionLabeler:V Pipeline:V AndroidRuntime:E '*:S' > "$OUT/logcat.txt" || true
adb shell screencap -p /sdcard/screen.png && adb pull /sdcard/screen.png "$OUT/screen.png" || true
echo "$status" > "$OUT/status.txt"
[ "$status" = passed ]
