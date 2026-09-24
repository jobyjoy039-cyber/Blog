# Real-ESRGAN Upscaler (Android)

An Android app that upscales images 4x (or 2x) with [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN).
Everything runs on the phone (ONNX Runtime, CPU). No internet connection or account is needed.

**Install:** copy `RealESRGAN-Upscaler.apk` to your phone, open it, and allow "install unknown apps" when asked.
Needs Android 7.0+ on an ARM phone (almost all phones are ARM).

## Using it
1. Tap **Choose image**. You can also share an image to the app from your gallery.
2. Pick a model:
   * **Photo / general** (`realesr-general-x4v3`): for photos and most images. Fast.
   * **Anime / illustration** (`realesr-animevideov3`): for drawings and cartoons. About twice as fast.
   * **High quality photo** (`RealESRGAN_x4plus`): the sharpest results for photos, but 10–20x slower.
3. Pick the output size, then tap **Upscale**. Press and hold the picture to compare with the original.
   * **2x / 4x**: multiplies the size.
   * **4K / 8K**: fits the image into 3840 × 2160 or 7680 × 4320 (turned for portrait images), keeping
     its shape. If more than 4x is needed, the app runs two passes automatically. The first pass stops at
     a quarter of the final size, so the slow second pass is as small as possible.
4. **Save to gallery** writes to `Pictures/Real-ESRGAN/`. PNG is used when the image has transparency, JPEG otherwise.

Rough times on a recent phone, general model: 4K from 1080p takes about 1–2 minutes, 8K from 1080p about 2–5 minutes.
The high-quality model can take 10–30+ minutes for 8K.

Each pass produces the requested size directly: every tile's 4x output is scaled down to the target
before it's stored. The full 4x image never exists in memory, so 8K (33 MP) needs about 130 MB for the result.
Images that are already at the chosen 4K/8K size are left alone. Very large photos are subsampled while loading.

## Building
`./build.sh` builds the APK without Gradle or the Google SDK download. It uses Ubuntu's Android packages:

```
sudo apt-get install aapt apksigner zipalign dalvik-exchange android-sdk-platform-23
pip install onnx numpy   # only needed if assets/*.onnx are missing
./build.sh
```

What the script does:
* `tools/convert_to_onnx.py` turns the official `.pth` weights into ONNX. It reads the PyTorch checkpoint
  without needing PyTorch installed and rebuilds the network graph. That's SRVGGNetCompact for the two fast models
  and RRDBNet (23 blocks) for `RealESRGAN_x4plus`.
* Downloads `onnxruntime-android` 1.20.0 from Maven Central. That's the newest release with Java 8 bytecode,
  which is what `dx` can read. `tools/TensorInfo.java` swaps out the one lambda that `dx` can't convert.
* Only `arm64-v8a` and `armeabi-v7a` native libraries are included. Set `ABIS="arm64-v8a armeabi-v7a x86_64"`
  to add the emulator ABI.
* The APK is signed with `release.keystore`, created on the first build and git-ignored. Keep that file:
  updates only install over an existing copy of the app if they're signed with the same key.
