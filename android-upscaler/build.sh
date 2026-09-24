#!/usr/bin/env bash
# Builds the Real-ESRGAN Upscaler APK without Gradle, using Ubuntu/Debian's Android packages:
#   apt-get install aapt apksigner zipalign dalvik-exchange android-sdk-platform-23
# Model conversion (only if assets/*.onnx are missing) needs: pip install onnx numpy
set -euo pipefail
cd "$(dirname "$0")"

ANDROID_JAR=${ANDROID_JAR:-/usr/lib/android-sdk/platforms/android-23/android.jar}
ORT_VERSION=1.20.0   # last onnxruntime-android release with Java 8 bytecode (dx can't read newer)
ABIS=${ABIS:-"arm64-v8a armeabi-v7a"}
B=build
mkdir -p "$B"

# 1. Models: convert the official Real-ESRGAN weights to ONNX.
for m in realesr-general-x4v3 realesr-animevideov3 RealESRGAN_x4plus; do
  if [ ! -f "assets/$m.onnx" ]; then
    case $m in RealESRGAN_x4plus) rel=v0.1.0 ;; *) rel=v0.2.5.0 ;; esac
    [ -f "$B/$m.pth" ] || curl -fsSL -o "$B/$m.pth" "https://github.com/xinntao/Real-ESRGAN/releases/download/$rel/$m.pth"
    (cd "$B" && python3 ../tools/convert_to_onnx.py && mv -f ./*.onnx ../assets/)
  fi
done

# 2. ONNX Runtime: fetch the AAR, replace the lambda-using classes dx can't handle.
ORT=$B/ort-$ORT_VERSION
if [ ! -f "$ORT/ort.jar" ]; then
  mkdir -p "$ORT/classes" "$ORT/patch"
  curl -fsSL -o "$ORT/ort.aar" "https://repo1.maven.org/maven2/com/microsoft/onnxruntime/onnxruntime-android/$ORT_VERSION/onnxruntime-android-$ORT_VERSION.aar"
  (cd "$ORT" && unzip -q -o ort.aar && cd classes && unzip -q -o ../classes.jar)
  javac -nowarn -source 8 -target 8 -bootclasspath "$ANDROID_JAR" -cp "$ORT/classes.jar" -d "$ORT/patch" tools/TensorInfo.java
  cp "$ORT"/patch/ai/onnxruntime/*.class "$ORT/classes/ai/onnxruntime/"
  # CUDA/TensorRT options are desktop-only.
  rm -f "$ORT"/classes/ai/onnxruntime/providers/{StringConfigProviderOptions,OrtCUDAProviderOptions,OrtTensorRTProviderOptions}.class
  (cd "$ORT/classes" && jar cf ../ort.jar ai)
fi

# 3. Resources + assets (models stored uncompressed).
rm -rf "$B/gen" "$B/obj" "$B/apk"
mkdir -p "$B/gen" "$B/obj" "$B/apk/lib"
# LITE=1 leaves out the large RealESRGAN_x4plus model (the app then disables that option).
ASSETS=assets
OUT=RealESRGAN-Upscaler.apk
if [ "${LITE:-0}" = 1 ]; then
  ASSETS=$B/assets-lite
  rm -rf "$ASSETS" && mkdir -p "$ASSETS"
  cp assets/realesr-*.onnx "$ASSETS/"
  OUT=RealESRGAN-Upscaler-lite.apk
fi
aapt package -f -0 onnx -M AndroidManifest.xml -S res -A "$ASSETS" -I "$ANDROID_JAR" -J "$B/gen" -F "$B/apk/base.apk"

# 4. Java -> dex.
javac -nowarn -source 8 -target 8 -encoding UTF-8 -bootclasspath "$ANDROID_JAR" -cp "$ORT/ort.jar" \
  -d "$B/obj" $(find src "$B/gen" -name '*.java')
dalvik-exchange --dex --min-sdk-version=24 --output="$B/apk/classes.dex" "$B/obj" "$ORT/ort.jar"

# 5. Add dex + native libs, align, sign.
(cd "$B/apk" && zip -q -j base.apk classes.dex)
for abi in $ABIS; do
  mkdir -p "$B/apk/lib/$abi"
  cp "$ORT/jni/$abi/"*.so "$B/apk/lib/$abi/"
done
(cd "$B/apk" && zip -q -r base.apk lib)
zipalign -f -p 4 "$B/apk/base.apk" "$B/apk/aligned.apk"

KS=${KEYSTORE:-release.keystore}
if [ ! -f "$KS" ]; then
  keytool -genkeypair -keystore "$KS" -alias upscaler -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass android -keypass android -dname "CN=Real-ESRGAN Upscaler"
fi
apksigner sign --ks "$KS" --ks-pass pass:android --ks-key-alias upscaler --key-pass pass:android \
  --out "$OUT" "$B/apk/aligned.apk"
apksigner verify "$OUT"
ls -la "$OUT"
