#!/usr/bin/env bash
# Creates the Play "upload key" and keystore.properties (both git-ignored).
# BACK BOTH FILES UP. Without them you can't upload updates (Google can reset an
# upload key, but it takes a support request and several days).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f upload-keystore.jks ] && { echo "upload-keystore.jks already exists" >&2; exit 1; }
PASS=$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 24)
keytool -genkeypair -keystore upload-keystore.jks -storetype PKCS12 -alias upload \
  -keyalg RSA -keysize 4096 -validity 10000 -storepass "$PASS" -keypass "$PASS" \
  -dname "CN=PixelBoost Upload Key, O=jobyjoy"
cat > keystore.properties <<PROPS
storeFile=upload-keystore.jks
storePassword=$PASS
keyAlias=upload
keyPassword=$PASS
PROPS
echo "Created upload-keystore.jks and keystore.properties"
