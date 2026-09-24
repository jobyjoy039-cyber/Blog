#!/usr/bin/env bash
# Usage: screenshots/run.sh <dir with sample images>   (run ../build.sh first)
set -euo pipefail
cd "$(dirname "$0")"
SAMPLES=$(realpath "${1:?sample image dir}"); shift
APP=$(realpath ..)
B=$APP/build
# Robolectric's "binary resources" mode: a compiled resource APK plus the assets directory.
# (Robolectric reads assets from the resource APK in this mode.)
rm -rf "$B/robo-assets" && mkdir -p "$B/robo-assets"
cp "$APP"/assets/*.onnx "$APP/licenses/licenses.txt" "$B/robo-assets/"
"$B/aapt2" link -o "$B/robo-res.apk" -I /usr/lib/android-sdk/platforms/android-23/android.jar \
  --manifest "$APP/AndroidManifest.xml" -A "$B/robo-assets" -0 onnx "$B/res.zip"
mkdir -p src/test/resources/com/android/tools
cat > src/test/resources/com/android/tools/test_config.properties <<PROPS
android_merged_manifest=$APP/AndroidManifest.xml
android_merged_assets=$B/robo-assets
android_resource_apk=$B/robo-res.apk
android_custom_package=com.jobyjoy.pixelboost
PROPS
mvn -q -B test -DsamplesDir="$SAMPLES" "$@"
