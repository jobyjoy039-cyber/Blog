#!/usr/bin/env bash
# Builds PixelBoost without Gradle or the Google SDK download:
#   * release/PixelBoost-<version>.aab  signed App Bundle to upload to Google Play
#   * release/PixelBoost-<version>.apk  universal APK for installing directly on a phone
#
# Needs Ubuntu/Debian's Android packages (android.jar, dx, zipalign) plus a JDK:
#   apt-get install dalvik-exchange android-sdk-platform-23 zipalign
# aapt2 comes from the bundletool jar, which is downloaded from GitHub.
# Model conversion (only if assets/*.onnx are missing) needs: pip install onnx numpy
set -euo pipefail
cd "$(dirname "$0")"

ANDROID_JAR=${ANDROID_JAR:-/usr/lib/android-sdk/platforms/android-23/android.jar}
ORT_VERSION=1.20.0        # newest onnxruntime-android with Java 8 bytecode (dx can't read newer)
BUNDLETOOL_VERSION=1.18.1
ABIS=${ABIS:-"arm64-v8a armeabi-v7a x86_64"}
B=build
mkdir -p "$B"

VERSION=$(sed -n 's/.*android:versionName="\([^"]*\)".*/\1/p' AndroidManifest.xml)
OUT=release/PixelBoost-$VERSION
mkdir -p release

# 1. Models: convert the official Real-ESRGAN weights to ONNX.
for m in realesr-general-x4v3 realesr-animevideov3 RealESRGAN_x4plus; do
  if [ ! -f "assets/$m.onnx" ]; then
    case $m in RealESRGAN_x4plus) rel=v0.1.0 ;; *) rel=v0.2.5.0 ;; esac
    [ -f "$B/$m.pth" ] || curl -fsSL -o "$B/$m.pth" "https://github.com/xinntao/Real-ESRGAN/releases/download/$rel/$m.pth"
    (cd "$B" && python3 ../tools/convert_to_onnx.py && mv -f ./*.onnx ../assets/)
  fi
done

# 2. Tools: bundletool (and the aapt2 binary it ships).
BT=$B/bundletool-$BUNDLETOOL_VERSION.jar
[ -f "$BT" ] || curl -fsSL -o "$BT" "https://github.com/google/bundletool/releases/download/$BUNDLETOOL_VERSION/bundletool-all-$BUNDLETOOL_VERSION.jar"
AAPT2=$B/aapt2
if [ ! -x "$AAPT2" ]; then
  unzip -q -o -j "$BT" linux/aapt2 -d "$B" && chmod +x "$AAPT2"
fi

# 3. ONNX Runtime: fetch the AAR, replace the lambda-using classes dx can't handle.
ORT=$B/ort-$ORT_VERSION
if [ ! -f "$ORT/ort.jar" ]; then
  rm -rf "$ORT" && mkdir -p "$ORT/classes" "$ORT/patch"
  curl -fsSL -o "$ORT/ort.aar" "https://repo1.maven.org/maven2/com/microsoft/onnxruntime/onnxruntime-android/$ORT_VERSION/onnxruntime-android-$ORT_VERSION.aar"
  (cd "$ORT" && unzip -q -o ort.aar && cd classes && unzip -q -o ../classes.jar)
  javac -nowarn -source 8 -target 8 -bootclasspath "$ANDROID_JAR" -cp "$ORT/classes.jar" -d "$ORT/patch" tools/TensorInfo.java
  cp "$ORT"/patch/ai/onnxruntime/*.class "$ORT/classes/ai/onnxruntime/"
  # CUDA/TensorRT options are desktop-only.
  rm -f "$ORT"/classes/ai/onnxruntime/providers/{StringConfigProviderOptions,OrtCUDAProviderOptions,OrtTensorRTProviderOptions}.class
  (cd "$ORT/classes" && jar cf ../ort.jar ai)
fi

# 4. Resources (proto format, as App Bundles require).
rm -rf "$B/gen" "$B/obj" "$B/module" "$B/res.zip"
mkdir -p "$B/gen" "$B/obj" "$B/module"
"$AAPT2" compile --dir res -o "$B/res.zip"
"$AAPT2" link --proto-format -o "$B/base-proto.apk" -I "$ANDROID_JAR" \
  --manifest AndroidManifest.xml --java "$B/gen" "$B/res.zip"

# 5. Java -> dex.
javac -nowarn -source 8 -target 8 -encoding UTF-8 -bootclasspath "$ANDROID_JAR" -cp "$ORT/ort.jar" \
  -d "$B/obj" $(find src "$B/gen" -name '*.java')
dalvik-exchange --dex --min-sdk-version=24 --output="$B/classes.dex" "$B/obj" "$ORT/ort.jar"

# 6. Base module: manifest/, res/, resources.pb, dex/, assets/, lib/.
M=$B/module
(cd "$M" && unzip -q ../base-proto.apk && mkdir manifest && mv AndroidManifest.xml manifest/)
mkdir -p "$M/dex" "$M/assets"
cp "$B/classes.dex" "$M/dex/"
cp assets/*.onnx licenses/licenses.txt "$M/assets/"
for abi in $ABIS; do
  mkdir -p "$M/lib/$abi"
  cp "$ORT/jni/$abi/"*.so "$M/lib/$abi/"
done
rm -f "$B/base.zip"
(cd "$M" && zip -q -r -D ../base.zip .)

# 7. Bundle + sign with the upload key.
if [ ! -f keystore.properties ]; then
  echo "keystore.properties missing: run tools/new_upload_key.sh first" >&2
  exit 1
fi
. ./keystore.properties   # storeFile, storePassword, keyAlias, keyPassword
rm -f "$OUT.aab" "$B/app.apks"
java -jar "$BT" build-bundle --modules="$B/base.zip" --output="$OUT.aab" --config=BundleConfig.json
jarsigner -keystore "$storeFile" -storepass "$storePassword" -keypass "$keyPassword" \
  -sigalg SHA256withRSA -digestalg SHA-256 "$OUT.aab" "$keyAlias"
jarsigner -verify "$OUT.aab" | tail -1

# 8. Universal APK from the bundle, for side-loading.
java -jar "$BT" build-apks --bundle="$OUT.aab" --output="$B/app.apks" --mode=universal \
  --ks="$storeFile" --ks-pass="pass:$storePassword" --ks-key-alias="$keyAlias" --key-pass="pass:$keyPassword"
unzip -q -o -p "$B/app.apks" universal.apk > "$OUT.apk"
ls -la "$OUT.aab" "$OUT.apk"
