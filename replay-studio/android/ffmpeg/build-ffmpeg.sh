#!/usr/bin/env bash
# Cross-compile FFmpeg + ffprobe for Android arm64 (API 24+) with libx264 and OpenSSL (for RTMPS).
#
#   NDK=/path/to/android-ndk-r27c SRC=/path/with/tarballs OUT=/path/out ./build-ffmpeg.sh [dynamic|static]
#
# SRC must contain ffmpeg.tar.xz (7.1.1), x264.tar.gz (stable branch) and openssl.tar.gz (3.0.x).
# "dynamic" links Android's system libc (what the APK ships: DNS resolution works through Android's netd).
# "static" is a fully static build used only to test the binary on a Linux PC under qemu-aarch64.
set -euo pipefail
VARIANT="${1:-dynamic}"
API=24
: "${NDK:?set NDK}" "${SRC:?set SRC}" "${OUT:?set OUT}"
TC="$NDK/toolchains/llvm/prebuilt/linux-x86_64"
export PATH="$TC/bin:$PATH"
export CC="$TC/bin/aarch64-linux-android${API}-clang" CXX="$TC/bin/aarch64-linux-android${API}-clang++"
export AR=llvm-ar RANLIB=llvm-ranlib STRIP=llvm-strip NM=llvm-nm
WORK="$OUT/work-$VARIANT"; DEPS="$WORK/deps"
rm -rf "$WORK"; mkdir -p "$WORK" "$DEPS"
JOBS=$(nproc)
LDEXTRA=""; [ "$VARIANT" = static ] && LDEXTRA="-static"

echo "== OpenSSL"
mkdir -p "$WORK/openssl" && tar -xzf "$SRC/openssl.tar.gz" -C "$WORK/openssl" --strip-components=1
( cd "$WORK/openssl"
  export ANDROID_NDK_ROOT="$NDK"
  ./Configure android-arm64 -D__ANDROID_API__=$API no-shared no-tests no-ui-console no-engine \
      --prefix="$DEPS" --libdir=lib >/dev/null
  make -j"$JOBS" build_libs >/dev/null && make install_dev >/dev/null )

echo "== x264"
mkdir -p "$WORK/x264" && tar -xzf "$SRC/x264.tar.gz" -C "$WORK/x264" --strip-components=1
( cd "$WORK/x264"
  ./configure --host=aarch64-linux-android --cross-prefix="$TC/bin/llvm-" --sysroot="$TC/sysroot" \
      --enable-static --enable-pic --disable-cli --prefix="$DEPS" >/dev/null
  make -j"$JOBS" >/dev/null && make install >/dev/null )

echo "== TLS alignment shim"
# Only matters for the static test build: bionic's static libc.a brings an 8-byte-aligned ELF TLS variable
# (GWP-ASan), and arm64 bionic refuses executables whose TLS segment is aligned below 64 bytes. A 64-byte-
# aligned real (not emulated) TLS variable raises the segment alignment. The dynamic APK build has no TLS
# segment at all (that variable lives in the phone's libc.so); the script checks this below.
printf '__thread char replay_studio_tls_align[64] __attribute__((aligned(64), used));\n' >"$WORK/tlsalign.c"
"$CC" -c -fPIC -O2 -fno-emulated-tls "$WORK/tlsalign.c" -o "$WORK/tlsalign.o"

echo "== FFmpeg ($VARIANT)"
mkdir -p "$WORK/ffmpeg" && tar -xJf "$SRC/ffmpeg.tar.xz" -C "$WORK/ffmpeg" --strip-components=1
( cd "$WORK/ffmpeg"
  PKG_CONFIG_PATH="$DEPS/lib/pkgconfig" PKG_CONFIG_LIBDIR="$DEPS/lib/pkgconfig" ./configure \
      --prefix="$OUT/$VARIANT" --target-os=android --arch=aarch64 --cpu=armv8-a --enable-cross-compile \
      --cc="$CC" --cxx="$CXX" --nm=llvm-nm --ar=llvm-ar --ranlib=llvm-ranlib --strip=llvm-strip \
      --sysroot="$TC/sysroot" --pkg-config=pkg-config --pkg-config-flags=--static \
      --enable-pic --enable-gpl --enable-version3 --enable-libx264 --enable-openssl \
      --disable-shared --enable-static --disable-debug --disable-doc --disable-ffplay \
      --disable-vulkan --disable-mediacodec --disable-jni --disable-indevs --enable-indev=lavfi --disable-outdevs \
      --extra-cflags="-I$DEPS/include -O2" --extra-ldflags="-L$DEPS/lib $LDEXTRA" \
      $( [ "$VARIANT" = static ] && echo --extra-ldexeflags="$WORK/tlsalign.o" ) >"$WORK/ffmpeg-configure.log"
  make -j"$JOBS" >"$WORK/ffmpeg-make.log" 2>&1 && make install >/dev/null )
llvm-strip "$OUT/$VARIANT/bin/ffmpeg" "$OUT/$VARIANT/bin/ffprobe"
if [ "$VARIANT" = dynamic ] && llvm-readelf -lW "$OUT/$VARIANT/bin/ffmpeg" | grep -q " TLS "; then
  echo "ERROR: dynamic ffmpeg has an ELF TLS segment; it would not start on Android 9 and older" >&2; exit 1
fi
ls -la "$OUT/$VARIANT/bin"
echo "Built $VARIANT FFmpeg into $OUT/$VARIANT/bin"
